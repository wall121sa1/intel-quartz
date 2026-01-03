#!/bin/sh

# Stop script on first error
set -e

echo "--- Container Starting ---"
echo "Entrypoint command: $@"

require_env() {
  name=$1
  value=$(eval "printf '%s' \"\${${name}:-}\"")
  if [ -z "${value}" ]; then
    echo "ERROR: ${name} must be set via the .env file." >&2
    exit 1
  fi
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

require_env "SECRET_KEY"
require_env "ENCRYPTION_KEY"
require_env "DATABASE_URL"
require_env "ADMIN_EMAIL"
require_env "ADMIN_PASSWORD"

# 1. Run the Python Init Script
# This will try to connect to the DB. If the DB is still booting,
# this script might fail. Docker will restart the container automatically
# until it succeeds.
echo "Running Database Initialization..."
python init_db.py

# 2. Execute the CMD passed by Docker/Compose (Gunicorn)
echo "Starting Application..."
exec "$@"
