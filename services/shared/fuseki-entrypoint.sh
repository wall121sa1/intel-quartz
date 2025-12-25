#!/bin/sh

set -e

CREDENTIALS_FILE="${CREDENTIALS_FILE:-/credentials/credentials.txt}"
CREDENTIALS_KEY="${FUSEKI_CREDENTIAL_KEY:-FUSEKI_ADMIN_PASSWORD}"
DEFAULT_PASSWORD="${FUSEKI_PASSWORD_DEFAULT:-changeme}"

credentials_dir=$(dirname "${CREDENTIALS_FILE}")
mkdir -p "${credentials_dir}"
touch "${CREDENTIALS_FILE}"
chmod 600 "${CREDENTIALS_FILE}"

read_credential() {
  awk -F= -v key="$1" '$1 == key {value=$2} END {print value}' "${CREDENTIALS_FILE}"
}

existing_password=$(read_credential "${CREDENTIALS_KEY}")
if [ -n "${existing_password}" ]; then
  if [ -z "${ADMIN_PASSWORD:-}" ] || [ "${ADMIN_PASSWORD}" = "${DEFAULT_PASSWORD}" ]; then
    ADMIN_PASSWORD="${existing_password}"
  fi
fi

if [ -z "${ADMIN_PASSWORD:-}" ] || [ "${ADMIN_PASSWORD}" = "${DEFAULT_PASSWORD}" ]; then
  ADMIN_PASSWORD=$(LC_ALL=C tr -dc 'A-Za-z0-9' </dev/urandom | head -c 24)
  printf '%s=%s\n' "${CREDENTIALS_KEY}" "${ADMIN_PASSWORD}" >>"${CREDENTIALS_FILE}"
  echo "Generated ${CREDENTIALS_KEY}; stored at ${CREDENTIALS_FILE}."
fi

export ADMIN_PASSWORD

exec "$@"
