#!/bin/sh

set -e

CREDENTIALS_FILE="${CREDENTIALS_FILE:-/credentials/credentials.txt}"
DB_PASSWORD_DEFAULT="${DB_PASSWORD_DEFAULT:-rsspass}"

read_credential() {
  if [ -f "${CREDENTIALS_FILE}" ]; then
    awk -F= -v key="$1" '$1 == key {value=$2} END {print value}' "${CREDENTIALS_FILE}"
  fi
}

update_database_url() {
  python - <<'PY'
import os
from urllib.parse import quote, urlparse, urlunparse

url = os.environ.get("DATABASE_URL")
password = os.environ.get("DB_PASSWORD")

if not url or not password:
    raise SystemExit

parsed = urlparse(url)
if not parsed.username:
    print(url)
    raise SystemExit

username = quote(parsed.username, safe="")
hostname = parsed.hostname or ""
port = f":{parsed.port}" if parsed.port else ""
userinfo = f"{username}:{quote(password, safe='')}@"
netloc = f"{userinfo}{hostname}{port}"
new_url = urlunparse(
    (parsed.scheme, netloc, parsed.path, parsed.params, parsed.query, parsed.fragment)
)
print(new_url)
PY
}

if [ -n "${DATABASE_URL:-}" ]; then
  db_password=$(read_credential "POSTGRES_RSS_PASSWORD")
  if [ -n "${db_password}" ]; then
    DB_PASSWORD="${db_password}"
    export DB_PASSWORD
    DATABASE_URL=$(update_database_url)
    export DATABASE_URL
    echo "Updated RSS DATABASE_URL from credentials file."
  fi
fi

exec "$@"
