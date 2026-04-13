#!/bin/sh
set -e

if [ -n "$TS_AUTHKEY" ]; then
    # Validate auth key format before starting Caddy — an invalid key causes
    # Caddy to exit non-zero and the container to restart in an infinite loop
    # with no obvious error unless you check the logs.
    case "$TS_AUTHKEY" in
        tskey-auth-*)
            ;;
        *)
            echo "[caddy] ERROR: TS_AUTHKEY does not look like a valid Tailscale auth key."
            echo "[caddy]        Expected format: tskey-auth-<key>"
            echo "[caddy]        Generate one at: https://login.tailscale.com/admin/settings/keys"
            exit 1
            ;;
    esac
    echo "[caddy] Tailscale mode — joining tailnet as '${TS_HOSTNAME:-ghostpod}'"
    cp /etc/caddy/Caddyfile.tailscale /etc/caddy/Caddyfile
else
    echo "[caddy] LAN mode — using self-signed TLS (tls internal)"
    cp /etc/caddy/Caddyfile.lan /etc/caddy/Caddyfile
fi

exec caddy run --config /etc/caddy/Caddyfile --adapter caddyfile
