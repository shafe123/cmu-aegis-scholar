# Quick Start - Author Scraper
# 
# This is a simple example showing how to run the author scraper
# for a subset of authors as a test.

# Test with just one author and limited publications
Write-Host "Testing with one author (max 5 publications)..." -ForegroundColor Cyan
poetry run python scrape_authors.py `
    --author-ids ur.012313314741.93 `
    --max-per-author 5 `
    --no-headless

# If the test succeeds, run the full scrape
Write-Host "`nTest successful! Running full scrape..." -ForegroundColor Green
poetry run python scrape_authors.py
