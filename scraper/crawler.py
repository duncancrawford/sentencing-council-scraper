"""Web crawler for discovering sentencing guideline pages."""

import time
import logging
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup

from .config import (
    BASE_URL,
    INDEX_URLS,
    REQUEST_HEADERS,
    REQUEST_DELAY,
    MAX_RETRIES,
    RETRY_BACKOFF,
)
from .models import OffenceLink

logger = logging.getLogger(__name__)


class SentencingCrawler:
    """Crawls the Sentencing Council website to discover guideline pages."""

    def __init__(self, delay: float = REQUEST_DELAY):
        self.session = requests.Session()
        self.session.headers.update(REQUEST_HEADERS)
        self.delay = delay
        self._last_request_time = 0.0

    def _polite_get(self, url: str) -> requests.Response:
        """Make a GET request with polite delays and retries."""
        elapsed = time.time() - self._last_request_time
        if elapsed < self.delay:
            time.sleep(self.delay - elapsed)

        for attempt in range(MAX_RETRIES):
            try:
                logger.info(f"Fetching: {url}")
                response = self.session.get(url, timeout=30)
                self._last_request_time = time.time()

                if response.status_code == 200:
                    return response
                elif response.status_code == 429:
                    wait = RETRY_BACKOFF ** (attempt + 1)
                    logger.warning(f"Rate limited, waiting {wait}s...")
                    time.sleep(wait)
                else:
                    logger.warning(
                        f"HTTP {response.status_code} for {url}"
                    )
                    response.raise_for_status()

            except requests.RequestException as e:
                if attempt < MAX_RETRIES - 1:
                    wait = RETRY_BACKOFF ** (attempt + 1)
                    logger.warning(
                        f"Request failed ({e}), retrying in {wait}s..."
                    )
                    time.sleep(wait)
                else:
                    raise

        return response

    def get_soup(self, url: str) -> BeautifulSoup:
        """Fetch a URL and return a BeautifulSoup object."""
        response = self._polite_get(url)
        return BeautifulSoup(response.text, "lxml")

    def discover_offences_from_index(self, url: str, court_type: str) -> list[OffenceLink]:
        """Discover offence guideline links from an index/listing page."""
        soup = self.get_soup(url)
        links = []
        current_category = ""

        # The offences page typically groups offences under category headings.
        # We try multiple strategies to find offence links.

        # Strategy 1: Look for links within the main content area
        main_content = (
            soup.find("main")
            or soup.find("div", class_="main-content")
            or soup.find("article")
            or soup.find("div", id="content")
            or soup
        )

        # Try to find offence links — these typically point to /offences/ paths
        for link in main_content.find_all("a", href=True):
            href = link["href"]
            full_url = urljoin(url, href)
            parsed = urlparse(full_url)

            # Filter for guideline/offence pages
            if not parsed.netloc.endswith("sentencingcouncil.org.uk"):
                continue

            path = parsed.path.rstrip("/")

            # Offence detail pages typically match patterns like:
            # /offences/magistrates-court/item/common-assault/
            # /offences/crown-court/item/murder/
            is_offence_page = (
                "/item/" in path
                or (
                    "/offences/" in path
                    and path.count("/") >= 4
                    and path not in ("/offences/magistrates-court", "/offences/crown-court")
                )
            )

            if not is_offence_page:
                # Check if this is a category heading
                parent = link.find_parent(["h2", "h3", "h4"])
                if parent:
                    current_category = link.get_text(strip=True)
                continue

            name = link.get_text(strip=True)
            if not name:
                continue

            # Try to determine category from surrounding context
            category = current_category
            heading = link.find_previous(["h2", "h3"])
            if heading:
                category = heading.get_text(strip=True)

            offence = OffenceLink(
                name=name,
                url=full_url,
                court_type=court_type,
                category=category,
            )

            # Avoid duplicates
            if not any(l.url == offence.url for l in links):
                links.append(offence)

        logger.info(f"Found {len(links)} offence links on {url}")
        return links

    def discover_all_offences(self) -> list[OffenceLink]:
        """Discover all offence guidelines from all index pages."""
        all_links = []
        seen_urls = set()

        # First try the main offences page which lists everything
        try:
            main_links = self.discover_offences_from_index(
                INDEX_URLS["all_offences"], "all"
            )
            for link in main_links:
                if link.url not in seen_urls:
                    seen_urls.add(link.url)
                    all_links.append(link)
        except Exception as e:
            logger.warning(f"Failed to crawl main offences page: {e}")

        # Then crawl the court-specific pages for any we missed
        for court_type, url in INDEX_URLS.items():
            if court_type == "all_offences":
                continue
            try:
                links = self.discover_offences_from_index(url, court_type)
                for link in links:
                    if link.url not in seen_urls:
                        seen_urls.add(link.url)
                        all_links.append(link)
            except Exception as e:
                logger.warning(f"Failed to crawl {court_type} page: {e}")

        # If the index pages didn't work well, try a sitemap approach
        if len(all_links) < 5:
            logger.info(
                "Few links found via index pages, trying alternative discovery..."
            )
            alt_links = self._discover_via_search_page(all_links, seen_urls)
            all_links.extend(alt_links)

        logger.info(f"Total offences discovered: {len(all_links)}")
        return all_links

    def _discover_via_search_page(
        self, existing: list, seen_urls: set
    ) -> list[OffenceLink]:
        """Alternative discovery by crawling the site more broadly."""
        extra = []

        # Try crawling the main guidelines pages
        for court_type in ("magistrates", "crown-court"):
            url = f"{BASE_URL}/guidelines/{court_type}/"
            try:
                soup = self.get_soup(url)
                for link in soup.find_all("a", href=True):
                    href = link["href"]
                    full_url = urljoin(url, href)

                    if full_url in seen_urls:
                        continue
                    if "sentencingcouncil.org.uk" not in full_url:
                        continue
                    if "/item/" not in full_url and "/offences/" not in full_url:
                        continue

                    name = link.get_text(strip=True)
                    if name:
                        offence = OffenceLink(
                            name=name,
                            url=full_url,
                            court_type=court_type.replace("-", "_"),
                        )
                        seen_urls.add(full_url)
                        extra.append(offence)
            except Exception as e:
                logger.warning(f"Alternative discovery failed for {url}: {e}")

        return extra
