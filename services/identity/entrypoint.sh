#!/bin/bash
set -e

# Wait for LDAP server to accept connections
echo "Checking connection to LDAP server (ldap-server:1389)..."
until timeout 1 bash -c "cat < /dev/null > /dev/tcp/ldap-server/1389"; do
  echo "LDAP not ready yet. Sleeping 2s..."
  sleep 2
done

# Use a flag file in the mounted /data volume to track whether
# the initial sync has already completed.
SYNC_FLAG="/data/.initial_sync_done"
API_HOST="${API_HOST:-0.0.0.0}"
API_PORT="${API_PORT:-8000}"

if [ ! -f "$SYNC_FLAG" ]; then
    echo "--- First-time setup: Starting record sync ---"
    python3 -c "from app.main import process_and_sync_file; process_and_sync_file()"
    touch "$SYNC_FLAG"
else
    echo "--- Persistent data detected. Running incremental check ---"
    python3 -c "from app.main import process_and_sync_file; process_and_sync_file()"
fi

echo "Starting FastAPI Gateway on ${API_HOST}:${API_PORT}..."
exec uvicorn app.main:app --host "$API_HOST" --port "$API_PORT"

