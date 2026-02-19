#!/usr/bin/env pwsh
<#
.SYNOPSIS
    Run Cosmos DB loader for JSON data from Azure Blob Storage

.DESCRIPTION
    This script runs the Cosmos DB loader to load JSON data (regular, compressed, or JSONL format) 
    from Azure Blob Storage into Cosmos DB. Supports multiple data sources (DTIC, OpenAlex, etc.).
    It checks for required environment variables and dependencies.

.PARAMETER ForceReload
    Force reload of all documents, including already loaded ones

.PARAMETER StateFile
    Custom state file path (default: load_state.json)

.PARAMETER BlobContainer
    Azure Blob Storage container name (default: raw)

.PARAMETER BlobPrefix
    Blob prefix to filter files (e.g., "dtic/works/", "openalex/works/")

.PARAMETER CosmosDatabase
    Cosmos DB database name (default: aegisraw)

.PARAMETER CosmosContainer
    Cosmos DB container name (default: dtic-works)

.PARAMETER PartitionKey
    Partition key path for Cosmos DB (default: id)

.EXAMPLE
    .\run_loader.ps1

.EXAMPLE
    .\run_loader.ps1 -ForceReload

.EXAMPLE
    .\run_loader.ps1 -BlobPrefix "dtic/works/"

.EXAMPLE
    .\run_loader.ps1 -BlobPrefix "openalex/works/" -CosmosContainer "openalex-works"

.EXAMPLE
    .\run_loader.ps1 -CosmosDatabase "my-database" -CosmosContainer "my-container"
#>

param(
    [switch]$ForceReload,
    [string]$StateFile = "load_state.json",
    [string]$BlobContainer = "raw",
    [string]$BlobPrefix = "",
    [string]$CosmosDatabase = "aegisraw",
    [string]$CosmosContainer = "dtic-works",
    [string]$PartitionKey = "id"
)

# Color output functions
function Write-Info($message) {
    Write-Host "[INFO] $message" -ForegroundColor Cyan
}

function Write-Success($message) {
    Write-Host "[OK] $message" -ForegroundColor Green
}

function Write-Error($message) {
    Write-Host "[ERROR] $message" -ForegroundColor Red
}

function Write-Warning($message) {
    Write-Host "[WARN] $message" -ForegroundColor Yellow
}

# Check Python installation
Write-Info "Checking Python installation..."
$pythonCmd = Get-Command python -ErrorAction SilentlyContinue

if (-not $pythonCmd) {
    Write-Error "Python is not installed or not in PATH"
    Write-Info "Please install Python 3.8 or higher from https://www.python.org/"
    exit 1
}

$pythonVersion = python --version 2>&1
Write-Success "Found $pythonVersion"

# Check if script exists
$scriptPath = Join-Path $PSScriptRoot "load_dtic.py"
if (-not (Test-Path $scriptPath)) {
    Write-Error "load_dtic.py not found at: $scriptPath"
    exit 1
}

# Check required environment variables
Write-Info "Checking environment variables..."

$missingVars = @()

if (-not $env:AZURE_STORAGE_CONNECTION_STRING) {
    $missingVars += "AZURE_STORAGE_CONNECTION_STRING"
}

if (-not $env:COSMOS_ENDPOINT) {
    $missingVars += "COSMOS_ENDPOINT"
}

if (-not $env:COSMOS_KEY) {
    $missingVars += "COSMOS_KEY"
}

if ($missingVars.Count -gt 0) {
    Write-Error "Missing required environment variables:"
    foreach ($var in $missingVars) {
        Write-Host "  - $var" -ForegroundColor Red
    }
    Write-Host ""
    Write-Info "Set environment variables using:"
    Write-Host '  $env:AZURE_STORAGE_CONNECTION_STRING="..."' -ForegroundColor Yellow
    Write-Host '  $env:COSMOS_ENDPOINT="https://..."' -ForegroundColor Yellow
    Write-Host '  $env:COSMOS_KEY="..."' -ForegroundColor Yellow
    exit 1
}

Write-Success "All required environment variables are set"

# Check dependencies
Write-Info "Checking Python dependencies..."
$requiredPackages = @("azure-storage-blob", "azure-cosmos")
$missingPackages = @()

foreach ($package in $requiredPackages) {
    $installed = python -c "import importlib.util; print(importlib.util.find_spec('$($package.Replace('-', '_'))') is not None)" 2>$null
    if ($installed -ne "True") {
        $missingPackages += $package
    }
}

if ($missingPackages.Count -gt 0) {
    Write-Warning "Missing required packages: $($missingPackages -join ', ')"
    Write-Info "Installing missing packages..."
    foreach ($package in $missingPackages) {
        Write-Info "Installing $package..."
        python -m pip install $package
        if ($LASTEXITCODE -ne 0) {
            Write-Error "Failed to install $package"
            exit 1
        }
    }
    Write-Success "All dependencies installed"
}
else {
    Write-Success "All dependencies are installed"
}

# Build command
$cmd = @(
    "python",
    $scriptPath,
    "--blob-container", $BlobContainer,
    "--cosmos-database", $CosmosDatabase,
    "--cosmos-container", $CosmosContainer,
    "--partition-key", $PartitionKey,
    "--state-file", $StateFile
)

if ($BlobPrefix) {
    $cmd += "--blob-prefix"
    $cmd += $BlobPrefix
}

if ($ForceReload) {
    $cmd += "--force-reload"
}

# Run the loader
Write-Host ""
Write-Info "Starting Cosmos DB loader..."
Write-Host "=" * 70 -ForegroundColor Cyan
Write-Host ""

& $cmd[0] $cmd[1..($cmd.Length - 1)]

$exitCode = $LASTEXITCODE

Write-Host ""
Write-Host "=" * 70 -ForegroundColor Cyan

if ($exitCode -eq 0) {
    Write-Success "Loader completed successfully"
}
else {
    Write-Error "Loader failed with exit code: $exitCode"
}

exit $exitCode
