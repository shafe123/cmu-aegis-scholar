#!/bin/bash
# Quick Start - Author Scraper
# 
# This is a simple example showing how to run the author scraper
# for a subset of authors as a test.

# Set your Azure connection string
export AZURE_STORAGE_CONNECTION_STRING="YOUR_CONNECTION_STRING_HERE"

# Test with just one author and limited publications
echo "Testing with one author (max 5 publications)..."
poetry run python scrape_authors.py \
    --author-ids ur.012313314741.93 \
    --max-per-author 5 \
    --no-headless

# If the test succeeds, run the full scrape
if [ $? -eq 0 ]; then
    echo -e "\nTest successful! Running full scrape..."
    poetry run python scrape_authors.py
else
    echo -e "\nTest failed. Please check the error messages above."
    exit 1
fi
