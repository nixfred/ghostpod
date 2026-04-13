"""
Orchestrator: per-session ephemeral terminal containers.

Flow for each browser connection:
  1. Browser loads GET / → redirected to /login if not authenticated
  2. User submits login form → POST /login verifies credentials, sets
     a signed session cookie, redirects to /
  3. Browser JS calls GET /token → returns empty token (no ttyd auth)
  4. Browser JS opens WebSocket at /ws
  5. Orchestrator spawns a fresh session container
  6. Bidirectionally proxies WebSocket frames between browser and container
  7. On disconnect (either side), stops and removes the container
"""

import asyncio
import base64
import hashlib
import hmac
import json
import logging
import os
import random
import secrets
import time
import uuid

import aiohttp
from aiohttp import web
import bcrypt
import docker
import docker.errors

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
log = logging.getLogger(__name__)

SESSION_IMAGE  = os.getenv("SESSION_IMAGE",  "ghostpod-session:latest")
SESSION_NETWORK = os.getenv("SESSION_NETWORK", "ghostpod-sessions")
TTYD_PORT      = 7681
STATIC_DIR     = os.path.join(os.path.dirname(__file__), "static")

ADMIN_USER          = os.getenv("ADMIN_USER", "")
ADMIN_PASSWORD_HASH = os.getenv("ADMIN_PASSWORD_HASH", "")
SESSION_COOKIE      = "st_session"
SESSION_TTL         = 86400  # 24 hours

_raw_secret = os.getenv("SECRET_KEY", "")
if not _raw_secret:
    _raw_secret = secrets.token_hex(32)
    log.warning("SECRET_KEY not set — sessions will not survive restarts")
SECRET_KEY = _raw_secret

docker_client = docker.from_env()

# ── Word lists for friendly session names ──────────────────────────────────────

_ADJECTIVES = [
    "autumn", "bold", "calm", "deft", "eager", "fleet", "grand", "happy",
    "ivory", "jolly", "keen", "lofty", "misty", "noble", "ocean", "polar",
    "quiet", "rapid", "solar", "teal", "ultra", "vivid", "warm", "xenon",
    "young", "zesty", "amber", "brisk", "crisp", "dusty", "early", "faint",
    "glowy", "hazy", "inky", "jade", "kinetic", "lunar", "mellow", "neon",
]

_NOUNS = [
    "badger", "falcon", "heron", "ibis", "jaguar", "kestrel", "lynx",
    "marmot", "narwhal", "osprey", "puffin", "quail", "rabbit", "salmon",
    "thrush", "viper", "walrus", "xerus", "yak", "zebu", "condor", "dingo",
    "egret", "finch", "gibbon", "hyena", "impala", "jackal", "kodiak",
    "lemur", "magpie", "numbat", "ocelot", "petrel", "quokka", "raven",
]


def _random_name() -> str:
    return f"{random.choice(_ADJECTIVES)}-{random.choice(_NOUNS)}"


# ── Auth ───────────────────────────────────────────────────────────────────────

_LOGIN_PAGE = """\
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width,initial-scale=1">
  <title>ghostpod</title>
  <style>
    *{{box-sizing:border-box;margin:0;padding:0}}
    body{{background:#1e1e2e;color:#cdd6f4;font-family:monospace;
          display:flex;align-items:center;justify-content:center;min-height:100vh}}
    .card{{background:#181825;border:1px solid #313244;border-radius:8px;
           padding:2rem;width:100%;max-width:360px}}
    h1{{font-size:1.1rem;color:#cba4f7;margin-bottom:1.5rem;letter-spacing:.05em}}
    h1 span{{color:#6c7086}}
    label{{display:block;font-size:.75rem;color:#6c7086;margin-bottom:.4rem;
           text-transform:uppercase;letter-spacing:.08em}}
    input{{width:100%;background:#313244;border:1px solid #45475a;border-radius:4px;
           color:#cdd6f4;font-family:monospace;font-size:.9rem;
           padding:.6rem .75rem;margin-bottom:1rem;outline:none}}
    input:focus{{border-color:#89b4fa}}
    button{{width:100%;background:#89b4fa;color:#1e1e2e;border:none;
            border-radius:4px;font-family:monospace;font-size:.9rem;font-weight:700;
            padding:.65rem;cursor:pointer;margin-top:.5rem}}
    button:hover{{background:#b4befe}}
    .error{{background:#45475a;border-left:3px solid #f38ba8;color:#f38ba8;
            font-size:.8rem;padding:.5rem .75rem;margin-bottom:1rem;
            border-radius:0 4px 4px 0}}
  </style>
</head>
<body>
  <div class="card">
    <h1>sandbox<span>-</span>terminal</h1>
    {error}
    <form method="post" action="/login">
      <label for="u">username</label>
      <input id="u" name="username" type="text" autocomplete="username" autofocus>
      <label for="p">password</label>
      <input id="p" name="password" type="password" autocomplete="current-password">
      <button type="submit">connect &#8594;</button>
    </form>
  </div>
</body>
</html>"""

_ERROR_BLOCK = '<div class="error">invalid credentials</div>'


def _auth_required() -> bool:
    return bool(ADMIN_USER and ADMIN_PASSWORD_HASH)


def _make_token() -> str:
    payload = base64.urlsafe_b64encode(
        json.dumps({"exp": time.time() + SESSION_TTL}).encode()
    ).decode().rstrip("=")
    sig = hmac.new(SECRET_KEY.encode(), payload.encode(), hashlib.sha256).hexdigest()
    return f"{payload}.{sig}"


def _valid_token(token: str) -> bool:
    try:
        payload, sig = token.rsplit(".", 1)
        expected = hmac.new(
            SECRET_KEY.encode(), payload.encode(), hashlib.sha256
        ).hexdigest()
        if not hmac.compare_digest(sig, expected):
            return False
        padding = "=" * (-len(payload) % 4)
        data = json.loads(base64.urlsafe_b64decode(payload + padding))
        return data["exp"] > time.time()
    except Exception:
        return False


def _check_password(password: str) -> bool:
    try:
        return bcrypt.checkpw(password.encode(), ADMIN_PASSWORD_HASH.encode())
    except Exception:
        return False


def _authenticated(request: web.Request) -> bool:
    if not _auth_required():
        return True
    return _valid_token(request.cookies.get(SESSION_COOKIE, ""))


def _login_redirect() -> web.Response:
    return web.HTTPFound("/login")


# ── Network setup ──────────────────────────────────────────────────────────────

def ensure_session_network():
    try:
        docker_client.networks.get(SESSION_NETWORK)
        log.info(f"Session network '{SESSION_NETWORK}' already exists")
    except docker.errors.NotFound:
        docker_client.networks.create(SESSION_NETWORK, driver="bridge")
        log.info(f"Created session network '{SESSION_NETWORK}'")


# ── WebSocket proxy ────────────────────────────────────────────────────────────

async def wait_for_ttyd(ip: str, timeout: float = 30.0) -> bool:
    deadline = asyncio.get_event_loop().time() + timeout
    async with aiohttp.ClientSession() as session:
        while asyncio.get_event_loop().time() < deadline:
            try:
                async with session.get(
                    f"http://{ip}:{TTYD_PORT}/",
                    timeout=aiohttp.ClientTimeout(total=1.0),
                ):
                    return True
            except Exception:
                await asyncio.sleep(0.25)
    return False


async def proxy_websockets(
    ws_browser: web.WebSocketResponse,
    ws_ttyd: aiohttp.ClientWebSocketResponse,
):
    async def forward(src, dst, label: str):
        try:
            async for msg in src:
                if msg.type == aiohttp.WSMsgType.TEXT:
                    await dst.send_str(msg.data)
                elif msg.type == aiohttp.WSMsgType.BINARY:
                    await dst.send_bytes(msg.data)
                elif msg.type in (aiohttp.WSMsgType.CLOSE, aiohttp.WSMsgType.ERROR):
                    log.info(f"[proxy] {label} closed")
                    break
        except Exception as exc:
            log.warning(f"[proxy] {label} error: {exc}")

    tasks = [
        asyncio.create_task(forward(ws_browser, ws_ttyd, "browser→ttyd")),
        asyncio.create_task(forward(ws_ttyd, ws_browser, "ttyd→browser")),
    ]
    _, pending = await asyncio.wait(tasks, return_when=asyncio.FIRST_COMPLETED)
    for task in pending:
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass


# ── Route handlers ─────────────────────────────────────────────────────────────

async def handle_login_get(request: web.Request) -> web.Response:
    return web.Response(
        content_type="text/html",
        text=_LOGIN_PAGE.format(error=""),
    )


async def handle_login_post(request: web.Request) -> web.Response:
    data = await request.post()
    username = data.get("username", "")
    password = data.get("password", "")

    if username == ADMIN_USER and _check_password(password):
        response = web.HTTPFound("/")
        response.set_cookie(
            SESSION_COOKIE,
            _make_token(),
            max_age=SESSION_TTL,
            httponly=True,
            samesite="Strict",
        )
        return response

    return web.Response(
        content_type="text/html",
        text=_LOGIN_PAGE.format(error=_ERROR_BLOCK),
        status=401,
    )


async def handle_index(request: web.Request) -> web.FileResponse:
    if not _authenticated(request):
        raise _login_redirect()
    return web.FileResponse(os.path.join(STATIC_DIR, "index.html"))


async def handle_token(request: web.Request) -> web.Response:
    if not _authenticated(request):
        raise web.HTTPUnauthorized()
    return web.Response(
        content_type="application/json",
        text=json.dumps({"token": ""}),
    )


async def handle_ws(request: web.Request) -> web.WebSocketResponse:
    if not _authenticated(request):
        raise web.HTTPUnauthorized()

    session_id = str(uuid.uuid4())[:8]
    container = None
    loop = asyncio.get_event_loop()

    log.info(f"[{session_id}] New session")

    ws_browser = web.WebSocketResponse(protocols=["tty"])
    await ws_browser.prepare(request)

    try:
        session_name = _random_name()
        container = await loop.run_in_executor(
            None,
            lambda: docker_client.containers.run(
                SESSION_IMAGE,
                detach=True,
                remove=True,
                network=SESSION_NETWORK,
                name=f"{session_name}-{session_id}",
                hostname=session_name,
                labels={"ghostpod.session": session_id},
                # security_opt removed — breaks sudo for non-root user
                cap_drop=["SYS_ADMIN", "NET_ADMIN", "SYS_MODULE", "SYS_RAWIO",
                           "SYS_BOOT", "SYS_PTRACE", "AUDIT_WRITE", "AUDIT_CONTROL",
                           "MAC_ADMIN", "MAC_OVERRIDE", "SYSLOG"],
                mem_limit="512m",
                memswap_limit="512m",
                pids_limit=256,
                volumes={"/home/pi/ghostpod/.ssh": {"bind": "/tmp/.host-ssh", "mode": "ro"}},
            ),
        )
        log.info(f"[{session_id}] Container {container.short_id} started as '{session_name}'")

        await loop.run_in_executor(None, container.reload)
        container_ip = (
            container.attrs["NetworkSettings"]["Networks"][SESSION_NETWORK]["IPAddress"]
        )
        log.info(f"[{session_id}] Container IP: {container_ip}")

        ready = await wait_for_ttyd(container_ip)
        if not ready:
            log.error(f"[{session_id}] ttyd did not become ready in time")
            await ws_browser.close(code=1011, message=b"Session container failed to start")
            return ws_browser

        async with aiohttp.ClientSession() as http_session:
            async with http_session.ws_connect(
                f"ws://{container_ip}:{TTYD_PORT}/ws",
                protocols=["tty"],
            ) as ws_ttyd:
                log.info(f"[{session_id}] Proxying session")
                await proxy_websockets(ws_browser, ws_ttyd)

    except Exception as exc:
        log.error(f"[{session_id}] Unhandled error: {exc}", exc_info=True)
        if not ws_browser.closed:
            await ws_browser.close(code=1011, message=b"Internal server error")
    finally:
        if container:
            try:
                await loop.run_in_executor(None, lambda: container.stop(timeout=3))
                log.info(f"[{session_id}] Container stopped")
            except Exception:
                pass

    log.info(f"[{session_id}] Session ended")
    return ws_browser


# ── App factory ────────────────────────────────────────────────────────────────

def create_app() -> web.Application:
    app = web.Application()
    app.router.add_get("/login", handle_login_get)
    app.router.add_post("/login", handle_login_post)
    app.router.add_get("/", handle_index)
    app.router.add_get("/token", handle_token)
    app.router.add_get("/ws", handle_ws)
    return app


if __name__ == "__main__":
    ensure_session_network()
    if _auth_required():
        log.info(f"Auth enabled for user '{ADMIN_USER}'")
    else:
        log.warning("Auth disabled — set ADMIN_USER and ADMIN_PASSWORD_HASH to enable")
    app = create_app()
    web.run_app(app, host="0.0.0.0", port=8080)
