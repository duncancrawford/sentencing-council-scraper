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
from bs4 import BeautifulSoup, Tag

from .config import (
    BASE_URL,
    INDEX_URLS,
    FALLBACK_INDEX_URLS,
    REQUEST_HEADERS,
    REQUEST_DELAY,
    MAX_RETRIES,
    RETRY_BACKOFF,
)
from .models import OffenceLink
from .index_tabs import extract_tab_links

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
        # 1) Script tags with inline JS
        for script in soup.find_all("script"):
            text = script.string or script.get_text() or ""
            data = self._parse_guideline_data_from_text(text)
            if data:
                return data

        # 2) JSON embedded in data attributes
        for el in soup.find_all(attrs={"data-guideline-data": True}):
            data = self._parse_guideline_data_from_text(el.get("data-guideline-data", ""))
            if data:
                return data

        logger.warning("No guidelineData JSON found in page")
        return []

    def _parse_guideline_data_from_text(self, text: str) -> list[dict]:
        """Try to extract guideline data from a blob of text."""
        if not text:
            return []

        # Direct JSON array
        stripped = text.strip()
        if stripped.startswith("[") and stripped.endswith("]"):
            try:
                data = json.loads(stripped)
                if isinstance(data, list):
                    logger.info(f"Extracted {len(data)} offences from JSON array")
                    return data
            except json.JSONDecodeError:
                pass

        # JSON object that contains guidelineData
        if stripped.startswith("{") and stripped.endswith("}"):
            try:
                obj = json.loads(stripped)
                if isinstance(obj, dict):
                    for key in ("guidelineData", "guidelinesData", "guideline_data"):
                        if key in obj and isinstance(obj[key], list):
                            logger.info(
                                f"Extracted {len(obj[key])} offences from JSON object"
                            )
                            return obj[key]
            except json.JSONDecodeError:
                pass

        # JS assignment patterns
        for key in ("guidelineData", "guidelinesData", "guideline_data"):
            match = re.search(rf"{key}\s*=\s*", text)
            if not match:
                continue
            json_str = self._extract_json_array_after(text, match.end())
            if not json_str:
                continue
            try:
                data = json.loads(json_str)
                if isinstance(data, list):
                    logger.info(f"Extracted {len(data)} offences from {key}")
                    return data
            except json.JSONDecodeError as e:
                logger.warning(f"Failed to parse {key} JSON: {e}")
                continue

        return []

    def _extract_json_array_after(self, text: str, start_idx: int) -> str:
        """Extract a JSON array after a given index using bracket matching."""
        idx = text.find("[", start_idx)
        if idx == -1:
            return ""

        depth = 0
        in_str = False
        escape = False

        for i in range(idx, len(text)):
            ch = text[i]
            if in_str:
                if escape:
                    escape = False
                elif ch == "\\":
                    escape = True
                elif ch == "\"":
                    in_str = False
                continue

            if ch == "\"":
                in_str = True
                continue
            if ch == "[":
                depth += 1
            elif ch == "]":
                depth -= 1
                if depth == 0:
                    return text[idx : i + 1]

        return ""

    def _infer_court_type_from_href(self, href: str, default: str) -> str:
        """Infer court type from legacy offence URL patterns."""
        if "/offences/magistrates-court/" in href:
            return "magistrates"
        if "/offences/crown-court/" in href:
            return "crown_court"
        return default

    def _extract_urls_from_text(self, text: str, offences_only: bool = True) -> list[str]:
        """Extract offence/guideline URLs from arbitrary text."""
        if not text:
            return []
        if offences_only:
            pattern = r"(https?://[^\s\"']+/offences/[^\s\"']+|/offences/[^\s\"']+)"
        else:
            pattern = (
                r"(https?://[^\s\"']+/(?:offences|guidelines)/[^\s\"']+"
                r"|/(?:offences|guidelines)/[^\s\"']+)"
            )
        return re.findall(pattern, text)

    def _derive_name_from_url(self, url: str) -> str:
        """Create a readable name from an offence URL."""
        path = url.split("?")[0].split("#")[0].rstrip("/")
        slug = path.split("/")[-1] if path else url
        slug = slug.replace("-", " ").replace("_", " ").strip()
        return slug.title() if slug else "Unknown offence"

    def _extract_offence_links_from_html(
        self, root: Tag, base_url: str, court_type: str, raw_html: str | None = None
    ) -> list[OffenceLink]:
        """Extract offence links from legacy A–Z list HTML."""
        links: list[OffenceLink] = []

        def add_url(url: str, name: str = "") -> None:
            href = url.strip()
            if not href:
                return
            if "/offences/" not in href:
                return
            full_url = urljoin(base_url, href)
            inferred = self._infer_court_type_from_href(href, court_type)
            display_name = name.strip() if name.strip() else self._derive_name_from_url(full_url)
            links.append(
                OffenceLink(
                    name=display_name,
                    url=full_url,
                    court_type=inferred,
                    category="",
                    source_tab="Offences",
                )
            )

        def add_link(a_tag: Tag) -> None:
            href = a_tag.get("href", "").strip()
            name = a_tag.get_text(strip=True)
            if not href:
                return
            add_url(href, name)

        # Prefer the "Offences" section if present.
        heading = None
        for tag in root.find_all(["h2", "h3", "h4"]):
            if tag.get_text(strip=True).lower() == "offences":
                heading = tag
                break

        if heading:
            for sibling in heading.find_next_siblings():
                if sibling.name in ("h2", "h3", "h4"):
                    sibling_text = sibling.get_text(strip=True).lower()
                    if sibling_text in ("overarching guidelines", "ancillary orders", "additional information"):
                        break
                for a_tag in sibling.find_all("a", href=True):
                    add_link(a_tag)
        else:
            for a_tag in root.find_all("a", href=True):
                add_link(a_tag)

        # Scan data attributes for embedded URLs
        for tag in root.find_all(True):
            for attr_val in tag.attrs.values():
                values = attr_val if isinstance(attr_val, list) else [attr_val]
                for value in values:
                    if not isinstance(value, str):
                        continue
                    for url in self._extract_urls_from_text(value, offences_only=True):
                        name = tag.get_text(strip=True)
                        add_url(url, name)

        # Last resort: regex scan of raw HTML for offence URLs
        if raw_html:
            for url in self._extract_urls_from_text(raw_html, offences_only=True):
                add_url(url)

        # De-duplicate by URL while preserving order.
        unique = []
        seen = set()
        for link in links:
            if link.url in seen:
                continue
            seen.add(link.url)
            unique.append(link)

        if unique:
            logger.info(f"Extracted {len(unique)} offence links from HTML list")
        return unique

    def discover_offences_from_index(
        self, url: str, court_type: str
    ) -> list[OffenceLink]:
        """Discover offence guideline links from an index page.

        Extracts the embedded guidelineData JSON, plus any HTML links
        from the overarching guidelines tab (tab-panel-1).
        """
        response = self._polite_get(url)
        html = response.text
        soup = BeautifulSoup(html, "lxml")
        links = []

        # Primary: extract from tab-panel-0 if present, else whole page
        panel_0 = soup.find(id="tab-panel-0")
        if panel_0:
            guideline_data = self._parse_guideline_data_from_text(str(panel_0))
            if not guideline_data:
                guideline_data = self._extract_guideline_data_json(panel_0)
        else:
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
                source_tab="Offences",
            )
            links.append(offence)

        # Secondary: also grab links from other tabs (overarching + supplementary)
        for link in extract_tab_links(soup, url, court_type):
            if not any(l.url == link.url for l in links):
                links.append(link)

        # Fallback: legacy A–Z offence list in HTML
        if not links:
            panel_0 = panel_0 or soup.find(id="tab-panel-0")
            if panel_0:
                links = self._extract_offence_links_from_html(
                    panel_0, url, court_type, raw_html=str(panel_0)
                )
            else:
                links = self._extract_offence_links_from_html(
                    soup, url, court_type, raw_html=html
                )

        # Final fallback: try legacy index URL if configured
        if not links:
            fallback_url = FALLBACK_INDEX_URLS.get(court_type)
            if fallback_url and fallback_url != url:
                logger.info(f"Retrying with fallback index URL: {fallback_url}")
                fallback_soup = self.get_soup(fallback_url)
                links = self._extract_offence_links_from_html(
                    fallback_soup, fallback_url, court_type
                )

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
