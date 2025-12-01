#!/bin/sh

# Stop script on first error
set -e

echo "--- Container Starting ---"

# 1. Run the Python Init Script
# This will try to connect to the DB. If the DB is still booting,
# this script might fail. Docker will restart the container automatically
# until it succeeds.
echo "Running Database Initialization..."
python init_db.py

# 2. Execute the CMD passed by Docker/Compose (Gunicorn)
echo "Starting Application..."
exec "$@"