#!/usr/bin/env bash
set -euo pipefail

# Do not start Quartz automatically; default to an interactive shell unless a command is provided.
if [ $# -eq 0 ]; then
  set -- bash
fi

echo "🚀 Launching command: $*"
exec "$@"
