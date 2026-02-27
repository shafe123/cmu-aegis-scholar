#!/usr/bin/env pwsh
#
# Run the DTIC entity extractors (organizations, authors, topics, and works)
#
# Usage:
#   .\run_cleaner.ps1            # Run all extractors in parallel
#   .\run_cleaner.ps1 -Orgs      # Run only organization extractor
#   .\run_cleaner.ps1 -Authors   # Run only author extractor
#   .\run_cleaner.ps1 -Topics    # Run only topic extractor
#   .\run_cleaner.ps1 -Works     # Run only work extractor
#

param(
    [switch]$Orgs,
    [switch]$Authors,
    [switch]$Topics,
    [switch]$Works,
    [switch]$Help
)

# Show help if requested
if ($Help) {
    Write-Host "DTIC Entity Extractor Runner" -ForegroundColor Cyan
    Write-Host ""
    Write-Host "Usage:" -ForegroundColor Yellow
    Write-Host "  .\run_cleaner.ps1            # Run all extractors in parallel"
    Write-Host "  .\run_cleaner.ps1 -Orgs      # Run only organization extractor"
    Write-Host "  .\run_cleaner.ps1 -Authors   # Run only author extractor"
    Write-Host "  .\run_cleaner.ps1 -Topics    # Run only topic extractor"
    Write-Host "  .\run_cleaner.ps1 -Works     # Run only work extractor"
    Write-Host "  .\run_cleaner.ps1 -Help      # Show this help"
    Write-Host ""
    Write-Host "Environment:" -ForegroundColor Yellow
    Write-Host "  AZURE_STORAGE_CONNECTION_STRING must be set"
    exit 0
}

# Ensure we're in the correct directory
Set-Location $PSScriptRoot

# Check for connection string
if (-not $env:AZURE_STORAGE_CONNECTION_STRING) {
    Write-Host "Error: AZURE_STORAGE_CONNECTION_STRING environment variable not set" -ForegroundColor Red
    Write-Host "Please set it with: `$env:AZURE_STORAGE_CONNECTION_STRING='your-connection-string'" -ForegroundColor Yellow
    exit 1
}

# Determine which extractors to run (default to all if none specified)
$runOrgs = $Orgs -or (-not $Topics -and -not $Orgs -and -not $Authors -and -not $Works)
$runAuthors = $Authors -or (-not $Topics -and -not $Orgs -and -not $Authors -and -not $Works)
$runTopics = $Topics -or (-not $Topics -and -not $Orgs -and -not $Authors -and -not $Works)
$runWorks = $Works -or (-not $Topics -and -not $Orgs -and -not $Authors -and -not $Works)

# Display what we're running
Write-Host "Starting DTIC entity extractors..." -ForegroundColor Green
if ($runOrgs) {
    Write-Host "  - Organization extractor (clean_orgs.py)" -ForegroundColor Cyan
}
if ($runAuthors) {
    Write-Host "  - Author extractor (clean_authors.py)" -ForegroundColor Cyan
}
if ($runTopics) {
    Write-Host "  - Topic extractor (clean_topics.py)" -ForegroundColor Cyan
}
if ($runWorks) {
    Write-Host "  - Work extractor (clean_works.py)" -ForegroundColor Cyan
}

$jobs = @()
$orgJob = $null
$authorJob = $null
$topicJob = $null
$workJob = $null

# Start organization extractor if requested
if ($runOrgs) {
    $orgJob = Start-Job -ScriptBlock {
        Set-Location $using:PSScriptRoot
        $env:AZURE_STORAGE_CONNECTION_STRING = $using:env:AZURE_STORAGE_CONNECTION_STRING
        poetry run python clean_orgs.py
    }
    $jobs += $orgJob
}

# Start author extractor if requested
if ($runAuthors) {
    $authorJob = Start-Job -ScriptBlock {
        Set-Location $using:PSScriptRoot
        $env:AZURE_STORAGE_CONNECTION_STRING = $using:env:AZURE_STORAGE_CONNECTION_STRING
        poetry run python clean_authors.py
    }
    $jobs += $authorJob
}

# Start topic extractor if requested
if ($runTopics) {
    $topicJob = Start-Job -ScriptBlock {
        Set-Location $using:PSScriptRoot
        $env:AZURE_STORAGE_CONNECTION_STRING = $using:env:AZURE_STORAGE_CONNECTION_STRING
        poetry run python clean_topics.py
    }
    $jobs += $topicJob
}

# Start work extractor if requested
if ($runWorks) {
    $workJob = Start-Job -ScriptBlock {
        Set-Location $using:PSScriptRoot
        $env:AZURE_STORAGE_CONNECTION_STRING = $using:env:AZURE_STORAGE_CONNECTION_STRING
        poetry run python clean_works.py
    }
    $jobs += $workJob
}

if ($jobs.Count -gt 1) {
    Write-Host "`nAll extractors running in background..." -ForegroundColor Yellow
}
else {
    Write-Host "`nExtractor running..." -ForegroundColor Yellow
}
Write-Host "Waiting for completion...`n" -ForegroundColor Yellow

# Wait for all jobs to complete
Wait-Job $jobs | Out-Null

# Get and display results
if ($orgJob) {
    $orgResult = Receive-Job $orgJob
    Write-Host "=== Organization Extractor Results ===" -ForegroundColor Cyan
    $orgResult | ForEach-Object { Write-Host $_ }
    $orgExit = $orgJob.State -eq 'Completed' ? 0 : 1
}
else {
    $orgExit = 0  # Not run, so consider it successful
}

if ($authorJob) {
    if ($orgJob) { Write-Host "" }
    $authorResult = Receive-Job $authorJob
    Write-Host "=== Author Extractor Results ===" -ForegroundColor Cyan
    $authorResult | ForEach-Object { Write-Host $_ }
    $authorExit = $authorJob.State -eq 'Completed' ? 0 : 1
}
else {
    $authorExit = 0  # Not run, so consider it successful
}

if ($topicJob) {
    if ($orgJob -or $authorJob) { Write-Host "" }
    $topicResult = Receive-Job $topicJob
    Write-Host "=== Topic Extractor Results ===" -ForegroundColor Cyan
    $topicResult | ForEach-Object { Write-Host $_ }
    $topicExit = $topicJob.State -eq 'Completed' ? 0 : 1
}
else {
    $topicExit = 0  # Not run, so consider it successful
}

if ($workJob) {
    if ($orgJob -or $authorJob -or $topicJob) { Write-Host "" }
    $workResult = Receive-Job $workJob
    Write-Host "=== Work Extractor Results ===" -ForegroundColor Cyan
    $workResult | ForEach-Object { Write-Host $_ }
    $workExit = $workJob.State -eq 'Completed' ? 0 : 1
}
else {
    $workExit = 0  # Not run, so consider it successful
}

# Clean up jobs
Remove-Job $jobs

# Show final status
Write-Host "`n=== Final Status ===" -ForegroundColor Green
if ($runOrgs) {
    if ($orgExit -eq 0) {
        Write-Host "✓ Organization extractor completed successfully" -ForegroundColor Green
    }
    else {
        Write-Host "✗ Organization extractor failed" -ForegroundColor Red
    }
}

if ($runAuthors) {
    if ($authorExit -eq 0) {
        Write-Host "✓ Author extractor completed successfully" -ForegroundColor Green
    }
    else {
        Write-Host "✗ Author extractor failed" -ForegroundColor Red
    }
}

if ($runTopics) {
    if ($topicExit -eq 0) {
        Write-Host "✓ Topic extractor completed successfully" -ForegroundColor Green
    }
    else {
        Write-Host "✗ Topic extractor failed" -ForegroundColor Red
    }
}

if ($runWorks) {
    if ($workExit -eq 0) {
        Write-Host "✓ Work extractor completed successfully" -ForegroundColor Green
    }
    else {
        Write-Host "✗ Work extractor failed" -ForegroundColor Red
    }
}

# Exit with error if any job failed
if ($orgExit -ne 0 -or $authorExit -ne 0 -or $topicExit -ne 0 -or $workExit -ne 0) {
    exit 1
}

exit 0
