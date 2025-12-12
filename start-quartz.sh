#!/usr/bin/env bash
set -euo pipefail

# Default to the shared watcher vault mount if VAULT_ROOT is not provided.
CLEANUP_TARGET=${VAULT_ROOT:-docs/watcher_vault}

if [ $# -eq 0 ]; then
  set -- npx quartz build --serve
fi

PYTHON_BIN=${PYTHON_BIN:-python3}
if [ -x /opt/quartz-venv/bin/python3 ]; then
  PYTHON_BIN=/opt/quartz-venv/bin/python3
fi

echo "🧹 Running frontmatter cleanup for '${CLEANUP_TARGET}' before starting Quartz using ${PYTHON_BIN}..."
"${PYTHON_BIN}" watcher/app/cleanup_frontmatter.py "$CLEANUP_TARGET"

echo "🚀 Launching Quartz with command: $*"
exec "$@"
