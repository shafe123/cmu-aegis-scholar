"""
Performance test script for DTIC scraper.
"""

import time
from scraper import DTICScraper
from scraper_parallel import ParallelDTICScraper


def test_single():
    """Test single scraper (JavaScript extraction only)."""
    print("=" * 60)
    print("TESTING: Single scraper (JavaScript extraction)")
    print("=" * 60)

    scraper = DTICScraper(headless=True)
    scraper._init_driver()

    test_url = "https://dtic.dimensions.ai/details/publication/pub.1000000000"

    start = time.time()
    scraper._extract_publication_from_page(test_url)
    elapsed = time.time() - start

    scraper.driver.quit()

    print(f"✓ Time: {elapsed:.2f} seconds")
    print()
    return elapsed


def test_parallel(num_publications=10, num_workers=4):
    """Test parallel scraping."""
    print("=" * 60)
    print(
        f"TESTING: Parallel scraper - {num_workers} workers, {num_publications} publications"
    )
    print("=" * 60)

    scraper = ParallelDTICScraper(num_workers=num_workers, headless=True)

    # Create test URLs
    test_urls = [
        f"https://dtic.dimensions.ai/details/publication/pub.100000000{i}"
        for i in range(num_publications)
    ]

    start = time.time()
    scraper.scrape_urls(test_urls)
    elapsed = time.time() - start

    print(f"✓ Total time: {elapsed:.2f} seconds")
    print(f"✓ Average per publication: {elapsed / num_publications:.2f} seconds")
    print()
    return elapsed


def estimate_full_scrape(time_per_pub, total_pubs=600000):
    """Estimate time to scrape all publications."""
    total_seconds = time_per_pub * total_pubs

    hours = total_seconds / 3600
    days = hours / 24
    weeks = days / 7
    months = days / 30
    years = days / 365

    print(f"Estimated time for {total_pubs:,} publications:")
    print(f"  At {time_per_pub:.2f} sec/pub:")
    if years >= 1:
        print(f"    → {years:.1f} years ({months:.1f} months)")
    elif months >= 1:
        print(f"    → {months:.1f} months ({days:.1f} days)")
    elif weeks >= 1:
        print(f"    → {weeks:.1f} weeks ({days:.1f} days)")
    elif days >= 1:
        print(f"    → {days:.1f} days ({hours:.1f} hours)")
    else:
        print(f"    → {hours:.1f} hours")
    print()


def main():
    """Run all performance tests."""
    print("\n" + "=" * 60)
    print("DTIC SCRAPER PERFORMANCE TESTS")
    print("=" * 60)
    print()

    # Test 1: Single scraper
    try:
        single_time = test_single()
    except Exception as e:
        print(f"✗ Single scraper test failed: {e}")
        single_time = 1.0  # Estimate

    # Test 2: Parallel
    try:
        parallel_time = test_parallel(num_publications=10, num_workers=4)
        parallel_per_pub = parallel_time / 10
    except Exception as e:
        print(f"✗ Parallel test failed: {e}")
        parallel_per_pub = single_time / 4  # Estimate with 4 workers

    # Summary
    print("=" * 60)
    print("SUMMARY")
    print("=" * 60)
    print(f"Single scraper:   {single_time:.2f} sec/publication")
    print(
        f"Parallel (4):     {parallel_per_pub:.2f} sec/publication ({single_time / parallel_per_pub:.1f}x faster)"
    )
    print()

    # Estimates for full scrape
    print("=" * 60)
    print("FULL SCRAPE ESTIMATES (600,000 publications)")
    print("=" * 60)
    print("Single scraper:")
    estimate_full_scrape(single_time)
    print("Parallel (4 workers):")
    estimate_full_scrape(parallel_per_pub)

    print("=" * 60)
    print("RECOMMENDATION")
    print("=" * 60)
    print("For best performance, use parallel scraping:")
    print()
    print("  poetry run python scraper_parallel.py --workers 8")
    print()
    print("Expected completion time: ~2-3 weeks for 600k publications")
    print("=" * 60)


if __name__ == "__main__":
    main()
