"""
DTIC Scraper for publications and technical reports.

This scraper navigates https://dtic.dimensions.ai/discover/publication
and extracts publication data, including author and organization information.
It includes state persistence and rate limiting for resilient operation.
"""

import json
import logging
import time
import random
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


def load_config(config_file: str = "config.json") -> Dict:
    """Load configuration from JSON file."""
    config_path = Path(config_file)
    if config_path.exists():
        try:
            with open(config_path, 'r', encoding='utf-8') as f:
                return json.load(f)
        except json.JSONDecodeError as e:
            # Can't use logger here as it's not configured yet
            print(f"Warning: Error loading config file: {e}, using defaults")
    return {}


# Generate timestamped log filename
_log_timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
_logs_dir = Path("logs")
_logs_dir.mkdir(exist_ok=True)
_log_filename = _logs_dir / f"{_log_timestamp}_dtic_scraper.log"

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(_log_filename),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)


@dataclass
class Author:
    """Represents a publication author."""
    name: str
    affiliations: List[str]
    researcher_id: Optional[str] = None


@dataclass
class Organization:
    """Represents an organization."""
    name: str
    org_id: Optional[str] = None
    country: Optional[str] = None
    type: Optional[str] = None


@dataclass
class Publication:
    """Represents a publication or technical report."""
    publication_id: str
    title: str
    abstract: Optional[str]
    authors: List[Dict]
    organizations: List[Dict]
    publication_date: Optional[str]
    url: str
    doi: Optional[str] = None
    document_type: Optional[str] = None
    keywords: Optional[List[str]] = None
    citations_count: Optional[int] = None
    scraped_at: Optional[str] = None
    
    def __post_init__(self):
        if self.scraped_at is None:
            self.scraped_at = datetime.now().isoformat()
        if self.keywords is None:
            self.keywords = []


class StateManager:
    """Manages scraper state for resilient operation."""
    
    def __init__(self, state_file: str = "scraper_state.json"):
        self.state_file = Path(state_file)
        self.state = self._load_state()
    
    def _load_state(self) -> Dict:
        """Load state from file or create new state."""
        if self.state_file.exists():
            try:
                with open(self.state_file, 'r', encoding='utf-8') as f:
                    state = json.load(f)
                    logger.info(f"Loaded state: {len(state.get('scraped_ids', []))} publications scraped")
                    return state
            except json.JSONDecodeError:
                logger.warning("Corrupted state file, starting fresh")
        
        return {
            'scraped_ids': [],
            'failed_ids': [],
            'last_page': 0,
            'last_updated': None
        }
    
    def save_state(self):
        """Save current state to file."""
        self.state['last_updated'] = datetime.now().isoformat()
        with open(self.state_file, 'w', encoding='utf-8') as f:
            json.dump(self.state, f, indent=2)
        logger.debug("State saved")
    
    def mark_scraped(self, publication_id: str):
        """Mark a publication as successfully scraped."""
        if publication_id not in self.state['scraped_ids']:
            self.state['scraped_ids'].append(publication_id)
            self.save_state()
    
    def mark_failed(self, publication_id: str):
        """Mark a publication as failed."""
        if publication_id not in self.state['failed_ids']:
            self.state['failed_ids'].append(publication_id)
            self.save_state()
    
    def is_scraped(self, publication_id: str) -> bool:
        """Check if publication has been scraped."""
        return publication_id in self.state['scraped_ids']
    
    def update_page(self, page: int):
        """Update last processed page."""
        self.state['last_page'] = page
        self.save_state()


class RateLimiter:
    """Handles rate limiting with exponential backoff."""
    
    def __init__(self, 
                 min_delay: float = 2.0, 
                 max_delay: float = 10.0,
                 base_backoff: float = 2.0):
        self.min_delay = min_delay
        self.max_delay = max_delay
        self.base_backoff = base_backoff
        self.consecutive_errors = 0
    
    def wait(self):
        """Wait with random jitter to avoid detection."""
        delay = random.uniform(self.min_delay, self.max_delay)
        logger.debug(f"Rate limiting: waiting {delay:.2f} seconds")
        time.sleep(delay)
    
    def backoff(self):
        """Exponential backoff after errors."""
        self.consecutive_errors += 1
        delay = min(
            self.base_backoff ** self.consecutive_errors,
            60  # Max 60 seconds
        )
        logger.warning(f"Backing off for {delay:.2f} seconds (error #{self.consecutive_errors})")
        time.sleep(delay)
    
    def reset(self):
        """Reset error counter after successful operation."""
        self.consecutive_errors = 0


class DTICScraper:
    """Main scraper class for DTIC publications."""
    
    def __init__(self, 
                 output_dir: str = "dtic_publications",
                 headless: bool = True,
                 state_file: str = "scraper_state.json",
                 config_file: str = "config.json"):
        # Load configuration
        self.config = load_config(config_file)
        
        # Apply config or use defaults
        self.output_dir = Path(output_dir)
        # Create output directory if it doesn't exist
        self.output_dir.mkdir(parents=True, exist_ok=True)
        logger.info(f"Output directory: {self.output_dir.absolute()}")
        
        self.headless = self.config.get('scraper', {}).get('headless', headless)
        logger.info("Fast mode: enabled (JS extraction only)")
        
        self.driver: Optional[webdriver.Chrome] = None
        self.state_manager = StateManager(state_file)
        
        # Initialize rate limiter with config values
        rate_config = self.config.get('rate_limiting', {})
        self.rate_limiter = RateLimiter(
            min_delay=rate_config.get('min_delay', 2.0),
            max_delay=rate_config.get('max_delay', 10.0),
            base_backoff=rate_config.get('base_backoff', 2.0)
        )
        
        self.base_url = self.config.get('scraper', {}).get('base_url', 
                                                             "https://dtic.dimensions.ai/discover/publication")
        
        # Get selectors from config
        self.selectors = self.config.get('selectors', {})
    
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
        
        # Use 'eager' page load strategy - returns when DOM is loaded, not all resources
        chrome_options.page_load_strategy = 'eager'
        
        # Disable images for faster loading
        prefs = {
            "profile.managed_default_content_settings.images": 2,
            "profile.default_content_setting_values.notifications": 2,
        }
        chrome_options.add_experimental_option("prefs", prefs)
        
        self.driver = webdriver.Chrome(options=chrome_options)
        
        # Set page load timeout
        page_timeout = self.config.get('timeouts', {}).get('page_load', 10)
        self.driver.set_page_load_timeout(page_timeout)
        
        # Minimal implicit wait
        self.driver.implicitly_wait(3)
        logger.info("WebDriver initialized (eager page loading, images disabled)")

    
    def _extract_javascript_data(self, script_pattern: str = "__NUXT__") -> Optional[Dict]:
        """
        Extract data from JavaScript objects embedded in the page.
        Returns the publication data from config.details.document or similar objects.
        """
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
            
        except Exception as e:
            logger.warning(f"Could not extract JavaScript data: {e}")
        
        return None
    
    def _extract_publication_from_page(self, url: str) -> Optional[Publication]:
        """
        Extract publication data from a detailed publication page using JavaScript.
        
        Args:
            url: Publication URL
        """
        try:
            # Rate limit before page load
            self.rate_limiter.wait()
            
            # Start loading page
            start_load = time.time()
            logger.info(f"Starting page load: {url}")
            
            self.driver.get(url)
            
            load_time = time.time() - start_load
            logger.info(f"Page loaded in {load_time:.2f}s")
            
            # Wait for JavaScript to execute
            start_wait = time.time()
            WebDriverWait(self.driver, 3).until(
                lambda d: d.execute_script("return document.readyState") == "complete"
            )
            wait_time = time.time() - start_wait
            logger.debug(f"JavaScript ready in {wait_time:.2f}s")
            
            # Extract publication ID from URL
            pub_id = url.split('/')[-1]
            
            # Start extraction
            start_extract = time.time()
            logger.debug(f"Starting data extraction for {pub_id}")
            
            result = self._extract_publication_from_js(url, pub_id)
            
            extract_time = time.time() - start_extract
            logger.info(f"Data extraction completed in {extract_time:.2f}s")
            
            return result
            
        except Exception as e:
            logger.error(f"Error extracting publication from {url}: {e}")
            return None
    
    def _extract_publication_from_js(self, url: str, pub_id: str) -> Optional[Publication]:
        """
        Extract publication data from JavaScript objects only.
        No fallback to DOM scraping - if data isn't in JS, it's skipped.
        """
        try:
            # Get JavaScript data
            js_data = self._extract_javascript_data()
            
            if not js_data:
                logger.warning(f"No JS data found for {pub_id}")
                return None
            
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
            start_authors = time.time()
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
                        
                        # Extract affiliation names
                        affil_list = []
                        for affil in author_data.get('affiliations', []):
                            if isinstance(affil, dict):
                                affil_name = affil.get('name')
                                if affil_name:
                                    affil_list.append(affil_name)
                        
                        if name:
                            authors.append(Author(
                                name=name,
                                researcher_id=researcher_id,
                                affiliations=affil_list
                            ))
            
            authors_time = time.time() - start_authors
            logger.debug(f"Extracted {len(authors)} authors from JS in {authors_time:.2f}s")
            
            # Extract organizations from author affiliations
            start_orgs = time.time()
            organizations = []
            if authors_section:
                affiliations_details = authors_section.get('affiliations_details', [])
                seen_orgs = set()
                for author_data in affiliations_details:
                    if isinstance(author_data, dict):
                        for affil in author_data.get('affiliations', []):
                            if isinstance(affil, dict):
                                org_id = affil.get('id')  # grid.* ID
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
            
            orgs_time = time.time() - start_orgs
            logger.debug(f"Extracted {len(organizations)} organizations from JS in {orgs_time:.2f}s")
            
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
                url=url,
                doi=doi,
                document_type=document_type,
                keywords=keywords,
                citations_count=citations_count
            )
            
            logger.info(f"[JS] Extracted publication: {title[:50] if title else pub_id}...")
            return publication
            
        except Exception as e:
            logger.error(f"Error in JS extraction for {pub_id}: {e}")
            return None
    
    def _extract_fields_of_research(self, js_data: Dict) -> List[str]:
        """
        Extract Fields of Research path from JavaScript data.
        
        Args:
            js_data: The complete JavaScript data object
            
        Returns:
            List containing the navigation path (if found)
        """
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
    
    def _get_publication_links(self) -> List[str]:
        """Extract publication links from the current search results page."""
        links = []
        
        try:
            # Get publication link selectors from config
            pub_link_selectors = self.selectors.get('publication_links', [
                "a[href*='/publication/']"
            ])
            
            if isinstance(pub_link_selectors, str):
                pub_link_selectors = [pub_link_selectors]
            
            # Wait for results to load using first selector
            WebDriverWait(self.driver, 15).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, pub_link_selectors[0]))
            )
            
            # Extract all publication links using all configured selectors
            for selector in pub_link_selectors:
                link_elements = self.driver.find_elements(By.CSS_SELECTOR, selector)
            # Extract all publication links using all configured selectors
            for selector in pub_link_selectors:
                link_elements = self.driver.find_elements(By.CSS_SELECTOR, selector)
                
                for elem in link_elements:
                    try:
                        href = elem.get_attribute('href')
                        if href and href not in links:
                            # Ensure it's a direct publication link
                            if '/publication/pub.' in href or '/publication/' in href:
                                links.append(href)
                    except StaleElementReferenceException:
                        continue
            
            logger.info(f"Found {len(links)} publication links on current page")
            
        except TimeoutException:
            logger.warning("Timeout waiting for publication links")
        except Exception as e:
            logger.error(f"Error getting publication links: {e}")
        
        return links
    
    def _save_publication(self, publication: Publication):
        """Save publication to individual JSON file in output directory."""
        try:
            # Create filename from publication ID
            filename = f"{publication.publication_id}.json"
            filepath = self.output_dir / filename
            
            # Save as formatted JSON
            with open(filepath, 'w', encoding='utf-8') as f:
                json.dump(asdict(publication), f, indent=2, ensure_ascii=False)
            
            logger.debug(f"Saved publication: {publication.publication_id} to {filename}")
        except Exception as e:
            logger.error(f"Error saving publication: {e}")
    
    def _scroll_and_load_more(self) -> bool:
        """
        Scroll down to trigger infinite scroll and load more publications.
        
        Returns:
            True if more content was loaded, False otherwise
        """
        try:
            # Get current page height
            last_height = self.driver.execute_script("return document.body.scrollHeight")
            
            # Scroll to bottom
            self.driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
            
            # Wait for new content to load
            time.sleep(2)
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
    
    def scrape(self, max_pages: Optional[int] = None, max_publications: Optional[int] = None):
        """
        Main scraping method using infinite scroll.
        
        Args:
            max_pages: Maximum number of scrolls/batches (None for unlimited)
            max_publications: Maximum number of publications to scrape (None for unlimited)
        """
        try:
            self._init_driver()
            
            # Navigate to base URL
            logger.info(f"Navigating to {self.base_url}")
            self.driver.get(self.base_url)
            self.rate_limiter.wait()
            
            scraped_count = len(self.state_manager.state['scraped_ids'])
            scroll_count = 0
            all_seen_links = set()
            
            while True:
                # Check limits
                if max_pages and scroll_count >= max_pages:
                    logger.info(f"Reached maximum scroll limit: {max_pages}")
                    break
                
                if max_publications and scraped_count >= max_publications:
                    logger.info(f"Reached maximum publications limit: {max_publications}")
                    break
                
                logger.info(f"Processing scroll batch {scroll_count + 1}")
                
                # Get all publication links currently visible
                pub_links = self._get_publication_links()
                
                if not pub_links:
                    logger.warning("No publication links found")
                    break
                
                # Filter to new links only
                new_links = [link for link in pub_links if link not in all_seen_links]
                logger.info(f"Found {len(new_links)} new publication links (total seen: {len(all_seen_links)})")
                
                # Add to seen set
                all_seen_links.update(new_links)
                
                # Process new publications
                for link in new_links:
                    pub_id = link.split('/')[-1]
                    
                    # Skip if already scraped
                    if self.state_manager.is_scraped(pub_id):
                        logger.debug(f"Skipping already scraped publication: {pub_id}")
                        continue
                    
                    # Check publication limit
                    if max_publications and scraped_count >= max_publications:
                        break
                    
                    try:
                        logger.info(f"{'='*60}")
                        logger.info(f"Processing publication {scraped_count + 1}: {pub_id}")
                        logger.info(f"{'='*60}")
                        
                        # Extract publication data
                        publication = self._extract_publication_from_page(link)
                        
                        if publication:
                            # Save publication
                            self._save_publication(publication)
                            self.state_manager.mark_scraped(pub_id)
                            scraped_count += 1
                            self.rate_limiter.reset()
                            
                            logger.info(f"[OK] Successfully scraped publication {scraped_count}/{max_publications or 'ALL'}")
                            
                            # Navigate back to main page
                            self.driver.get(self.base_url)
                            self.rate_limiter.wait()
                            
                            # Scroll to where we were
                            for _ in range(scroll_count):
                                self.driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
                                time.sleep(0.5)
                        else:
                            self.state_manager.mark_failed(pub_id)
                        
                    except Exception as e:
                        logger.error(f"Error processing publication {pub_id}: {e}")
                        self.state_manager.mark_failed(pub_id)
                        self.rate_limiter.backoff()
                        
                        # Try to recover by going back to main page
                        try:
                            self.driver.get(self.base_url)
                            self.rate_limiter.wait()
                        except:
                            pass
                
                # Check if we've hit the publication limit
                if max_publications and scraped_count >= max_publications:
                    break
                
                # Try to load more content via infinite scroll
                if not self._scroll_and_load_more():
                    logger.info("No more content to load")
                    break
                
                scroll_count += 1
            
            logger.info(f"Scraping completed. Total publications: {scraped_count}")
            
        except KeyboardInterrupt:
            logger.info("Scraping interrupted by user")
        except Exception as e:
            logger.error(f"Fatal error during scraping: {e}")
        finally:
            if self.driver:
                self.driver.quit()
                logger.info("WebDriver closed")
    
    def resume(self, max_pages: Optional[int] = None, max_publications: Optional[int] = None):
        """Resume scraping from last saved state."""
        logger.info("Resuming scraping from saved state")
        self.scrape(max_pages=max_pages, max_publications=max_publications)


def main():
    """Main entry point for the scraper."""
    import argparse
    
    parser = argparse.ArgumentParser(description="DTIC Publication Scraper")
    parser.add_argument('--output-dir', '-o', default='dtic_publications',
                      help='Output directory path (default: dtic_publications)')
    parser.add_argument('--state', '-s', default='scraper_state.json',
                      help='State file path (default: scraper_state.json)')
    parser.add_argument('--config', '-c', default='config.json',
                      help='Config file path (default: config.json)')
    parser.add_argument('--max-pages', '-p', type=int, default=None,
                      help='Maximum number of pages to scrape')
    parser.add_argument('--max-publications', '-n', type=int, default=None,
                      help='Maximum number of publications to scrape')
    parser.add_argument('--headless', action='store_true', default=True,
                      help='Run browser in headless mode (default: True)')
    parser.add_argument('--no-headless', action='store_false', dest='headless',
                      help='Run browser with visible window')
    parser.add_argument('--resume', '-r', action='store_true',
                      help='Resume from last saved state')
    
    args = parser.parse_args()
    
    scraper = DTICScraper(
        output_dir=args.output_dir,
        headless=args.headless,
        state_file=args.state,
        config_file=args.config
    )
    
    if args.resume:
        scraper.resume(max_pages=args.max_pages, max_publications=args.max_publications)
    else:
        scraper.scrape(max_pages=args.max_pages, max_publications=args.max_publications)


if __name__ == "__main__":
    main()
