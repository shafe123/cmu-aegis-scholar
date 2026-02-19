#!/bin/bash
#
# Run the DTIC keyword amplifier
# This script fetches actual keywords from URLs in DTIC publications
#

# Check if Python is available
if ! command -v python3 &> /dev/null; then
    echo "Error: Python 3 is not installed or not in PATH"
    exit 1
fi

# Check for required environment variable
if [ -z "$AZURE_STORAGE_CONNECTION_STRING" ]; then
    echo "Error: AZURE_STORAGE_CONNECTION_STRING environment variable is not set"
    echo "Set it with: export AZURE_STORAGE_CONNECTION_STRING='your-connection-string'"
    exit 1
fi

echo "Starting DTIC keyword amplifier..."
echo ""

# Install requirements if needed
if ! pip3 show azure-storage-blob &> /dev/null; then
    echo "Installing required packages..."
    pip3 install azure-storage-blob requests
fi

# Run the amplifier
python3 amplify_keywords.py \
    --container raw \
    --source-prefix "dtic/works/" \
    --dest-prefix "dtic/works_amplified/" \
    --delay 0.5 \
    "$@"

echo ""
echo "Amplification complete!"
