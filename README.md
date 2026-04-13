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
git clone https://github.com/Monear/ghostpod
cd ghostpod
cp .env.example .env
# fill in .env — see below

# Tailscale mode (default)
docker compose up --build

# LAN mode — exposes ports 80/443 on the host
docker compose -f docker-compose.yml -f docker-compose.lan.yml up --build
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

Leave `TS_AUTHKEY` empty and Caddy will use its internal CA to issue a self-signed cert for your local IP or hostname. LAN mode needs host port bindings, so use the override file:

```bash
docker compose -f docker-compose.yml -f docker-compose.lan.yml up --build
```

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

## License

MIT

---

## Notice

Built with AI assistance (Anthropic Claude). Reviewed by me. Provided as-is — see [LICENSE](./LICENSE).
