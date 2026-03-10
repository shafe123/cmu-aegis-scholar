#!/usr/bin/env pwsh
<#
.SYNOPSIS
    Quick start script for the embedding model evaluation pipeline.

.DESCRIPTION
    This script automates the setup and execution of the evaluation pipeline:
    1. Checks prerequisites
    2. Starts Milvus vector database
    3. Runs the evaluation

.PARAMETER Model
    Name of the embedding model to evaluate. Use "all" to evaluate all models.

.PARAMETER GroundTruth
    Path to the ground truth CSV file.

.PARAMETER AllModels
    Switch to evaluate all available models.

.PARAMETER SkipSetup
    Skip Docker and dependency checks.

.PARAMETER MaxBlobs
    Maximum number of blob files to process (for testing).

.EXAMPLE
    .\quick_start.ps1 -Model "sentence-transformers/all-MiniLM-L6-v2" -GroundTruth "Author Ratings - Overall.csv"

.EXAMPLE
    .\quick_start.ps1 -AllModels -GroundTruth "Author Ratings - Overall.csv"
#>

[CmdletBinding()]
param(
    [Parameter(Mandatory = $false)]
    [string]$Model = "sentence-transformers/all-MiniLM-L6-v2",
    
    [Parameter(Mandatory = $false)]
    [string]$GroundTruth = "Author Ratings - Overall.csv",
    
    [Parameter(Mandatory = $false)]
    [switch]$AllModels,
    
    [Parameter(Mandatory = $false)]
    [switch]$SkipSetup,
    
    [Parameter(Mandatory = $false)]
    [int]$MaxBlobs = 0
)

$ErrorActionPreference = "Stop"

# Color output functions
function Write-Success {
    param([string]$Message)
    Write-Host "✓ $Message" -ForegroundColor Green
}

function Write-Info {
    param([string]$Message)
    Write-Host "ℹ $Message" -ForegroundColor Cyan
}

function Write-Warning-Custom {
    param([string]$Message)
    Write-Host "⚠ $Message" -ForegroundColor Yellow
}

function Write-Error-Custom {
    param([string]$Message)
    Write-Host "✗ $Message" -ForegroundColor Red
}

# Banner
Write-Host ""
Write-Host "================================================" -ForegroundColor Magenta
Write-Host "  Embedding Model Evaluation Pipeline" -ForegroundColor Magenta
Write-Host "  CMU AEGIS Scholar" -ForegroundColor Magenta
Write-Host "================================================" -ForegroundColor Magenta
Write-Host ""

if (-not $SkipSetup) {
    Write-Info "Checking prerequisites..."
    
    # Check Python
    try {
        $pythonVersion = python --version 2>&1
        Write-Success "Python: $pythonVersion"
    }
    catch {
        Write-Error-Custom "Python not found. Please install Python 3.10+"
        exit 1
    }
    
    # Check Docker
    try {
        $dockerVersion = docker --version
        Write-Success "Docker: $dockerVersion"
    }
    catch {
        Write-Error-Custom "Docker not found. Please install Docker Desktop"
        exit 1
    }
    
    # Check Docker Compose
    try {
        $composeVersion = docker-compose --version
        Write-Success "Docker Compose: $composeVersion"
    }
    catch {
        Write-Error-Custom "Docker Compose not found. Please install Docker Compose"
        exit 1
    }
    
    Write-Host ""
    
    # Check virtual environment
    Write-Info "Checking Python virtual environment..."
    if (-not (Test-Path "venv")) {
        Write-Warning-Custom "Virtual environment not found. Creating..."
        python -m venv venv
        Write-Success "Virtual environment created"
    }
    else {
        Write-Success "Virtual environment exists"
    }
    
    # Activate virtual environment
    Write-Info "Activating virtual environment..."
    & ".\venv\Scripts\Activate.ps1"
    
    # Install dependencies
    Write-Info "Installing/updating dependencies..."
    pip install -q -r requirements.txt
    Write-Success "Dependencies installed"
    
    Write-Host ""
    
    # Check Milvus
    Write-Info "Checking Milvus status..."
    $milvusRunning = docker-compose ps -q milvus
    
    if (-not $milvusRunning) {
        Write-Warning-Custom "Milvus not running. Starting..."
        docker-compose up -d
        Write-Info "Waiting for Milvus to be ready (60 seconds)..."
        Start-Sleep -Seconds 60
        Write-Success "Milvus started"
    }
    else {
        Write-Success "Milvus is running"
    }
    
    Write-Host ""
}

# Check Azure connection string
Write-Info "Checking Azure Storage connection..."
if (-not $env:AZURE_STORAGE_CONNECTION_STRING) {
    Write-Warning-Custom "AZURE_STORAGE_CONNECTION_STRING not set"
    Write-Host "Please set it with:"
    Write-Host '  $env:AZURE_STORAGE_CONNECTION_STRING = "your-connection-string"' -ForegroundColor Yellow
    Write-Host ""
    $continue = Read-Host "Continue anyway? (y/n)"
    if ($continue -ne "y") {
        exit 1
    }
}
else {
    Write-Success "Azure connection string configured"
}

Write-Host ""

# Check ground truth file
if (-not (Test-Path $GroundTruth)) {
    Write-Error-Custom "Ground truth file not found: $GroundTruth"
    exit 1
}
Write-Success "Ground truth file found: $GroundTruth"

Write-Host ""
Write-Host "================================================" -ForegroundColor Magenta
Write-Host "  Starting Evaluation" -ForegroundColor Magenta
Write-Host "================================================" -ForegroundColor Magenta
Write-Host ""

# Build command
$cmd = "python run_evaluation.py --ground-truth `"$GroundTruth`""

if ($AllModels) {
    $cmd += " --all-models"
    Write-Info "Mode: Evaluating ALL models"
}
else {
    $cmd += " --model `"$Model`""
    Write-Info "Mode: Evaluating single model - $Model"
}

if ($MaxBlobs -gt 0) {
    $cmd += " --max-blobs $MaxBlobs"
    Write-Info "Limiting to $MaxBlobs blob files (testing mode)"
}

Write-Host ""
Write-Info "Running: $cmd"
Write-Host ""

# Run evaluation
Invoke-Expression $cmd

if ($LASTEXITCODE -eq 0) {
    Write-Host ""
    Write-Host "================================================" -ForegroundColor Green
    Write-Host "  Evaluation Complete!" -ForegroundColor Green
    Write-Host "================================================" -ForegroundColor Green
    Write-Host ""
    Write-Success "Results saved to: results/"
    Write-Host ""
    Write-Host "Next steps:"
    Write-Host "  1. Review results in the results/ directory"
    Write-Host "  2. Check summary.json for overall metrics"
    Write-Host "  3. Stop Milvus: docker-compose down"
    Write-Host ""
}
else {
    Write-Host ""
    Write-Host "================================================" -ForegroundColor Red
    Write-Host "  Evaluation Failed" -ForegroundColor Red
    Write-Host "================================================" -ForegroundColor Red
    Write-Host ""
    Write-Error-Custom "Evaluation exited with code $LASTEXITCODE"
    Write-Host ""
    Write-Host "Troubleshooting:"
    Write-Host "  1. Check logs above for error messages"
    Write-Host "  2. Verify Milvus is running: docker-compose ps"
    Write-Host "  3. Check Milvus logs: docker-compose logs milvus"
    Write-Host "  4. See README.md for more help"
    Write-Host ""
    exit $LASTEXITCODE
}
