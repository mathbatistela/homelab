#!/bin/sh
# Bridge the published port -> Camoufox's loopback port, then run the server in
# the foreground (so a crash exits the container and Docker restarts it).
set -eu

EXT_PORT="${CAMOUFOX_PORT:-9222}"
INT_PORT="${CAMOUFOX_INTERNAL_PORT:-9223}"

# fork = one child per connection; reuseaddr = fast restart. Backend refuses
# until Camoufox is up, which is fine (clients retry / connect once ready).
socat TCP-LISTEN:"${EXT_PORT}",fork,reuseaddr TCP:127.0.0.1:"${INT_PORT}" &

exec python /app/server.py
