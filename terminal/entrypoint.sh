#!/bin/sh
set -e

mkdir -p /home/pi/.local/bin

# Copy host SSH keys with correct ownership/permissions for pi
if [ -d /tmp/.host-ssh ]; then
    mkdir -p /home/pi/.ssh
    # Everything in the directory is copied, not a fixed filename list: a host
    # that needs more than one identity (an RSA key for older boxes alongside
    # ed25519) would otherwise have the extra keys silently dropped.
    for f in /tmp/.host-ssh/*; do
        [ -f "$f" ] || continue
        name=${f##*/}
        cp "$f" /home/pi/.ssh/ 2>/dev/null || continue
        case "$name" in
            *.pub) chmod 644 "/home/pi/.ssh/$name" ;;
            *)     chmod 600 "/home/pi/.ssh/$name" ;;
        esac
    done
    chown -R pi:pi /home/pi/.ssh
fi

# Two modes, chosen by the orchestrator via GHOSTPOD_PERSIST.
#
# Ephemeral (default): ttyd --once exits after the first client disconnects and
# the container has --rm, so Docker removes it immediately after.
#
# Persistent: --once is dropped so ttyd keeps serving, and the shell runs inside
# tmux so the state lives in the tmux server rather than in the connection. A
# phone locking its screen, or iOS suspending a background tab, drops the
# WebSocket; on return ttyd accepts a new client which reattaches to the same
# tmux session, with the same scrollback and the same running processes. Without
# tmux, a reconnect would still land in a brand-new shell even though the
# container survived.
if [ -n "$GHOSTPOD_PERSIST" ]; then
    exec ttyd \
      --port 7681 \
      --writable \
      -t rendererType=dom \
      su - pi -c 'exec tmux new-session -A -s main'
else
    exec ttyd \
      --once \
      --port 7681 \
      --writable \
      -t rendererType=dom \
      su - pi
fi
