#!/usr/bin/env pwsh
# Example script to run scraper and uploader together
# Usage: .\run_scraper_with_uploader.ps1 -ConnectionString "YOUR_CONNECTION_STRING" -Years "1970-2026"
#    Or: Set $env:AZURE_STORAGE_CONNECTION_STRING and run without -ConnectionString

param(
    [string]$ConnectionString = $env:AZURE_STORAGE_CONNECTION_STRING,
    [string]$Container = "raw",
    [string]$Years = "1970-2026",
    [int]$MaxPerYear = 1000
)

if (-not $ConnectionString) {
    Write-Host "Error: Connection string is required" -ForegroundColor Red
    Write-Host "Either set AZURE_STORAGE_CONNECTION_STRING environment variable or use -ConnectionString parameter" -ForegroundColor Yellow
    exit 1
}

Write-Host "Starting DTIC scraper with Azure uploader" -ForegroundColor Green
Write-Host "============================================" -ForegroundColor Green
Write-Host ""

# Check if uploader is already running
$existingUploader = Get-Process -Name python -ErrorAction SilentlyContinue | Where-Object {
    $_.CommandLine -like "*uploader.py*--watch*"
}

if ($existingUploader) {
    Write-Host "Error: An uploader process is already running (PID: $($existingUploader.Id))" -ForegroundColor Red
    Write-Host "Please stop the existing uploader before starting a new one." -ForegroundColor Yellow
    Write-Host "You can stop it with: Stop-Process -Id $($existingUploader.Id)" -ForegroundColor Yellow
    exit 1
}

# Start uploader in background
Write-Host "Starting uploader in watch mode..." -ForegroundColor Cyan
$uploaderJob = Start-Job -ScriptBlock {
    param($connStr, $container)
    Set-Location $using:PWD
    $env:AZURE_STORAGE_CONNECTION_STRING = $connStr
    poetry run python uploader.py `
        --container $container `
        --watch `
        --interval 5
} -ArgumentList $ConnectionString, $Container

Write-Host "Uploader started (Job ID: $($uploaderJob.Id))" -ForegroundColor Green
Write-Host ""

# Give uploader time to initialize
Start-Sleep -Seconds 2

# Start scraper
Write-Host "Starting scraper..." -ForegroundColor Cyan
Write-Host "Year range: $Years" -ForegroundColor Yellow
if ($MaxPerYear -gt 0) {
    Write-Host "Max per year: $MaxPerYear" -ForegroundColor Yellow
    poetry run python scraper.py --years $Years --max-per-year $MaxPerYear
}
else {
    poetry run python scraper.py --years $Years
}

# Stop uploader
Write-Host ""
Write-Host "Scraper complete. Stopping uploader..." -ForegroundColor Cyan
Stop-Job -Id $uploaderJob.Id
Remove-Job -Id $uploaderJob.Id

Write-Host ""
Write-Host "All done!" -ForegroundColor Green
