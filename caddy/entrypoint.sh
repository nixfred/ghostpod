#!/bin/sh
set -e

if [ -n "$TS_AUTHKEY" ]; then
    echo "[caddy] Tailscale mode — joining tailnet as '${TS_HOSTNAME:-ghostpod}'"
    cp /etc/caddy/Caddyfile.tailscale /etc/caddy/Caddyfile
else
    echo "[caddy] LAN mode — using self-signed TLS (tls internal)"
    cp /etc/caddy/Caddyfile.lan /etc/caddy/Caddyfile
fi

exec caddy run --config /etc/caddy/Caddyfile --adapter caddyfile
