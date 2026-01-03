#!/bin/sh

set -e

if [ -z "${POSTGRES_PASSWORD:-}" ]; then
  echo "ERROR: POSTGRES_PASSWORD must be set via the .env file." >&2
  exit 1
fi

if [ "$#" -eq 0 ]; then
  set -- postgres
fi

exec docker-entrypoint.sh "$@"
