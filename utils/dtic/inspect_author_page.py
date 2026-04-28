"""
Temporary script to inspect JavaScript data on DTIC author page
"""

import json
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC


def extract_javascript_data(driver):
    """Extract JavaScript configuration data from the page"""
    try:
        # Try to extract the config object that Dimensions embeds
        script = """
        if (typeof config !== 'undefined') {
            return JSON.stringify(config);
        } else if (typeof window.config !== 'undefined') {
            return JSON.stringify(window.config);
        }
        return null;
        """
        result = driver.execute_script(script)
        if result:
            return json.loads(result)
    except Exception as e:
        print(f"Error extracting config: {e}")

    return None


def main():
    url = "https://dtic.dimensions.ai/discover/publication?search_mode=content&and_facet_researcher=ur.012313314741.93"

    # Setup Chrome options (same as scraper.py)
    chrome_options = Options()
    chrome_options.add_argument("--headless")
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")
    chrome_options.add_argument("--disable-blink-features=AutomationControlled")
    chrome_options.add_experimental_option("excludeSwitches", ["enable-automation"])
    chrome_options.add_experimental_option("useAutomationExtension", False)
    chrome_options.add_argument(
        "user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    )
    chrome_options.page_load_strategy = "eager"

    # Disable images for faster loading
    prefs = {
        "profile.managed_default_content_settings.images": 2,
        "profile.default_content_setting_values.notifications": 2,
    }
    chrome_options.add_experimental_option("prefs", prefs)

    # Initialize driver
    print(f"Loading page: {url}")
    driver = webdriver.Chrome(options=chrome_options)

    try:
        driver.get(url)

        # Wait for content to load
        print("Waiting for page content...")
        WebDriverWait(driver, 10).until(
            EC.presence_of_element_located((By.TAG_NAME, "body"))
        )

        # Wait a bit more for dynamic content to load
        import time

        time.sleep(5)

        # Extract JavaScript data
        print("\nExtracting JavaScript data...")
        js_data = extract_javascript_data(driver)

        # Also try to get search results from the page after they've loaded
        print("\nSearching for search results in page...")
        try:
            search_results_script = """
            // Try different places where search results might be stored
            if (typeof window.__NUXT__ !== 'undefined') {
                return JSON.stringify(window.__NUXT__);
            }
            if (typeof window.searchResults !== 'undefined') {
                return JSON.stringify(window.searchResults);
            }
            // Look for Vue/Nuxt store
            if (typeof window.$nuxt !== 'undefined' && window.$nuxt.$store) {
                return JSON.stringify(window.$nuxt.$store.state);
            }
            return null;
            """
            nuxt_data = driver.execute_script(search_results_script)
            if nuxt_data:
                try:
                    nuxt_obj = json.loads(nuxt_data)
                    with open("nuxt_data.json", "w", encoding="utf-8") as f:
                        json.dump(nuxt_obj, f, indent=2)
                    print("NUXT data saved to: nuxt_data.json")
                    # Check if there are results in the NUXT data
                    if isinstance(nuxt_obj, dict):
                        print(f"NUXT top-level keys: {list(nuxt_obj.keys())}")
                except Exception as e:
                    print(f"Error parsing NUXT data: {e}")
        except Exception as e:
            print(f"Error extracting NUXT data: {e}")

        # Check DOM for publication cards/links
        print("\nChecking DOM for publication elements...")
        try:
            # Try to find publication links in the DOM
            pub_links = driver.find_elements(
                By.CSS_SELECTOR, "a[href*='/details/publication']"
            )
            print(f"Found {len(pub_links)} publication links in DOM")

            if pub_links:
                print("\nFirst 5 publication URLs:")
                for i, link in enumerate(pub_links[:5]):
                    href = link.get_attribute("href")
                    text = link.text.strip()[:100]
                    print(f"  {i + 1}. {href}")
                    print(f"     Title: {text}")

        except Exception as e:
            print(f"Error checking DOM: {e}")

        # Try to find total results count and pagination
        print("\nLooking for pagination and total count...")
        try:
            # Search for elements that might contain total count
            count_script = """
            // Look for pagination or results count in various places
            let result = {};
            
            // Check for results count text in DOM
            let countElements = document.querySelectorAll('[class*="count"], [class*="result"], [class*="total"]');
            if (countElements.length > 0) {
                result.countElementsFound = countElements.length;
            }
            
            // Try to get info from page text
            let bodyText = document.body.innerText;
            let matches = bodyText.match(/\\d+[,\\d]*\\s+(results?|publications?|documents?)/gi);
            if (matches) {
                result.matches = matches;
            }
            
            // Look for pagination elements
            let paginationElements = document.querySelectorAll('[class*="pagination"], [class*="page"]');
            if (paginationElements.length > 0) {
                result.paginationElementsFound = paginationElements.length;
            }
            
            return JSON.stringify(result);
            """
            count_info = driver.execute_script(count_script)
            if count_info:
                count_data = json.loads(count_info)
                print(f"Count/Pagination info: {json.dumps(count_data, indent=2)}")

        except Exception as e:
            print(f"Error getting count info: {e}")

        if js_data:
            # Save full data to a file
            output_file = "author_page_data.json"
            with open(output_file, "w", encoding="utf-8") as f:
                json.dump(js_data, f, indent=2)
            print(f"\nFull data saved to: {output_file}")

            # Print specific keys we're interested in
            print("\n=== Top-level keys available ===")
            print(list(js_data.keys()))

            # Check for search section
            if "search" in js_data:
                print("\n=== Search section keys ===")
                search_data = js_data["search"]
                print(list(search_data.keys()))

                # Save search section separately
                with open("author_search_data.json", "w", encoding="utf-8") as f:
                    json.dump(search_data, f, indent=2)
                print("Search section saved to: author_search_data.json")

                # Check for results
                if "results" in search_data:
                    results = search_data["results"]
                    print("\n=== Results information ===")
                    print(f"Type: {type(results)}")
                    if isinstance(results, dict):
                        print(f"Keys: {list(results.keys())}")
                        if "docs" in results:
                            docs = results["docs"]
                            print(f"Number of docs: {len(docs)}")
                            if docs:
                                print(f"\nFirst doc keys: {list(docs[0].keys())}")
                                print(
                                    f"\nFirst doc example (truncated): {json.dumps(docs[0], indent=2)[:1000]}"
                                )
                    elif isinstance(results, list):
                        print(f"Number of results: {len(results)}")
                        if results:
                            print(f"First result keys: {list(results[0].keys())}")

                # Check pagination
                if "pagination" in search_data:
                    print("\n=== Pagination info ===")
                    print(json.dumps(search_data["pagination"], indent=2))

        else:
            print("No JavaScript config data found on page")
            print("\nTrying alternative extraction methods...")

            # Try to find any embedded JSON or data
            scripts = driver.find_elements(By.TAG_NAME, "script")
            print(f"Found {len(scripts)} script tags")

    finally:
        driver.quit()


if __name__ == "__main__":
    main()
