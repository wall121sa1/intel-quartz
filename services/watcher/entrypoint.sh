#!/bin/sh

# Stop script on first error
set -e

echo "--- Container Starting ---"
echo "Entrypoint command: $@"

secrets_file=""

generate_secret_key() {
  python - <<'PY'
import secrets
print(secrets.token_urlsafe(32))
PY
}

generate_encryption_key() {
  python - <<'PY'
from cryptography.fernet import Fernet
print(Fernet.generate_key().decode())
PY
}

ensure_secret() {
  key_name=$1
  generator=$2
  shift 2

  current_value=$(eval "printf '%s' \"\${${key_name}:-}\"")
  for default_value in "$@"; do
    if [ "${current_value}" = "${default_value}" ]; then
      current_value=""
      break
    fi
  done

  if [ -z "${current_value}" ] && [ -f "${secrets_file}" ]; then
    stored_value=$(grep -m 1 "^${key_name}=" "${secrets_file}" | cut -d= -f2-)
    if [ -n "${stored_value}" ]; then
      current_value="${stored_value}"
    fi
  fi

  if [ -z "${current_value}" ]; then
    current_value=$(${generator})
    printf '%s=%s\n' "${key_name}" "${current_value}" >>"${secrets_file}"
    echo "Generated ${key_name}; stored at ${secrets_file}."
  fi

  export "${key_name}=${current_value}"
}

wait_for_service() {
  url=$1
  name=$2
  attempts=${3:-15}
  delay=${4:-2}

  echo "Checking ${name} availability at ${url}..."
  for i in $(seq 1 "${attempts}"); do
    if curl -fsS "${url}" >/dev/null 2>&1; then
      echo "${name} is reachable (attempt ${i}/${attempts})."
      return 0
    fi

    echo "${name} not ready yet (attempt ${i}/${attempts}); retrying in ${delay}s..."
    sleep "${delay}"
  done

  echo "Warning: ${name} did not respond after ${attempts} attempts." >&2
}

if printf '%s\n' "$@" | grep -q "worker.py"; then
  echo "Detected worker container startup; scheduler will be enabled."
else
  echo "Detected web container startup; running Gunicorn server."
fi

if [ -n "${NER_SERVICE_URL:-}" ]; then
  wait_for_service "${NER_SERVICE_URL%/}/health/ready" "NER service"
else
  echo "NER_SERVICE_URL is not set; skipping NER readiness check."
fi

if [ -n "${LIBRETRANSLATE_URL:-}" ]; then
  wait_for_service "${LIBRETRANSLATE_URL%/}/health" "LibreTranslate"
else
  echo "LIBRETRANSLATE_URL is not set; skipping LibreTranslate readiness check."
fi

VAULT_ROOT=${VAULT_ROOT:-/app/vault_data}
secrets_file="${VAULT_ROOT}/generated-secrets.env"
mkdir -p "${VAULT_ROOT}"

if [ ! -f "${secrets_file}" ]; then
  touch "${secrets_file}"
  chmod 600 "${secrets_file}"
fi

ensure_secret "SECRET_KEY" generate_secret_key "change-me" "dev-secret-key"
ensure_secret "ENCRYPTION_KEY" generate_encryption_key "change-me-too" "change-me"

# 1. Run the Python Init Script
# This will try to connect to the DB. If the DB is still booting,
# this script might fail. Docker will restart the container automatically
# until it succeeds.
echo "Running Database Initialization..."
python init_db.py

# 2. Execute the CMD passed by Docker/Compose (Gunicorn)
echo "Starting Application..."
exec "$@"
