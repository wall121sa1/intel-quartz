#!/bin/sh

set -e

CREDENTIALS_FILE="${CREDENTIALS_FILE:-/credentials/credentials.txt}"
CREDENTIALS_KEY="${POSTGRES_CREDENTIAL_KEY:-POSTGRES_PASSWORD}"
DEFAULT_PASSWORD="${POSTGRES_PASSWORD_DEFAULT:-}"

credentials_dir=$(dirname "${CREDENTIALS_FILE}")
mkdir -p "${credentials_dir}"
touch "${CREDENTIALS_FILE}"
chmod 600 "${CREDENTIALS_FILE}"

read_credential() {
  awk -F= -v key="$1" '$1 == key {value=$2} END {print value}' "${CREDENTIALS_FILE}"
}

existing_password=$(read_credential "${CREDENTIALS_KEY}")
if [ -n "${existing_password}" ]; then
  if [ -z "${POSTGRES_PASSWORD:-}" ] || [ "${POSTGRES_PASSWORD}" = "${DEFAULT_PASSWORD}" ]; then
    POSTGRES_PASSWORD="${existing_password}"
  fi
fi

if [ -z "${POSTGRES_PASSWORD:-}" ] || [ "${POSTGRES_PASSWORD}" = "${DEFAULT_PASSWORD}" ]; then
  POSTGRES_PASSWORD=$(LC_ALL=C tr -dc 'A-Za-z0-9' </dev/urandom | head -c 24)
  printf '%s=%s\n' "${CREDENTIALS_KEY}" "${POSTGRES_PASSWORD}" >>"${CREDENTIALS_FILE}"
  echo "Generated ${CREDENTIALS_KEY}; stored at ${CREDENTIALS_FILE}."
fi

export POSTGRES_PASSWORD

if [ "$#" -eq 0 ]; then
  set -- postgres
fi

exec docker-entrypoint.sh "$@"
