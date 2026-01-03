#!/bin/sh

set -e

if [ -z "${DATABASE_URL:-}" ]; then
  echo "ERROR: DATABASE_URL must be set via the .env file." >&2
  exit 1
fi

exec "$@"
