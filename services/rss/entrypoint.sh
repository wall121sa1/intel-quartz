#!/bin/sh
set -e

if [ "$(id -u)" = "0" ]; then
  mkdir -p /app/sessions
  chown -R appuser:appuser /app/sessions
  exec gosu appuser "$@"
fi

exec "$@"
