"""Parser for supplementary information pages."""

from __future__ import annotations

from bs4 import BeautifulSoup, Tag

from .models import SupplementaryPage, SupplementarySection
from .parser import GuidelineParser


class SupplementaryParser:
    """Parses a supplementary information page into structured sections."""

    def __init__(self, soup: BeautifulSoup, url: str, court_type: str = ""):
        self.soup = soup
        self.url = url
        self.court_type = court_type
        # Reuse main-content selection logic from GuidelineParser.
        self._content = GuidelineParser(soup, url, court_type)._get_main_content()

    def parse(
        self,
        page_type: str = "supplementary",
        source_tab: str = "",
        category: str = "",
    ) -> SupplementaryPage:
        title = self._parse_title()
        sections = self._parse_sections()
        return SupplementaryPage(
            page_title=title,
            url=self.url,
            court_type=self.court_type,
            sections=sections,
            page_type=page_type,
            source_tab=source_tab,
            category=category,
        )

    def _parse_title(self) -> str:
        h1 = self.soup.find("h1")
        if h1:
            return h1.get_text(strip=True)
        title = self.soup.find("title")
        return title.get_text(strip=True) if title else "Supplementary information"

    def _parse_sections(self) -> list[SupplementarySection]:
        headings = self._content.find_all(["h2", "h3", "h4"])
        if not headings:
            text = self._content.get_text("\n", strip=True)
            return [
                SupplementarySection(
                    heading="Content",
                    level="h2",
                    text=text,
                    bullets=self._extract_bullets(self._content),
                    tables=self._extract_tables(self._content),
                )
            ]

        sections: list[SupplementarySection] = []
        for heading in headings:
            heading_text = heading.get_text(" ", strip=True)
            nodes = []
            for sibling in heading.find_next_siblings():
                if sibling.name in ("h2", "h3", "h4"):
                    break
                nodes.append(sibling)
            section_root = self._wrap_nodes(nodes)
            text = section_root.get_text("\n", strip=True)
            sections.append(
                SupplementarySection(
                    heading=heading_text,
                    level=heading.name or "h2",
                    text=text,
                    bullets=self._extract_bullets(section_root),
                    tables=self._extract_tables(section_root),
                )
            )
        return sections

    def _extract_bullets(self, root: Tag) -> list[str]:
        bullets = []
        for li in root.find_all("li"):
            text = li.get_text(" ", strip=True)
            if text:
                bullets.append(text)
        return bullets

    def _extract_tables(self, root: Tag) -> list[list[list[str]]]:
        tables = []
        for table in root.find_all("table"):
            rows = []
            for row in table.find_all("tr"):
                cells = [
                    cell.get_text(" ", strip=True)
                    for cell in row.find_all(["th", "td"])
                ]
                if cells:
                    rows.append(cells)
            if rows:
                tables.append(rows)
        return tables

    def _wrap_nodes(self, nodes: list[Tag]) -> Tag:
        wrapper = self.soup.new_tag("div")
        for node in nodes:
            wrapper.append(node)
        return wrapper
