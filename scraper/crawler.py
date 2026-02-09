"""Web crawler for discovering sentencing guideline pages.

The Sentencing Council website embeds offence data as a JavaScript JSON
array (`var guidelineData = [...]`) inside a <script> tag within
tab-panel-0. This crawler extracts that JSON to discover all guideline
URLs, then fetches each guideline page individually.
"""

import json
import re
import time
import logging
from urllib.parse import urljoin

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

    def _extract_guideline_data_json(self, soup: BeautifulSoup) -> list[dict]:
        """Extract the guidelineData JSON array from the embedded <script> tag.

        The page contains a script like:
            var guidelineData = [{"id":"1974","name":"Abstracting electricity",...}, ...]

        This is inside the tab-panel-0 div. The JSON contains nested arrays
        (e.g. "courtType":["Crown","Magistrates"]) so we can't use a simple
        regex to match brackets — instead we find the start of the assignment
        and let json.loads handle the parsing.
        """
        for script in soup.find_all("script"):
            text = script.string or script.get_text() or ""
            # Find the assignment
            match = re.search(r"var\s+guidelineData\s*=\s*", text)
            if not match:
                continue

            # Everything after "var guidelineData = " is the JSON array
            json_str = text[match.end():].strip().rstrip(";").strip()

            if not json_str.startswith("["):
                logger.warning("guidelineData found but doesn't start with '['")
                continue

            try:
                data = json.loads(json_str)
                logger.info(f"Extracted {len(data)} offences from guidelineData JSON")
                return data
            except json.JSONDecodeError as e:
                logger.warning(f"Failed to parse guidelineData JSON: {e}")
                # Try to recover by finding the last complete object
                last_brace = json_str.rfind("}")
                if last_brace > 0:
                    truncated = json_str[: last_brace + 1] + "]"
                    try:
                        data = json.loads(truncated)
                        logger.info(
                            f"Extracted {len(data)} offences (truncated recovery)"
                        )
                        return data
                    except json.JSONDecodeError:
                        pass

        logger.warning("No guidelineData JSON found in page")
        return []

    def discover_offences_from_index(
        self, url: str, court_type: str
    ) -> list[OffenceLink]:
        """Discover offence guideline links from an index page.

        Extracts the embedded guidelineData JSON, plus any HTML links
        from the overarching guidelines tab (tab-panel-1).
        """
        soup = self.get_soup(url)
        links = []

        # Primary: extract from the guidelineData JSON in tab-panel-0
        guideline_data = self._extract_guideline_data_json(soup)

        for item in guideline_data:
            name = item.get("name", "")
            item_url = item.get("url", "")

            if not name or not item_url:
                continue

            full_url = urljoin(url, item_url)

            # Determine court type from the item data
            court_types = item.get("courtType", [])
            if isinstance(court_types, list):
                item_court = ", ".join(court_types)
            else:
                item_court = str(court_types)

            # Get the category from relevantCollections
            category = ""
            collections = item.get("relevantCollections", [])
            if collections and isinstance(collections, list):
                category = collections[0].get("name", "")

            offence = OffenceLink(
                name=name,
                url=full_url,
                court_type=item_court or court_type,
                category=category,
            )
            links.append(offence)

        # Secondary: also grab overarching guidelines from tab-panel-1
        panel_1 = soup.find(id="tab-panel-1")
        if panel_1:
            for a_tag in panel_1.find_all("a", href=True):
                href = a_tag["href"]
                full_url = urljoin(url, href)
                name = a_tag.get_text(strip=True)
                if name and "/guidelines/" in href:
                    offence = OffenceLink(
                        name=name,
                        url=full_url,
                        court_type=court_type,
                        category="Overarching guidelines",
                    )
                    if not any(l.url == offence.url for l in links):
                        links.append(offence)

        logger.info(f"Found {len(links)} guideline links on {url}")
        return links

    def discover_all_offences(self) -> list[OffenceLink]:
        """Discover all offence guidelines from all index pages.

        Fetches both the magistrates' and Crown Court index pages,
        deduplicates by URL, and returns a combined list.
        """
        all_links = []
        seen_urls = set()

        for court_type, url in INDEX_URLS.items():
            try:
                links = self.discover_offences_from_index(url, court_type)
                for link in links:
                    if link.url not in seen_urls:
                        seen_urls.add(link.url)
                        all_links.append(link)
                    else:
                        logger.debug(f"Duplicate URL skipped: {link.url}")
            except Exception as e:
                logger.error(f"Failed to crawl {court_type} page ({url}): {e}")

        logger.info(f"Total unique offences discovered: {len(all_links)}")
        return all_links
