"""
DTIC Author-Specific Scraper

Scrapes publications for specific author IDs from DTIC and uploads to Azure Blob Storage.
Uses the same extraction methods as the main scraper but targets author-filtered search pages.
"""

import json
import logging
import sys
import time
import os
from pathlib import Path
from typing import Dict, List, Optional
from datetime import datetime
from dataclasses import dataclass, asdict

from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import (
    TimeoutException, 
    NoSuchElementException, 
    StaleElementReferenceException
)
from selenium.webdriver.chrome.options import Options
from azure.storage.blob import BlobServiceClient


# Import classes from scraper module
import sys
sys.path.append(str(Path(__file__).parent))
from scraper import (
    Publication, 
    Author, 
    Organization, 
    StateManager, 
    RateLimiter,
    load_config,
    extract_grid_id_from_affiliation
)


# Generate timestamped log filename
_log_timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
_logs_dir = Path("logs")
_logs_dir.mkdir(exist_ok=True)
_log_filename = _logs_dir / f"{_log_timestamp}_author_scraper.log"

# Configure logging with UTF-8 encoding
file_handler = logging.FileHandler(_log_filename, encoding='utf-8')
stream_handler = logging.StreamHandler(sys.stdout)
stream_handler.stream = open(sys.stdout.fileno(), mode='w', encoding='utf-8', buffering=1)

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[file_handler, stream_handler]
)
logger = logging.getLogger(__name__)

# Quiet Azure SDK loggers
logging.getLogger('azure').setLevel(logging.WARNING)
logging.getLogger('azure.core.pipeline.policies.http_logging_policy').setLevel(logging.WARNING)


class AzureBlobUploader:
    """Simplified Azure Blob uploader for direct integration."""
    
    def __init__(self, connection_string: str, container_name: str = "raw", blob_prefix: str = "dtic/works/"):
        self.blob_prefix = blob_prefix
        self.blob_service_client = BlobServiceClient.from_connection_string(connection_string)
        self.container_client = self.blob_service_client.get_container_client(container_name)
        
        # Create container if it doesn't exist
        try:
            self.container_client.create_container()
            logger.info(f"Created new container: {container_name}")
        except Exception:
            pass  # Container already exists
        
        logger.debug(f"Connected to Azure Blob Storage container: {container_name}")
    
    def upload_publication(self, publication: Publication) -> bool:
        """Upload a publication directly to Azure Blob Storage."""
        try:
            filename = f"{publication.publication_id}.json"
            blob_name = f"{self.blob_prefix}{filename}"
            
            # Convert to JSON
            json_data = json.dumps(asdict(publication), indent=2, ensure_ascii=False)
            
            # Upload to blob
            blob_client = self.container_client.get_blob_client(blob_name)
            blob_client.upload_blob(json_data.encode('utf-8'), overwrite=True)
            
            logger.info(f"[OK] Uploaded to Azure: {blob_name}")
            return True
            
        except Exception as e:
            logger.error(f"[FAIL] Failed to upload {publication.publication_id}: {e}")
            return False


class AuthorScraper:
    """Scraper for author-specific publications on DTIC."""
    
    def __init__(self, 
                 azure_connection_string: str,
                 output_dir: str = "dtic_publications",
                 headless: bool = True,
                 state_file: str = "author_scraper_state.json",
                 config_file: str = "config.json"):
        # Load configuration
        self.config = load_config(config_file)
        
        # Setup output directory
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        logger.info(f"Output directory: {self.output_dir.absolute()}")
        
        self.headless = self.config.get('scraper', {}).get('headless', headless)
        self.driver: Optional[webdriver.Chrome] = None
        self.state_manager = StateManager(state_file)
        
        # Initialize rate limiter with config values
        rate_config = self.config.get('rate_limiting', {})
        self.rate_limiter = RateLimiter(
            min_delay=rate_config.get('min_delay', 2.0),
            max_delay=rate_config.get('max_delay', 10.0),
            base_backoff=rate_config.get('base_backoff', 2.0)
        )
        
        self.base_url = "https://dtic.dimensions.ai/discover/publication"
        self.selectors = self.config.get('selectors', {})
        
        # Initialize Azure uploader
        self.azure_uploader = AzureBlobUploader(azure_connection_string)
        logger.debug("Azure Blob Storage uploader initialized")
    
    def _init_driver(self):
        """Initialize Selenium WebDriver with appropriate options."""
        chrome_options = Options()
        
        if self.headless:
            chrome_options.add_argument('--headless')
        
        # Standard options for better stability
        chrome_options.add_argument('--no-sandbox')
        chrome_options.add_argument('--disable-dev-shm-usage')
        chrome_options.add_argument('--disable-blink-features=AutomationControlled')
        chrome_options.add_experimental_option("excludeSwitches", ["enable-automation"])
        chrome_options.add_experimental_option('useAutomationExtension', False)
        
        # User agent to avoid detection
        chrome_options.add_argument('user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36')
        
        # Use 'eager' page load strategy
        chrome_options.page_load_strategy = 'eager'
        
        # Disable images for faster loading
        prefs = {
            "profile.managed_default_content_settings.images": 2,
            "profile.default_content_setting_values.notifications": 2,
        }
        chrome_options.add_experimental_option("prefs", prefs)
        
        logger.debug("Initializing Chrome WebDriver...")
        self.driver = webdriver.Chrome(options=chrome_options)
        self.driver.set_page_load_timeout(30)
        logger.debug("WebDriver initialized successfully")
    
    def _extract_javascript_data(self):
        """Extract data from the page's JavaScript config."""
        try:
            # DTIC stores publication data in config.details.document
            data = self.driver.execute_script("""
                // Try DTIC-specific location first: config.details.document
                if (typeof config !== 'undefined' && 
                    config.details && 
                    config.details.document) {
                    console.log('Found data in config.details.document');
                    return config.details.document;
                }
                
                // Try on window object
                if (typeof window.config !== 'undefined' && 
                    window.config.details && 
                    window.config.details.document) {
                    console.log('Found data in window.config.details.document');
                    return window.config.details.document;
                }
                
                // Fallback to other common patterns
                if (typeof __NUXT__ !== 'undefined') {
                    console.log('Found __NUXT__ data');
                    return __NUXT__;
                }
                
                if (typeof window.__NUXT__ !== 'undefined') {
                    console.log('Found window.__NUXT__ data');
                    return window.__NUXT__;
                }
                
                // Try other alternatives
                const alternatives = ['__INITIAL_STATE__', '__DATA__', '__NEXT_DATA__'];
                for (const alt of alternatives) {
                    if (typeof window[alt] !== 'undefined') {
                        console.log('Found data in ' + alt);
                        return window[alt];
                    }
                }
                
                console.log('No JavaScript data found');
                return null;
            """)
            
            if data:
                logger.debug(f"Extracted JavaScript data object with {len(str(data))} chars")
                logger.debug(f"Data keys: {list(data.keys()) if isinstance(data, dict) else 'not a dict'}")
                return data
            else:
                logger.warning("JavaScript data extraction returned null")
            
        except Exception as e:
            logger.error(f"Could not extract JavaScript data: {e}")
        
        return None
    
    def _extract_publication_from_js(self, js_data: Dict, pub_url: str) -> Optional[Publication]:
        """Extract publication data from JavaScript config."""
        try:
            # Extract publication ID from URL
            pub_id = pub_url.split('/')[-1].split('?')[0]
            
            # Log available keys for debugging
            if isinstance(js_data, dict):
                logger.debug(f"JS data top-level keys: {list(js_data.keys())}")
            
            # Extract from DTIC structure: page_structure
            page_structure = js_data.get('page_structure', {})
            
            # Title from publication-header
            title = None
            pub_header = page_structure.get('publication-header', {}).get('data', {})
            if pub_header:
                title = pub_header.get('title')
            
            # Abstract from abstract section (optional - may not exist)
            abstract = None
            abstract_section = page_structure.get('abstract', {}).get('data', {})
            if abstract_section:
                abstract = abstract_section.get('abstract')
            
            # DOI from custom-meta
            doi = None
            custom_meta = page_structure.get('custom-meta', {}).get('data', {})
            if custom_meta:
                doi = custom_meta.get('doi')
            
            # Document type from publication-header
            document_type = None
            if pub_header:
                document_type = pub_header.get('pub_class') or pub_header.get('pub_class_id')
            
            # Publication date from metadata
            publication_date = None
            metadata = pub_header.get('metadata', {}).get('data', {})
            if metadata:
                publication_date = metadata.get('pub_date')
            
            # Extract citations - default to 0
            citations_count = 0
            
            # Extract keywords from Fields of Research (ANZSRC 2020)
            keywords = self._extract_fields_of_research(js_data)
            
            # Extract authors from page_structure.authors.data.affiliations_details
            authors = []
            authors_section = page_structure.get('authors', {}).get('data', {})
            if authors_section:
                affiliations_details = authors_section.get('affiliations_details', [])
                for author_data in affiliations_details:
                    if isinstance(author_data, dict):
                        first_name = author_data.get('first_name', '')
                        last_name = author_data.get('last_name', '')
                        name = f"{first_name} {last_name}".strip()
                        
                        researcher_id = author_data.get('researcher_id')
                        orcid_list = author_data.get('orcid', [])
                        if orcid_list and isinstance(orcid_list, list) and len(orcid_list) > 0:
                            if not researcher_id:
                                researcher_id = orcid_list[0]
                        
                        # Extract affiliation names and GRID IDs for this author
                        affil_list = []
                        affil_details = []
                        author_org_ids = []
                        seen_author_org_ids = set()
                        for affil in author_data.get('affiliations', []):
                            if isinstance(affil, dict):
                                affil_name = affil.get('name')
                                grid_id = extract_grid_id_from_affiliation(affil)
                                country = affil.get('country')
                                if affil_name:
                                    affil_list.append(affil_name)
                                    affil_details.append({
                                        'name': affil_name,
                                        'org_id': grid_id,
                                        'country': country
                                    })
                                if grid_id and grid_id not in seen_author_org_ids:
                                    author_org_ids.append(grid_id)
                                    seen_author_org_ids.add(grid_id)
                        
                        if name:
                            authors.append(Author(
                                name=name,
                                researcher_id=researcher_id,
                                affiliations=affil_list,
                                org_ids=author_org_ids,
                                affiliation_details=affil_details
                            ))
            
            logger.debug(f"Extracted {len(authors)} authors from JS")
            
            # Extract organizations from author affiliations
            organizations = []
            if authors_section:
                affiliations_details = authors_section.get('affiliations_details', [])
                seen_orgs = set()
                for author_data in affiliations_details:
                    if isinstance(author_data, dict):
                        for affil in author_data.get('affiliations', []):
                            if isinstance(affil, dict):
                                org_id = extract_grid_id_from_affiliation(affil)
                                org_name = affil.get('name')
                                if org_name and org_id and org_id not in seen_orgs:
                                    organizations.append(Organization(
                                        name=org_name,
                                        org_id=org_id,
                                        country=affil.get('country'),
                                        type=None
                                    ))
                                    seen_orgs.add(org_id)
                                elif org_name and not org_id:
                                    # Organization without ID (raw affiliation)
                                    org_key = org_name.lower()
                                    if org_key not in seen_orgs:
                                        organizations.append(Organization(
                                            name=org_name,
                                            org_id=None,
                                            country=affil.get('country'),
                                            type=None
                                        ))
                                        seen_orgs.add(org_key)
            
            logger.debug(f"Extracted {len(organizations)} organizations from JS")
            
            # Parse publication date if needed
            if publication_date:
                publication_date = self._parse_publication_date(str(publication_date))
            
            publication = Publication(
                publication_id=pub_id,
                title=title or "Unknown Title",
                abstract=abstract,
                authors=[asdict(a) for a in authors],
                organizations=[asdict(o) for o in organizations],
                publication_date=publication_date,
                url=pub_url,
                doi=doi,
                document_type=document_type,
                keywords=keywords,
                citations_count=citations_count
            )
            
            logger.info(f"[JS] Extracted publication: {title[:50] if title else pub_id}...")
            return publication
            
        except Exception as e:
            logger.error(f"Error in JS extraction for {pub_url}: {e}")
            return None
    
    def _extract_fields_of_research(self, js_data: Dict) -> List[str]:
        """Extract Fields of Research (ANZSRC 2020) from page structure."""
        keywords = []
        
        try:
            # Get categories from page_structure
            page_structure = js_data.get('page_structure', {})
            categories = page_structure.get('categories', {})
            
            # Look for categories-for entity
            entities = categories.get('entities', [])
            
            for entity in entities:
                if isinstance(entity, dict) and entity.get('key') == 'categories-for':
                    navigation = entity.get('navigation', {})
                    json_path = navigation.get('json')
                    if json_path:
                        keywords.append(json_path)
                        logger.debug(f"Found Fields of Research path: {json_path}")
                    break
        
        except Exception as e:
            logger.debug(f"Error extracting Fields of Research path: {e}")
        
        return keywords
    
    def _parse_publication_date(self, date_str: Optional[str]) -> Optional[str]:
        """Parse and normalize publication date."""
        if not date_str:
            return None
        
        try:
            import re
            date_str = date_str.strip()
            
            # Match "Month Year" format (e.g., "September 2026")
            month_year_match = re.match(r'^([A-Za-z]+)\s+(\d{4})$', date_str)
            if month_year_match:
                month, year = month_year_match.groups()
                return f"1 {month} {year}"
            
            # Match "Day Month Year" format - return as is
            day_month_year_match = re.match(r'^(\d{1,2})\s+([A-Za-z]+)\s+(\d{4})$', date_str)
            if day_month_year_match:
                return date_str
            
            # Match "YYYY-MM-DD" format
            iso_match = re.match(r'^(\d{4})-(\d{2})-(\d{2})$', date_str)
            if iso_match:
                return date_str
            
            # Return raw string if no pattern matches
            return date_str
            
        except Exception as e:
            logger.debug(f"Error parsing date '{date_str}': {e}")
            return date_str
    
    def _extract_publication_from_page(self, pub_url: str) -> Optional[Publication]:
        """Navigate to publication page and extract data."""
        try:
            # Rate limit before page load
            self.rate_limiter.wait()
            
            # Open new tab using JavaScript (blank first)
            self.driver.execute_script("window.open('about:blank', '_blank');")
            
            # Switch to the new tab
            all_windows = self.driver.window_handles
            new_tab = [w for w in all_windows if w != self.main_window][0]
            self.driver.switch_to.window(new_tab)
            
            # Navigate to the URL
            logger.debug(f"Loading publication: {pub_url}")
            self.driver.get(pub_url)
            
            # Wait for JavaScript to execute and page to be ready
            try:
                WebDriverWait(self.driver, 5).until(
                    lambda d: d.execute_script("return document.readyState") == "complete"
                )
                logger.debug("Page ready state: complete")
            except TimeoutException:
                logger.warning("Timeout waiting for page readyState")
            
            # Extract JavaScript data
            js_data = self._extract_javascript_data()
            
            publication = None
            if js_data:
                publication = self._extract_publication_from_js(js_data, pub_url)
                if publication:
                    logger.info(f"[OK] Extracted from JS: {publication.publication_id}")
                else:
                    logger.warning("Failed to extract publication from JS data")
            else:
                logger.warning(f"No JavaScript data found for {pub_url}")
            
            # Close tab and switch back
            self.driver.close()
            self.driver.switch_to.window(self.main_window)
            
            return publication
            
        except Exception as e:
            logger.error(f"Error extracting publication from {pub_url}: {e}")
            # Try to recover by closing tab and switching back
            try:
                if self.driver.current_window_handle != self.main_window:
                    self.driver.close()
                    self.driver.switch_to.window(self.main_window)
            except:
                pass
            return None
    
    def _get_publication_links(self) -> List[str]:
        """Extract publication links from the current search results page."""
        links = []
        
        try:
            # Wait for publication links to appear
            wait = WebDriverWait(self.driver, 10)
            wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, "a[href*='/publication/']")))
            
            # Find all publication links
            elements = self.driver.find_elements(By.CSS_SELECTOR, "a[href*='/publication/']")
            
            for element in elements:
                try:
                    href = element.get_attribute('href')
                    if href and ('/publication/pub.' in href or '/publication/' in href.rstrip('/')):
                        if href not in links:
                            links.append(href)
                except StaleElementReferenceException:
                    continue
            
            logger.debug(f"Found {len(links)} publication links")
            
        except TimeoutException:
            logger.warning("Timeout waiting for publication links")
        except Exception as e:
            logger.error(f"Error getting publication links: {e}")
        
        return links
    
    def _scroll_and_load_more(self) -> bool:
        """Scroll down to trigger infinite scroll and load more publications."""
        try:
            # Get current page height
            last_height = self.driver.execute_script("return document.body.scrollHeight")
            
            # Scroll to bottom
            self.driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
            
            # Wait for new content to load
            time.sleep(1)
            self.rate_limiter.wait()
            
            # Get new page height
            new_height = self.driver.execute_script("return document.body.scrollHeight")
            
            # Check if new content was loaded
            if new_height > last_height:
                logger.info("Loaded more publications via infinite scroll")
                return True
            else:
                logger.info("Reached end of infinite scroll")
                return False
            
        except Exception as e:
            logger.error(f"Error during infinite scroll: {e}")
            return False
    
    def _save_publication_local(self, publication: Publication):
        """Save publication to local JSON file."""
        try:
            filename = f"{publication.publication_id}.json"
            filepath = self.output_dir / filename
            
            with open(filepath, 'w', encoding='utf-8') as f:
                json.dump(asdict(publication), f, indent=2, ensure_ascii=False)
            
            logger.debug(f"Saved locally: {publication.publication_id}")
        except Exception as e:
            logger.error(f"Error saving publication locally: {e}")
    
    def scrape_author(self, author_id: str, max_publications: Optional[int] = None):
        """
        Scrape all publications for a specific author.
        
        Args:
            author_id: Author's researcher ID (e.g., ur.012313314741.93)
            max_publications: Maximum number of publications to scrape (None for all)
        """
        logger.info(f"{'='*80}")
        logger.info(f"Starting scrape for author: {author_id}")
        logger.info(f"{'='*80}")
        
        try:
            if not self.driver:
                self._init_driver()
            
            # Build author-filtered URL
            url = f"{self.base_url}?search_mode=content&and_facet_researcher={author_id}"
            
            # Navigate to URL
            logger.info(f"Navigating to {url}")
            self.driver.get(url)
            self.rate_limiter.wait()
            
            # Store the main window handle
            self.main_window = self.driver.current_window_handle
            
            # Track progress
            author_processed = 0
            author_scraped = 0
            author_uploaded = 0
            seen_links = set()
            
            logger.info("Starting publication extraction...")
            
            while True:
                # Get publication links currently visible
                pub_links = self._get_publication_links()
                
                if not pub_links:
                    logger.warning("No publication links found")
                    break
                
                # Find new links
                new_links = [link for link in pub_links if link not in seen_links]
                seen_links.update(new_links)
                
                if new_links:
                    logger.info(f"Found {len(new_links)} new publication links (total seen: {len(seen_links)})")
                
                # Process the new links
                for link in new_links:
                    pub_id = link.split('/')[-1].split('?')[0]
                    
                    # Check if already scraped
                    if self.state_manager.is_scraped(pub_id):
                        logger.debug(f"Skipping already scraped: {pub_id}")
                        author_processed += 1
                        continue
                    
                    # Check if we've hit the limit
                    if max_publications and author_processed >= max_publications:
                        logger.info(f"Reached publication limit for {author_id}: {max_publications}")
                        break
                    
                    try:
                        logger.info(f"Processing publication {author_processed + 1}: {pub_id}")
                        
                        # Extract publication data
                        publication = self._extract_publication_from_page(link)
                        
                        if publication:
                            # Save locally
                            self._save_publication_local(publication)
                            
                            # Upload to Azure
                            if self.azure_uploader.upload_publication(publication):
                                author_uploaded += 1
                            
                            # Mark as scraped
                            self.state_manager.mark_scraped(pub_id)
                            author_processed += 1
                            author_scraped += 1
                            
                            self.rate_limiter.reset()
                            logger.info(f"[OK] Author {author_id}: {author_processed} processed, {author_scraped} scraped, {author_uploaded} uploaded")
                        else:
                            logger.warning(f"[SKIP] Failed to extract: {pub_id}")
                            self.rate_limiter.backoff()
                        
                    except Exception as e:
                        logger.error(f"Error processing {pub_id}: {e}")
                        self.rate_limiter.backoff()
                
                # Check if we've hit the limit
                if max_publications and author_processed >= max_publications:
                    break
                
                # Try to scroll and load more
                if not self._scroll_and_load_more():
                    logger.info("No more publications to load")
                    break
            
            logger.info(f"{'='*80}")
            logger.info(f"Author {author_id} complete:")
            logger.info(f"  Processed: {author_processed}")
            logger.info(f"  Newly scraped: {author_scraped}")
            logger.info(f"  Uploaded to Azure: {author_uploaded}")
            logger.info(f"{'='*80}")
            
        except Exception as e:
            logger.error(f"Error scraping author {author_id}: {e}")
    
    def scrape_multiple_authors(self, author_ids: List[str], max_publications_per_author: Optional[int] = None):
        """
        Scrape publications for multiple authors.
        
        Args:
            author_ids: List of author researcher IDs
            max_publications_per_author: Maximum publications per author (None for all)
        """
        logger.info(f"{'='*80}")
        logger.info(f"Starting multi-author scrape")
        logger.info(f"Total authors: {len(author_ids)}")
        logger.info(f"{'='*80}")
        
        total_processed = 0
        total_scraped = 0
        
        for idx, author_id in enumerate(author_ids, 1):
            logger.info(f"\n\nAuthor {idx}/{len(author_ids)}: {author_id}")
            
            try:
                self.scrape_author(author_id, max_publications=max_publications_per_author)
            except Exception as e:
                logger.error(f"Failed to scrape author {author_id}: {e}")
                continue
        
        logger.info(f"\n{'='*80}")
        logger.info(f"Multi-author scrape completed!")
        logger.info(f"Total authors processed: {len(author_ids)}")
        logger.info(f"{'='*80}")
    
    def close(self):
        """Clean up resources."""
        if self.driver:
            try:
                self.driver.quit()
                logger.info("WebDriver closed")
            except Exception as e:
                logger.error(f"Error closing WebDriver: {e}")


def main():
    """Main entry point for author scraper."""
    import argparse
    
    # List of author IDs to scrape
    DEFAULT_AUTHOR_IDS = [
        "ur.012313314741.93",
        "ur.015064057315.18",
        "ur.015627215165.71",
        "ur.016406327051.56",
        "ur.014452423664.19",
        "ur.012372653735.21",
        "ur.013062772232.30",
        "ur.01213120542.58",
        "ur.014541512746.21",
        "ur.01033404537.13",
        "ur.01220414055.82",
        "ur.012401467325.50",
        "ur.012065075654.47",
        "ur.015137513356.27",
        "ur.016610110700.09",
        "ur.016161161765.09",
        "ur.07511027635.48",
        "ur.011555712101.53",
        "ur.014361216414.52",
        "ur.014753037012.98",
        "ur.013323061215.08",
        "ur.01341474713.23",
        "ur.01017555417.25",
        "ur.0725745110.07",
        "ur.011054365124.22",
        "ur.0715732366.93",
        "ur.01047264435.23",
        "ur.015527265674.84",
        "ur.01042261017.84",
        "ur.01202401101.33",
        "ur.011703135307.28",
        "ur.011727670435.40",
    ]
    
    parser = argparse.ArgumentParser(description="DTIC Author-Specific Publication Scraper")
    parser.add_argument('--connection-string', '-c',
                      help='Azure Storage connection string (or set AZURE_STORAGE_CONNECTION_STRING env var)')
    parser.add_argument('--output-dir', '-o', default='dtic_publications',
                      help='Output directory path (default: dtic_publications)')
    parser.add_argument('--state', '-s', default='author_scraper_state.json',
                      help='State file path (default: author_scraper_state.json)')
    parser.add_argument('--config', default='config.json',
                      help='Config file path (default: config.json)')
    parser.add_argument('--max-per-author', '-m', type=int, default=None,
                      help='Maximum publications per author (default: all)')
    parser.add_argument('--headless', action='store_true', default=True,
                      help='Run browser in headless mode (default: True)')
    parser.add_argument('--no-headless', action='store_false', dest='headless',
                      help='Run browser with visible window')
    parser.add_argument('--author-ids', nargs='+',
                      help='Specific author IDs to scrape (overrides default list)')
    
    args = parser.parse_args()
    
    # Get connection string from args or environment variable
    connection_string = args.connection_string or os.environ.get('AZURE_STORAGE_CONNECTION_STRING')
    
    if not connection_string:
        parser.error('Azure Storage connection string is required. Provide via --connection-string or set AZURE_STORAGE_CONNECTION_STRING environment variable.')
    
    # Use provided author IDs or default list
    author_ids = args.author_ids if args.author_ids else DEFAULT_AUTHOR_IDS
    
    logger.info(f"Starting author scraper with {len(author_ids)} authors")
    
    scraper = AuthorScraper(
        azure_connection_string=connection_string,
        output_dir=args.output_dir,
        headless=args.headless,
        state_file=args.state,
        config_file=args.config
    )
    
    try:
        scraper.scrape_multiple_authors(
            author_ids=author_ids,
            max_publications_per_author=args.max_per_author
        )
    finally:
        scraper.close()


if __name__ == "__main__":
    main()
