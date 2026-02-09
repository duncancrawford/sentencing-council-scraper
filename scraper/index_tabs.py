"""Helpers for extracting guideline links from tab panels."""

from __future__ import annotations

from dataclasses import dataclass
from urllib.parse import urljoin

from bs4 import BeautifulSoup, Tag

from .models import OffenceLink


@dataclass(frozen=True)
class TabSpec:
    """Configuration for a tab panel that lists guideline links."""

    panel_id: str
    category: str
    source_tab: str
    allowed_hrefs: tuple[str, ...] = ()


DEFAULT_TABS: tuple[TabSpec, ...] = (
    TabSpec(
        panel_id="tab-panel-1",
        category="Overarching guidelines",
        source_tab="Overarching guidelines",
        allowed_hrefs=("/guidelines/", "/overarching-guides/"),
    ),
    TabSpec(
        panel_id="tab-panel-2",
        category="Supplementary information",
        source_tab="Supplementary information",
        allowed_hrefs=("/supplementary-information/",),
    ),
)


def extract_tab_links(
    soup: BeautifulSoup,
    base_url: str,
    court_type: str,
    tabs: tuple[TabSpec, ...] = DEFAULT_TABS,
) -> list[OffenceLink]:
    """Extract guideline links from configured tab panels."""
    links: list[OffenceLink] = []

    for spec in tabs:
        panel = soup.find(id=spec.panel_id)
        if not panel:
            continue
        for a_tag in panel.find_all("a", href=True):
            href = a_tag["href"]
            full_url = urljoin(base_url, href)
            name = a_tag.get_text(strip=True)
            if not name:
                continue
            if spec.allowed_hrefs and not any(part in href for part in spec.allowed_hrefs):
                continue
            offence = OffenceLink(
                name=name,
                url=full_url,
                court_type=court_type,
                category=spec.category,
                source_tab=spec.source_tab,
            )
            if not any(l.url == offence.url for l in links):
                links.append(offence)

    return links
