#!/bin/bash

# Run Cosmos DB loader for JSON data from Azure Blob Storage
# This script runs the Cosmos DB loader to load JSON data (regular, compressed, or JSONL format)
# from Azure Blob Storage into Cosmos DB. Supports multiple data sources (DTIC, OpenAlex, etc.).
# It checks for required environment variables and dependencies.

set -e  # Exit on error

# Color output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
NC='\033[0m' # No Color

info() {
    echo -e "${CYAN}[INFO]${NC} $1"
}

success() {
    echo -e "${GREEN}[OK]${NC} $1"
}

error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

warning() {
    echo -e "${YELLOW}[WARN]${NC} $1"
}

# Parse command line arguments
FORCE_RELOAD=""
STATE_FILE="load_state.json"
BLOB_CONTAINER="dtic-publications"
BLOB_PREFIX=""
COSMOS_DATABASE="aegis-scholar"
COSMOS_CONTAINER="publications"
PARTITION_KEY="id"

while [[ $# -gt 0 ]]; do
    case $1 in
        --force-reload)
            FORCE_RELOAD="--force-reload"
            shift
            ;;
        --state-file)
            STATE_FILE="$2"
            shift 2
            ;;
        --blob-container)
            BLOB_CONTAINER="$2"
            shift 2
            ;;
        --blob-prefix)
            BLOB_PREFIX="$2"
            shift 2
            ;;
        --cosmos-database)
            COSMOS_DATABASE="$2"
            shift 2
            ;;
        --cosmos-container)
            COSMOS_CONTAINER="$2"
            shift 2
            ;;
        --partition-key)
            PARTITION_KEY="$2"
            shift 2
            ;;
        -h|--help)
            echo "Usage: $0 [OPTIONS]"
            echo ""
            echo "Options:"
            echo "  --force-reload              Force reload all documents"
            echo "  --state-file FILE           Custom state file path (default: load_state.json)"
            echo "  --blob-container NAME       Blob container name (default: dtic-publications)"
            echo "  --blob-prefix PREFIX        Blob prefix to filter files (e.g., 'dtic/works/', 'openalex/works/')"
            echo "  --cosmos-database NAME      Cosmos database name (default: aegis-scholar)"
            echo "  --cosmos-container NAME     Cosmos container name (default: publications)"
            echo "  --partition-key KEY         Partition key path (default: id)"
            echo "  -h, --help                  Show this help message"
            exit 0
            ;;
        *)
            error "Unknown option: $1"
            echo "Use --help for usage information"
            exit 1
            ;;
    esac
done

# Check Python installation
info "Checking Python installation..."
if ! command -v python3 &> /dev/null; then
    error "Python 3 is not installed or not in PATH"
    info "Please install Python 3.8 or higher"
    exit 1
fi

PYTHON_VERSION=$(python3 --version 2>&1)
success "Found $PYTHON_VERSION"

# Get script directory
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
SCRIPT_PATH="$SCRIPT_DIR/load_dtic.py"

# Check if script exists
if [ ! -f "$SCRIPT_PATH" ]; then
    error "load_dtic.py not found at: $SCRIPT_PATH"
    exit 1
fi

# Check required environment variables
info "Checking environment variables..."

MISSING_VARS=()

if [ -z "$AZURE_STORAGE_CONNECTION_STRING" ]; then
    MISSING_VARS+=("AZURE_STORAGE_CONNECTION_STRING")
fi

if [ -z "$COSMOS_ENDPOINT" ]; then
    MISSING_VARS+=("COSMOS_ENDPOINT")
fi

if [ -z "$COSMOS_KEY" ]; then
    MISSING_VARS+=("COSMOS_KEY")
fi

if [ ${#MISSING_VARS[@]} -gt 0 ]; then
    error "Missing required environment variables:"
    for var in "${MISSING_VARS[@]}"; do
        echo "  - $var"
    done
    echo ""
    info "Set environment variables using:"
    echo "  export AZURE_STORAGE_CONNECTION_STRING=\"...\""
    echo "  export COSMOS_ENDPOINT=\"https://...\""
    echo "  export COSMOS_KEY=\"...\""
    exit 1
fi

success "All required environment variables are set"

# Check dependencies
info "Checking Python dependencies..."
REQUIRED_PACKAGES=("azure-storage-blob" "azure-cosmos")
MISSING_PACKAGES=()

for package in "${REQUIRED_PACKAGES[@]}"; do
    package_import=$(echo "$package" | tr '-' '_')
    if ! python3 -c "import $package_import" 2>/dev/null; then
        MISSING_PACKAGES+=("$package")
    fi
done

if [ ${#MISSING_PACKAGES[@]} -gt 0 ]; then
    warning "Missing required packages: ${MISSING_PACKAGES[*]}"
    info "Installing missing packages..."
    for package in "${MISSING_PACKAGES[@]}"; do
        info "Installing $package..."
        python3 -m pip install "$package"
        if [ $? -ne 0 ]; then
            error "Failed to install $package"
            exit 1
        fi
    done
    success "All dependencies installed"
else
    success "All dependencies are installed"
fi

# Build command
CMD=(
    python3
    "$SCRIPT_PATH"
    --blob-container "$BLOB_CONTAINER"
    --cosmos-database "$COSMOS_DATABASE"
    --cosmos-container "$COSMOS_CONTAINER"
    --partition-key "$PARTITION_KEY"
    --state-file "$STATE_FILE"
)

if [ -n "$BLOB_PREFIX" ]; then
    CMD+=(--blob-prefix "$BLOB_PREFIX")
fi

if [ -n "$FORCE_RELOAD" ]; then
    CMD+=("$FORCE_RELOAD")
fi

# Run the loader
echo ""
info "Starting Cosmos DB loader..."
echo "======================================================================"
echo ""

"${CMD[@]}"
EXIT_CODE=$?

echo ""
echo "======================================================================"

if [ $EXIT_CODE -eq 0 ]; then
    success "Loader completed successfully"
else
    error "Loader failed with exit code: $EXIT_CODE"
fi

exit $EXIT_CODE
