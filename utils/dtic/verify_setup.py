"""
Verify that the scraper environment is set up correctly.

This script checks:
1. Selenium is installed
2. Chrome/Chromium is available
3. WebDriver can be initialized
4. Can navigate to DTIC website
"""

import sys


def check_selenium():
    """Check if Selenium is installed."""
    print("\n1. Checking Selenium installation...")
    try:
        import selenium
        print(f"   ✓ Selenium {selenium.__version__} is installed")
        return True
    except ImportError:
        print("   ✗ Selenium is not installed")
        print("     Run: poetry add selenium")
        return False


def check_webdriver():
    """Check if WebDriver can be initialized."""
    print("\n2. Checking WebDriver initialization...")
    try:
        from selenium import webdriver
        from selenium.webdriver.chrome.options import Options
        
        options = Options()
        options.add_argument('--headless')
        options.add_argument('--no-sandbox')
        options.add_argument('--disable-dev-shm-usage')
        
        driver = webdriver.Chrome(options=options)
        print(f"   ✓ Chrome WebDriver initialized successfully")
        driver.quit()
        return True
        
    except Exception as e:
        print(f"   ✗ Failed to initialize WebDriver: {e}")
        print("     Make sure Chrome or Chromium is installed")
        print("     The WebDriver should be installed automatically by Selenium")
        return False


def check_dtic_access():
    """Check if DTIC website is accessible."""
    print("\n3. Checking DTIC website access...")
    try:
        from selenium import webdriver
        from selenium.webdriver.chrome.options import Options
        from selenium.webdriver.common.by import By
        from selenium.webdriver.support.ui import WebDriverWait
        from selenium.webdriver.support import expected_conditions as EC
        
        options = Options()
        options.add_argument('--headless')
        options.add_argument('--no-sandbox')
        options.add_argument('--disable-dev-shm-usage')
        
        driver = webdriver.Chrome(options=options)
        
        print("   Navigating to DTIC...")
        driver.get("https://dtic.dimensions.ai/discover/publication")
        
        # Wait for page to load
        WebDriverWait(driver, 15).until(
            EC.presence_of_element_located((By.TAG_NAME, "body"))
        )
        
        title = driver.title
        print(f"   ✓ Successfully loaded: {title}")
        
        # Try to find some common elements
        print("\n   Checking page structure...")
        
        # Get page source length as a simple check
        page_source = driver.page_source
        print(f"   Page source length: {len(page_source)} characters")
        
        # Check for common patterns
        if "publication" in page_source.lower():
            print("   ✓ Found 'publication' in page content")
        else:
            print("   ⚠ 'publication' not found in page content")
        
        # Try to find any links
        links = driver.find_elements(By.TAG_NAME, "a")
        print(f"   Found {len(links)} links on page")
        
        driver.quit()
        return True
        
    except Exception as e:
        print(f"   ✗ Error accessing DTIC: {e}")
        return False


def check_output_directory():
    """Check if we can write to the current directory."""
    print("\n4. Checking write permissions...")
    try:
        test_file = "test_write.tmp"
        with open(test_file, 'w') as f:
            f.write("test")
        
        import os
        os.remove(test_file)
        print("   ✓ Can write to current directory")
        return True
        
    except Exception as e:
        print(f"   ✗ Cannot write to current directory: {e}")
        return False


def main():
    """Run all checks."""
    print("=" * 70)
    print("DTIC Scraper Environment Verification")
    print("=" * 70)
    
    checks = [
        check_selenium,
        check_webdriver,
        check_dtic_access,
        check_output_directory
    ]
    
    results = []
    for check in checks:
        try:
            result = check()
            results.append(result)
        except Exception as e:
            print(f"   ✗ Unexpected error: {e}")
            results.append(False)
    
    print("\n" + "=" * 70)
    print("Summary")
    print("=" * 70)
    
    if all(results):
        print("\n✓ All checks passed! You're ready to start scraping.")
        print("\nTry running:")
        print("  python scraper.py --max-publications 5 --no-headless")
        return 0
    else:
        print("\n✗ Some checks failed. Please address the issues above.")
        print("\nCommon solutions:")
        print("  1. Install Selenium: poetry add selenium")
        print("  2. Install Chrome: https://www.google.com/chrome/")
        print("  3. Check your internet connection")
        return 1


if __name__ == "__main__":
    sys.exit(main())
