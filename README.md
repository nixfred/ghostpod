# ghostpod

A self-hosted browser terminal that spins up a fresh, isolated container for every session and tears it down on disconnect. Nothing persists. One command to run.

---

## Why

My iPad + keyboard is genuinely one of my favourite ways to work. Portable, great battery, proper keyboard — the problem is there's no decent Linux terminal on iPadOS. iSH exists but it's an x86 emulator running under the hood and it crawls the moment you ask anything of it.

What I wanted was a real shell I could hit from a browser tab, on any device, that felt clean every time I opened it. So I built ghostpod.

---

## What it does

- **Ephemeral sessions** — every connection gets a fresh container. Close the tab, it's gone.
- **Auth** — login page with bcrypt passwords and signed session cookies, or skip it entirely on a trusted network
- **Tailscale mode** — Caddy joins your tailnet and gets a real TLS cert automatically. No cert warnings, works on iOS.
- **LAN mode** — Caddy's internal CA for local IP/hostname access. Install the CA once per device.
- **Mobile toolbar** — Ctrl, Esc, Tab, arrow keys as buttons. Touch selection. iOS keyboard handling.
- **Sandboxed** — dropped capabilities, 512 MB memory cap, 256 PID limit per session

---

## Requirements

- Docker + Docker Compose
- The Docker socket (`/var/run/docker.sock`) — the orchestrator needs it to spawn containers at runtime
- A [Tailscale](https://tailscale.com) account + auth key if you want Tailscale mode

---

## Quick Start

```bash
git clone https://github.com/nixfred/ghostpod
cd ghostpod
cp .env.example .env
# fill in .env — see below
docker compose up --build
```

---

## Configuration

Everything lives in `.env`. Start from `.env.example`.

### Tailscale mode (what I use)

Caddy joins your tailnet as a node. Real Let's Encrypt cert, no browser warnings, works from my iPad without any extra setup.

```env
# from https://login.tailscale.com/admin/settings/keys — use a reusable ephemeral key
TS_AUTHKEY=tskey-auth-...

# must match the machine name in your Tailscale admin console
TS_HOSTNAME=ghostpod
```

Hit it at `https://ghostpod.<your-tailnet>.ts.net`.

### LAN mode

Leave `TS_AUTHKEY` empty and Caddy will use its internal CA to issue a self-signed cert for your local IP or hostname.

```env
TS_AUTHKEY=

LAN_HOST=192.168.1.100
```

#### Installing the CA

First boot, Caddy creates a local CA. Export it and install it once per device:

```bash
docker exec ghostpod-caddy \
  cat /data/caddy/pki/authorities/local/root.crt > caddy-local-ca.crt
```

- **macOS / iOS** — open the `.crt`, add to Keychain, set to Always Trust
- **Android** — Settings → Security → Install certificate
- **Windows** — double-click, install to Trusted Root CAs
- **Linux** — drop in `/usr/local/share/ca-certificates/`, run `update-ca-certificates`

### Behind an external reverse proxy (Traefik, nginx, etc.)

If you already have a reverse proxy that handles TLS (Traefik, nginx, Caddy running elsewhere), you can skip the bundled Caddy and point it directly at the orchestrator on port `8080`.

Drop in a `docker-compose.override.yml`:

```yaml
services:
  caddy:
    profiles: [disabled]      # don't start the bundled Caddy

  orchestrator:
    networks:
      - default
      - sessions
      - proxy                 # your existing reverse-proxy network
    labels:
      # --- example: Traefik v3 labels ---
      - traefik.enable=true
      - traefik.docker.network=proxy
      - traefik.http.routers.ghostpod.rule=Host(`shell.example.com`)
      - traefik.http.routers.ghostpod.entrypoints=websecure
      - traefik.http.routers.ghostpod.tls=true
      - traefik.http.services.ghostpod.loadbalancer.server.port=8080

networks:
  proxy:
    external: true
```

Two things to know:

- **WebSockets must be HTTP/1.1 to the backend.** The orchestrator uses aiohttp and will reject an HTTP/2 upgrade with `400 No WebSocket UPGRADE hdr`. Traefik and nginx already default to HTTP/1.1 upstream; just don't force HTTP/2-to-backend.
- **No auth is set by default**, so the reverse proxy is your only front door — either keep it on a trusted network (Tailscale, VPN, LAN) or set `ADMIN_USER` + `ADMIN_PASSWORD_HASH` in `.env`.

### Auth

Set `ADMIN_USER` and `ADMIN_PASSWORD_HASH` and unauthenticated requests get redirected to a login page. Leave them empty to run open — fine if it's Tailscale-only.

```env
ADMIN_USER=admin

# generate the hash:
#   docker run --rm caddy:latest caddy hash-password --plaintext 'yourpassword'
# escape every $ as $$ or docker-compose will mangle it
ADMIN_PASSWORD_HASH=$$2a$$14$$...

# signs session cookies — generate with: openssl rand -hex 32
# leave empty and a random key is used (sessions won't survive restarts)
SECRET_KEY=
```

---

## How it works

```
Browser
  └── Caddy  (TLS — Tailscale cert or internal CA)
        └── Orchestrator  (auth, session lifecycle, WebSocket proxy)
              └── Session container  (ttyd + zsh, gone on disconnect)
```

**Caddy** does TLS and proxies everything to the orchestrator. That's it.

**Orchestrator** is a small Python/aiohttp service. It serves the terminal page, checks auth, spawns a container per WebSocket connection, and bidirectionally proxies frames between the browser and the container's ttyd process. When either side disconnects, it stops and removes the container.

**Session containers** run `ttyd --once` so they self-exit the moment the client disconnects. Each one gets a random hostname (`eager-narwhal`, `polar-kestrel`, etc.), dropped capabilities, and hard resource limits.

---

## Customising the shell

Dotfiles live in `terminal/` and are baked into the session image at build time. Edit them and run `docker compose up --build` to rebuild.

```
terminal/
  .zshrc          — zsh config
  starship.toml   — Starship prompt (Catppuccin Mocha theme)
  .tmux.conf      — tmux config
```

---

## SSH from inside a session

Sessions can inherit an SSH identity from the host so you can `ssh somehost` from a ghostpod tab without re-typing anything.

On the host, drop the key material at `~/ghostpod/.ssh/`:

```bash
mkdir -p ~/ghostpod/.ssh
cp ~/.ssh/id_ed25519      ~/ghostpod/.ssh/
cp ~/.ssh/id_ed25519.pub  ~/ghostpod/.ssh/
cp ~/.ssh/known_hosts     ~/ghostpod/.ssh/   # optional
chmod 700 ~/ghostpod/.ssh
chmod 600 ~/ghostpod/.ssh/id_ed25519
```

The orchestrator bind-mounts that directory into every spawned session read-only at `/tmp/.host-ssh`, and `terminal/entrypoint.sh` copies the files into the session user's `~/.ssh/` with the right owner and permissions.

The copy looks only for these filenames: `id_ed25519`, `id_ed25519.pub`, `config`, `known_hosts`. Anything else is ignored.

**Caveat on `config`** — it's copied verbatim. A Mac-style config with `Include "/Users/..."` paths, `IdentityFile` references to files that don't exist in the container (`~/.ssh/id_rsa`), or `Host <x>` entries forcing a different user will produce warnings or break name resolution in the session. If in doubt, skip the `config` file — the session defaults (`pi@<host>` with `id_ed25519`) work fine for most cases.

Every session gets the same identity. Treat `~/ghostpod/.ssh/id_ed25519` as the identity for *the ghostpod deployment*, not necessarily your personal key.

---

## License

MIT

---

## Notice

Built with AI assistance (Anthropic Claude). Reviewed by me. Provided as-is — see [LICENSE](./LICENSE).
