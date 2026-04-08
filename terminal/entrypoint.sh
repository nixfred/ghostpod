#!/bin/sh
set -e

mkdir -p /root/.local/bin

# ttyd --once exits after the first client disconnects.
# The container has --rm, so Docker removes it immediately after.
exec ttyd \
  --once \
  --port 7681 \
  --writable \
  -t rendererType=dom \
  /bin/zsh
