#!/usr/bin/env bash
set -euo pipefail

# Default to the shared watcher vault mount if VAULT_ROOT is not provided.
CLEANUP_TARGET=${VAULT_ROOT:-docs/watcher_vault}

# Do not start Quartz automatically; default to an interactive shell unless a command is provided.
if [ $# -eq 0 ]; then
  set -- bash
fi

PYTHON_BIN=${PYTHON_BIN:-python3}
if [ -x /opt/quartz-venv/bin/python3 ]; then
  PYTHON_BIN=/opt/quartz-venv/bin/python3
fi

COMMAND_LOWER=${*,,}
if [[ ${COMMAND_LOWER} == *quartz* ]]; then
  echo "🧹 Running frontmatter cleanup for '${CLEANUP_TARGET}' before starting Quartz using ${PYTHON_BIN}..."
  "${PYTHON_BIN}" watcher/app/cleanup_frontmatter.py "$CLEANUP_TARGET"
else
  echo "ℹ️ Skipping frontmatter cleanup; no Quartz command detected."
fi

echo "🚀 Launching command: $*"
exec "$@"
