#!/bin/sh

set -e

if [ -z "${ADMIN_PASSWORD:-}" ]; then
  echo "ERROR: ADMIN_PASSWORD must be set via the .env file." >&2
  exit 1
fi

export ADMIN_PASSWORD

exec "$@"
