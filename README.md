# ghostpod

A self-hosted browser terminal with per-session ephemeral containers, mobile support, and optional Tailscale or LAN TLS — deployable with a single `docker compose up`.

Each browser session gets a fresh, isolated container that is destroyed on disconnect. Nothing persists between sessions.

---

## Features

- **Per-session isolation** — every connection spawns a fresh container, destroyed on disconnect
- **Auth** — styled login page with bcrypt-verified credentials and signed session cookies
- **Tailscale mode** — Caddy joins your tailnet, gets a real TLS cert automatically
- **LAN mode** — Caddy's internal CA issues a self-signed cert for your local IP or hostname
- **Mobile-friendly** — toolbar with Ctrl, Esc, Tab, arrow keys; touch text selection; iOS keyboard awareness
- **Sandboxed containers** — dangerous capabilities dropped, memory and PID limits enforced

---

## Requirements

- Docker and Docker Compose
- Docker socket access on the host (`/var/run/docker.sock`)
- For Tailscale mode: a [Tailscale account](https://tailscale.com) and an auth key

---

## Quick Start

```bash
git clone https://github.com/Monear/ghostpod
cd ghostpod
cp .env.example .env
# Edit .env — see Configuration below
docker compose up --build
```

---

## Configuration

All configuration lives in `.env`. Copy `.env.example` to get started.

### Tailscale mode (recommended)

Caddy joins your tailnet as a node and gets a real Let's Encrypt certificate automatically. No browser warnings, no CA installation needed on any device.

```env
# Auth key from https://login.tailscale.com/admin/settings/keys
# Use a reusable, ephemeral key
TS_AUTHKEY=tskey-auth-...

# Must match the machine name in your Tailscale admin console
TS_HOSTNAME=ghostpod
```

Access at `https://ghostpod.<your-tailnet>.ts.net`.

### LAN mode

Caddy issues a certificate via its internal CA for your local IP or hostname. Set `TS_AUTHKEY` to empty (or omit it) to use LAN mode.

```env
TS_AUTHKEY=

# IP or hostname browsers will connect to
LAN_HOST=192.168.1.100
```

#### Trusting the CA on your devices

The first time Caddy starts it creates a local CA. Export and install it once per device for a trusted green padlock.

```bash
# Export the CA cert
docker exec ghostpod-caddy \
  cat /data/caddy/pki/authorities/local/root.crt > caddy-local-ca.crt
```

- **macOS / iOS** — open the `.crt` file, add to Keychain, set to Always Trust
- **Android** — Settings → Security → Install certificate
- **Windows** — double-click the `.crt`, install to Trusted Root CAs
- **Linux** — copy to `/usr/local/share/ca-certificates/` and run `update-ca-certificates`

### Auth

Auth is handled by the orchestrator. When `ADMIN_USER` and `ADMIN_PASSWORD_HASH` are set, an unauthenticated request redirects to a login page.

```env
ADMIN_USER=admin

# Generate a bcrypt hash:
#   docker run --rm caddy:latest caddy hash-password --plaintext 'yourpassword'
# Escape every $ in the hash as $$ so docker-compose doesn't expand it.
# Example: $2a$14$abc... becomes $$2a$$14$$abc...
ADMIN_PASSWORD_HASH=$$2a$$14$$...

# Signs session cookies — generate with: openssl rand -hex 32
# If unset, a random key is used (sessions lost on restart).
SECRET_KEY=
```

Leave `ADMIN_PASSWORD_HASH` empty to run without authentication (useful for initial setup or trusted-network-only deployments).

---

## Architecture

```
Browser
  └── Caddy  (TLS termination — Tailscale cert or internal CA)
        └── Orchestrator  (auth, session lifecycle, WebSocket proxy)
              └── Session container  (ephemeral ttyd + zsh, destroyed on disconnect)
```

**Caddy** handles TLS only — either via the caddy-tailscale module (real LE certs) or `tls internal` (self-signed). It proxies everything to the orchestrator.

**Orchestrator** (`orchestrator/main.py`) is a small Python/aiohttp service that:
- Serves the terminal HTML (pre-built with mobile toolbar at image build time)
- Handles login and session cookie verification
- Spawns a Docker container per WebSocket connection
- Bidirectionally proxies WebSocket frames between the browser and the container's ttyd process
- Stops and removes the container when either side disconnects

**Session containers** run `ttyd --once`, so they exit as soon as the first client disconnects. Combined with `--rm`, the container is removed immediately. Each container gets:
- A friendly random hostname (`eager-narwhal`, `polar-kestrel`, etc.) visible in the shell prompt
- Dropped capabilities (`SYS_ADMIN`, `NET_ADMIN`, `SYS_MODULE`, `SYS_PTRACE`, and others)
- Memory limit (512 MB) and PID limit (256)

---

## Customising the shell environment

Dotfiles are baked into the session image (`terminal/`). Edit and rebuild to change the shell environment:

```
terminal/
  .zshrc          — zsh config
  starship.toml   — Starship prompt (Catppuccin Mocha theme)
  .tmux.conf      — tmux config
```

```bash
docker compose up --build
```

---

## License

MIT
