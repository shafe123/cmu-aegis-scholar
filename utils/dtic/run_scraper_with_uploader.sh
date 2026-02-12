#!/bin/bash
# Example script to run scraper and uploader together
# Usage: ./run_scraper_with_uploader.sh [years] [container_name] [max_per_year]
#    Example: ./run_scraper_with_uploader.sh "1970-2026" "raw" 500
#    Or: Set AZURE_STORAGE_CONNECTION_STRING env var and it will be used automatically

set -e

YEARS="${1:-1970-2026}"
CONTAINER="${2:-raw}"
MAX_PER_YEAR="${3:-0}"

if [ -z "$AZURE_STORAGE_CONNECTION_STRING" ]; then
    echo "Error: AZURE_STORAGE_CONNECTION_STRING environment variable is not set"
    echo "Set it with: export AZURE_STORAGE_CONNECTION_STRING=\"YOUR_CONNECTION_STRING\""
    exit 1
fi

echo "Starting DTIC scraper with Azure uploader"
echo "============================================"
echo ""

# Check if uploader is already running
if pgrep -f "uploader.py.*--watch" > /dev/null; then
    EXISTING_PID=$(pgrep -f "uploader.py.*--watch")
    echo "Error: An uploader process is already running (PID: $EXISTING_PID)"
    echo "Please stop the existing uploader before starting a new one."
    echo "You can stop it with: kill $EXISTING_PID"
    exit 1
fi

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
echo "Year range: $YEARS"
if [ "$MAX_PER_YEAR" -gt 0 ]; then
    echo "Max per year: $MAX_PER_YEAR"
    poetry run python scraper.py --years "$YEARS" --max-per-year "$MAX_PER_YEAR"
else
    poetry run python scraper.py --years "$YEARS"
fi

echo ""
echo "Scraper complete."
