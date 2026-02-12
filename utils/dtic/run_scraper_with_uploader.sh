#!/bin/bash
# Example script to run scraper and uploader together
# Usage: ./run_scraper_with_uploader.sh [max_publications] [container_name]
#    Or: Set AZURE_STORAGE_CONNECTION_STRING env var and it will be used automatically

set -e

MAX_PUBLICATIONS="${1:-100}"
CONTAINER="${2:-dtic-publications}"

if [ -z "$AZURE_STORAGE_CONNECTION_STRING" ]; then
    echo "Error: AZURE_STORAGE_CONNECTION_STRING environment variable is not set"
    echo "Set it with: export AZURE_STORAGE_CONNECTION_STRING=\"YOUR_CONNECTION_STRING\""
    exit 1
fi

echo "Starting DTIC scraper with Azure uploader"
echo "============================================"
echo ""

# Start uploader in background
echo "Starting uploader in watch mode..."
poetry run python uploader.py \
    --container "$CONTAINER" \
    --watch \
    --interval 5 &

UPLOADER_PID=$!
echo "Uploader started (PID: $UPLOADER_PID)"
echo ""

# Give uploader time to initialize
sleep 2

# Trap to ensure uploader is stopped
cleanup() {
    echo ""
    echo "Stopping uploader..."
    kill $UPLOADER_PID 2>/dev/null || true
    wait $UPLOADER_PID 2>/dev/null || true
    echo "All done!"
}
trap cleanup EXIT INT TERM

# Start scraper
echo "Starting scraper..."
poetry run python scraper.py --max-publications "$MAX_PUBLICATIONS"

echo ""
echo "Scraper complete."
