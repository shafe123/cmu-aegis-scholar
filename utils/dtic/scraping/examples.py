"""
Example usage of the DTIC scraper.

This script demonstrates how to use the scraper programmatically.
"""

from scraper import DTICScraper
import logging

# Configure logging to see what's happening
logging.basicConfig(level=logging.INFO)


def example_basic_scrape():
    """Basic scraping example."""
    print("=" * 60)
    print("Basic Scraping Example")
    print("=" * 60)

    scraper = DTICScraper(
        output_dir="my_publications",
        headless=True,  # Run without opening browser window
        state_file="my_state.json",
    )

    # Scrape first 5 publications
    scraper.scrape(max_publications=5)

    print("\nScraping completed! Check my_publications/ directory for results.")


def example_resume_scrape():
    """Example of resuming a scrape."""
    print("=" * 60)
    print("Resume Scraping Example")
    print("=" * 60)

    scraper = DTICScraper(
        output_dir="my_publications", headless=True, state_file="my_state.json"
    )

    # Resume from where we left off
    scraper.resume(max_publications=10)

    print("\nResume completed!")


def example_visible_browser():
    """Example with visible browser window (useful for debugging)."""
    print("=" * 60)
    print("Visible Browser Example")
    print("=" * 60)

    scraper = DTICScraper(
        output_dir="debug_publications",
        headless=False,  # Show browser window
        state_file="debug_state.json",
    )

    # Scrape just 2 publications so you can watch
    scraper.scrape(max_publications=2)

    print("\nDebug scraping completed!")


def example_custom_rate_limiting():
    """Example with custom rate limiting."""
    print("=" * 60)
    print("Custom Rate Limiting Example")
    print("=" * 60)

    scraper = DTICScraper(
        output_dir="slow_scrape", headless=True, state_file="slow_state.json"
    )

    # Adjust rate limiting for slower, more cautious scraping
    from scraper import RateLimiter

    scraper.rate_limiter = RateLimiter(
        min_delay=5.0,  # Minimum 5 seconds between requests
        max_delay=15.0,  # Maximum 15 seconds
        base_backoff=3.0,  # Slower backoff
    )

    scraper.scrape(max_publications=5)

    print("\nSlow scraping completed!")


if __name__ == "__main__":
    import sys

    examples = {
        "1": ("Basic scrape", example_basic_scrape),
        "2": ("Resume scrape", example_resume_scrape),
        "3": ("Visible browser", example_visible_browser),
        "4": ("Custom rate limiting", example_custom_rate_limiting),
    }

    print("\nDTIC Scraper Examples")
    print("=" * 60)
    print("\nAvailable examples:")
    for key, (description, _) in examples.items():
        print(f"  {key}. {description}")
    print("  q. Quit")

    if len(sys.argv) > 1:
        choice = sys.argv[1]
    else:
        choice = input("\nSelect an example (1-4, or q to quit): ").strip()

    if choice.lower() == "q":
        print("Goodbye!")
        sys.exit(0)

    if choice in examples:
        _, example_func = examples[choice]
        example_func()
    else:
        print(f"Invalid choice: {choice}")
        sys.exit(1)
