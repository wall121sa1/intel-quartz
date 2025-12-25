#!/bin/sh

set -e

CREDENTIALS_FILE="${CREDENTIALS_FILE:-/credentials/credentials.txt}"
DB_PASSWORD_DEFAULT="${DB_PASSWORD_DEFAULT:-rsspass}"

read_credential() {
  if [ -f "${CREDENTIALS_FILE}" ]; then
    awk -F= -v key="$1" '$1 == key {value=$2} END {print value}' "${CREDENTIALS_FILE}"
  fi
}

if [ -n "${DATABASE_URL:-}" ]; then
  db_password=$(read_credential "POSTGRES_RSS_PASSWORD")
  if [ -n "${db_password}" ]; then
    placeholder=":${DB_PASSWORD_DEFAULT}@"
    if printf '%s' "${DATABASE_URL}" | grep -q "${placeholder}"; then
      DATABASE_URL=$(printf '%s' "${DATABASE_URL}" | sed "s/${placeholder}/:${db_password}@/")
      export DATABASE_URL
      echo "Updated RSS DATABASE_URL from credentials file."
    fi
  fi
fi

exec "$@"
