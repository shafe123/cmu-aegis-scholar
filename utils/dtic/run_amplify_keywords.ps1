#!/usr/bin/env pwsh
#
# Run the DTIC keyword amplifier
# This script fetches actual keywords from URLs in DTIC publications
#

# Check if Python is available
if (-not (Get-Command python -ErrorAction SilentlyContinue)) {
    Write-Error "Python is not installed or not in PATH"
    exit 1
}

# Check for required environment variable
if (-not $env:AZURE_STORAGE_CONNECTION_STRING) {
    Write-Error "AZURE_STORAGE_CONNECTION_STRING environment variable is not set"
    Write-Host "Set it with: `$env:AZURE_STORAGE_CONNECTION_STRING='your-connection-string'"
    exit 1
}

Write-Host "Starting DTIC keyword amplifier..." -ForegroundColor Green
Write-Host ""

# Install requirements if needed
if (-not (pip show azure-storage-blob 2>$null)) {
    Write-Host "Installing required packages..." -ForegroundColor Yellow
    pip install azure-storage-blob requests
}

# Run the amplifier
python amplify_keywords.py `
    --container raw `
    --source-prefix "dtic/works/" `
    --dest-prefix "dtic/works/" `
    --delay 0.5 `
    $args

Write-Host ""
Write-Host "Amplification complete!" -ForegroundColor Green
