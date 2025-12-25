#!/bin/sh

set -e

CREDENTIALS_FILE="${CREDENTIALS_FILE:-/credentials/credentials.txt}"
CREDENTIALS_KEY="${FUSEKI_CREDENTIAL_KEY:-FUSEKI_ADMIN_PASSWORD}"
DEFAULT_PASSWORD="${FUSEKI_PASSWORD_DEFAULT:-changeme}"

credentials_dir=$(dirname "${CREDENTIALS_FILE}")
if mkdir -p "${credentials_dir}" 2>/dev/null; then
  if touch "${CREDENTIALS_FILE}" 2>/dev/null; then
    chmod 600 "${CREDENTIALS_FILE}" 2>/dev/null || true
  else
    echo "Warning: cannot touch ${CREDENTIALS_FILE}; proceeding without credentials file." >&2
  fi
else
  echo "Warning: cannot create ${credentials_dir}; proceeding without credentials file." >&2
fi

read_credential() {
  if [ -f "${CREDENTIALS_FILE}" ]; then
    awk -F= -v key="$1" '$1 == key {value=$2} END {print value}' "${CREDENTIALS_FILE}"
  fi
}

existing_password=$(read_credential "${CREDENTIALS_KEY}")
if [ -n "${existing_password}" ]; then
  if [ -z "${ADMIN_PASSWORD:-}" ] || [ "${ADMIN_PASSWORD}" = "${DEFAULT_PASSWORD}" ]; then
    ADMIN_PASSWORD="${existing_password}"
  fi
fi

if [ -z "${ADMIN_PASSWORD:-}" ] || [ "${ADMIN_PASSWORD}" = "${DEFAULT_PASSWORD}" ]; then
  ADMIN_PASSWORD=$(LC_ALL=C tr -dc 'A-Za-z0-9' </dev/urandom | head -c 24)
  if [ -w "${CREDENTIALS_FILE}" ]; then
    printf '%s=%s\n' "${CREDENTIALS_KEY}" "${ADMIN_PASSWORD}" >>"${CREDENTIALS_FILE}"
    echo "Generated ${CREDENTIALS_KEY}; stored at ${CREDENTIALS_FILE}."
  else
    echo "Generated ${CREDENTIALS_KEY}; credentials file not writable." >&2
  fi
fi

export ADMIN_PASSWORD

exec "$@"
