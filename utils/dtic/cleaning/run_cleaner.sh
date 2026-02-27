#!/bin/bash
#
# Run the DTIC entity extractors (organizations, authors, topics, and works)
#
# Usage:
#   ./run_cleaner.sh            # Run all extractors in parallel
#   ./run_cleaner.sh orgs       # Run only organization extractor
#   ./run_cleaner.sh authors    # Run only author extractor
#   ./run_cleaner.sh topics     # Run only topic extractor
#   ./run_cleaner.sh works      # Run only work extractor
#

show_help() {
    echo "DTIC Entity Extractor Runner"
    echo ""
    echo "Usage:"
    echo "  ./run_cleaner.sh            # Run all extractors in parallel"
    echo "  ./run_cleaner.sh orgs       # Run only organization extractor"
    echo "  ./run_cleaner.sh authors    # Run only author extractor"
    echo "  ./run_cleaner.sh topics     # Run only topic extractor"
    echo "  ./run_cleaner.sh works      # Run only work extractor"
    echo "  ./run_cleaner.sh help       # Show this help"
    echo ""
    echo "Environment:"
    echo "  AZURE_STORAGE_CONNECTION_STRING must be set"
    exit 0
}

# Show help if requested
if [ "$1" = "help" ] || [ "$1" = "-h" ] || [ "$1" = "--help" ]; then
    show_help
fi

# Ensure we're in the correct directory
cd "$(dirname "$0")"

# Check for connection string
if [ -z "$AZURE_STORAGE_CONNECTION_STRING" ]; then
    echo "Error: AZURE_STORAGE_CONNECTION_STRING environment variable not set"
    echo "Please set it with: export AZURE_STORAGE_CONNECTION_STRING='your-connection-string'"
    exit 1
fi

# Determine which extractors to run
RUN_ORGS=false
RUN_AUTHORS=false
RUN_TOPICS=false
RUN_WORKS=false

if [ "$1" = "orgs" ]; then
    RUN_ORGS=true
elif [ "$1" = "authors" ]; then
    RUN_AUTHORS=true
elif [ "$1" = "topics" ]; then
    RUN_TOPICS=true
elif [ "$1" = "works" ]; then
    RUN_WORKS=true
else
    # Default: run all
    RUN_ORGS=true
    RUN_AUTHORS=true
    RUN_TOPICS=true
    RUN_WORKS=true
fi

# Display what we're running
echo "Starting DTIC entity extractors..."
if [ "$RUN_ORGS" = true ]; then
    echo "  - Organization extractor (clean_orgs.py)"
fi
if [ "$RUN_AUTHORS" = true ]; then
    echo "  - Author extractor (clean_authors.py)"
fi
if [ "$RUN_TOPICS" = true ]; then
    echo "  - Topic extractor (clean_topics.py)"
fi
if [ "$RUN_WORKS" = true ]; then
    echo "  - Work extractor (clean_works.py)"
fi

# Create log files for output
TIMESTAMP=$(date +%s)
ORG_LOG="logs/org_extractor_$TIMESTAMP.log"
AUTHOR_LOG="logs/author_extractor_$TIMESTAMP.log"
TOPIC_LOG="logs/topic_extractor_$TIMESTAMP.log"
WORK_LOG="logs/work_extractor_$TIMESTAMP.log"

# Run extractors as needed
ORG_PID=""
AUTHOR_PID=""
TOPIC_PID=""
WORK_PID=""

if [ "$RUN_ORGS" = true ]; then
    poetry run python clean_orgs.py > "$ORG_LOG" 2>&1 &
    ORG_PID=$!
fi

if [ "$RUN_AUTHORS" = true ]; then
    poetry run python clean_authors.py > "$AUTHOR_LOG" 2>&1 &
    AUTHOR_PID=$!
fi

if [ "$RUN_TOPICS" = true ]; then
    poetry run python clean_topics.py > "$TOPIC_LOG" 2>&1 &
    TOPIC_PID=$!
fi

if [ "$RUN_WORKS" = true ]; then
    poetry run python clean_works.py > "$WORK_LOG" 2>&1 &
    WORK_PID=$!
fi

echo ""
if [ -n "$ORG_PID" ] && [ -n "$AUTHOR_PID" ] && [ -n "$TOPIC_PID" ] && [ -n "$WORK_PID" ]; then
    echo "All extractors running in background..."
elif [ -n "$ORG_PID" ] || [ -n "$AUTHOR_PID" ] || [ -n "$TOPIC_PID" ] || [ -n "$WORK_PID" ]; then
    echo "Extractors running in background..."
else
    echo "Extractor running..."
fi

if [ -n "$ORG_PID" ]; then
    echo "  Organization extractor PID: $ORG_PID (log: $ORG_LOG)"
fi
if [ -n "$AUTHOR_PID" ]; then
    echo "  Author extractor PID: $AUTHOR_PID (log: $AUTHOR_LOG)"
fi
if [ -n "$TOPIC_PID" ]; then
    echo "  Topic extractor PID: $TOPIC_PID (log: $TOPIC_LOG)"
fi
if [ -n "$WORK_PID" ]; then
    echo "  Work extractor PID: $WORK_PID (log: $WORK_LOG)"
fi

echo "Waiting for completion..."
echo ""

# Wait for processes and capture exit codes
ORG_EXIT=0
AUTHOR_EXIT=0
TOPIC_EXIT=0
WORK_EXIT=0

if [ -n "$ORG_PID" ]; then
    wait $ORG_PID
    ORG_EXIT=$?
fi

if [ -n "$AUTHOR_PID" ]; then
    wait $AUTHOR_PID
    AUTHOR_EXIT=$?
fi

if [ -n "$TOPIC_PID" ]; then
    wait $TOPIC_PID
    TOPIC_EXIT=$?
fi

if [ -n "$WORK_PID" ]; then
    wait $WORK_PID
    WORK_EXIT=$?
fi

# Display results
if [ "$RUN_ORGS" = true ]; then
    echo "=== Organization Extractor Results ==="
    cat "$ORG_LOG"
    echo ""
fi

if [ "$RUN_AUTHORS" = true ]; then
    echo "=== Author Extractor Results ==="
    cat "$AUTHOR_LOG"
    echo ""
fi

if [ "$RUN_TOPICS" = true ]; then
    echo "=== Topic Extractor Results ==="
    cat "$TOPIC_LOG"
    echo ""
fi

if [ "$RUN_WORKS" = true ]; then
    echo "=== Work Extractor Results ==="
    cat "$WORK_LOG"
    echo ""
fi

# Show final status
echo "=== Final Status ==="
if [ "$RUN_ORGS" = true ]; then
    if [ $ORG_EXIT -eq 0 ]; then
        echo "✓ Organization extractor completed successfully"
    else
        echo "✗ Organization extractor failed (exit code: $ORG_EXIT)"
    fi
fi

if [ "$RUN_AUTHORS" = true ]; then
    if [ $AUTHOR_EXIT -eq 0 ]; then
        echo "✓ Author extractor completed successfully"
    else
        echo "✗ Author extractor failed (exit code: $AUTHOR_EXIT)"
    fi
fi

if [ "$RUN_TOPICS" = true ]; then
    if [ $TOPIC_EXIT -eq 0 ]; then
        echo "✓ Topic extractor completed successfully"
    else
        echo "✗ Topic extractor failed (exit code: $TOPIC_EXIT)"
    fi
fi

if [ "$RUN_WORKS" = true ]; then
    if [ $WORK_EXIT -eq 0 ]; then
        echo "✓ Work extractor completed successfully"
    else
        echo "✗ Work extractor failed (exit code: $WORK_EXIT)"
    fi
fi

# Exit with error if any extractor failed
if [ $ORG_EXIT -ne 0 ] || [ $AUTHOR_EXIT -ne 0 ] || [ $TOPIC_EXIT -ne 0 ] || [ $WORK_EXIT -ne 0 ]; then
    exit 1
fi

exit 0
