#!/bin/sh
set -e

mkdir -p /home/pi/.local/bin

# Copy host SSH keys with correct ownership/permissions for pi
if [ -d /tmp/.host-ssh ]; then
    mkdir -p /home/pi/.ssh
    cp /tmp/.host-ssh/id_ed25519 /home/pi/.ssh/ 2>/dev/null && chmod 600 /home/pi/.ssh/id_ed25519
    cp /tmp/.host-ssh/id_ed25519.pub /home/pi/.ssh/ 2>/dev/null && chmod 644 /home/pi/.ssh/id_ed25519.pub
    cp /tmp/.host-ssh/config /home/pi/.ssh/ 2>/dev/null && chmod 600 /home/pi/.ssh/config
    cp /tmp/.host-ssh/known_hosts /home/pi/.ssh/ 2>/dev/null && chmod 600 /home/pi/.ssh/known_hosts
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
