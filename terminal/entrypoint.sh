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

# ttyd --once exits after the first client disconnects.
# The container has --rm, so Docker removes it immediately after.
exec ttyd \
  --once \
  --port 7681 \
  --writable \
  -t rendererType=dom \
  su - pi
