"""Parsers for extracting structured data from sentencing guideline pages.

The Sentencing Council guideline pages follow a general structure but vary
in detail. Each page typically contains:

  Step 1 — Determining the offence category (culpability + harm)
  Step 2 — Starting point and category range (sentencing table)
  Aggravating factors
  Mitigating factors
  Further steps

The HTML structure is not always consistent between offences, so these
parsers use multiple strategies and fall back gracefully.
"""

import re
import logging
from typing import Optional
from urllib.parse import urljoin

from bs4 import BeautifulSoup, Tag

from .models import (
    Guideline,
    CulpabilityLevel,
    HarmLevel,
    SentencingRange,
)

logger = logging.getLogger(__name__)


class GuidelineParser:
    """Parses a sentencing guideline page into structured data."""

    def __init__(self, soup: BeautifulSoup, url: str, court_type: str = ""):
        self.soup = soup
        self.url = url
        self.court_type = court_type

    def parse(self) -> Guideline:
        """Parse the full guideline page."""
        guideline = Guideline(
            offence_name=self._parse_offence_name(),
            url=self.url,
            court_type=self.court_type,
            legislation=self._parse_legislation(),
            effective_from=self._parse_effective_date(),
        )

        # Parse the structured steps
        guideline.culpability_levels = self._parse_culpability()
        guideline.harm_levels = self._parse_harm()
        guideline.sentencing_ranges = self._parse_sentencing_table()
        guideline.aggravating_factors = self._parse_factors("aggravat")
        guideline.mitigating_factors = self._parse_factors("mitigat")
        guideline.additional_steps = self._parse_additional_steps()

        # Also capture raw section text as fallback
        guideline.raw_sections = self._capture_raw_sections()

        return guideline

    def _get_main_content(self) -> Tag:
        """Find the main content area of the page."""
        candidates = [
            self.soup.find("main"),
            self.soup.find("div", class_=re.compile(r"main.?content|guideline.?content|entry.?content")),
            self.soup.find("article"),
            self.soup.find("div", id="content"),
        ]
        for c in candidates:
            if c:
                return c
        return self.soup

    def _parse_offence_name(self) -> str:
        """Extract the offence name from the page title."""
        # Try the h1 heading first
        h1 = self.soup.find("h1")
        if h1:
            return h1.get_text(strip=True)

        # Fall back to page title
        title = self.soup.find("title")
        if title:
            text = title.get_text(strip=True)
            # Remove site suffix like " – Sentencing"
            return re.split(r"\s*[–—|-]\s*Sentencing", text)[0].strip()

        return "Unknown offence"

    def _parse_legislation(self) -> str:
        """Extract the legislation reference (e.g. 'Theft Act 1968, s.1')."""
        content = self._get_main_content()

        # Look for text near headings about the offence
        for tag in content.find_all(["p", "div", "span"]):
            text = tag.get_text(strip=True)
            # Common patterns: "Contrary to section X of the Y Act ZZZZ"
            if re.search(r"(contrary to|section \d|s\.\d|\bAct\b \d{4})", text, re.I):
                return text
            # Also look for explicit legislation labels
            if re.search(r"(legislation|statute|offence wording)", text, re.I):
                return text

        return ""

    def _parse_effective_date(self) -> str:
        """Extract the effective date of the guideline."""
        content = self._get_main_content()

        for tag in content.find_all(["p", "div", "span", "time"]):
            text = tag.get_text(strip=True)
            if re.search(r"effective from|in force|applies to|came into force", text, re.I):
                return text

        # Check for <time> elements
        time_tag = content.find("time")
        if time_tag:
            return time_tag.get("datetime", time_tag.get_text(strip=True))

        return ""

    def _find_section(self, *keywords: str) -> Optional[Tag]:
        """Find a section by looking for headings containing keywords."""
        content = self._get_main_content()

        for heading in content.find_all(["h1", "h2", "h3", "h4", "h5"]):
            heading_text = heading.get_text(strip=True).lower()
            if any(kw.lower() in heading_text for kw in keywords):
                return heading

        # Also search in accordion/tab elements
        for el in content.find_all(class_=re.compile(r"accordion|tab|panel|step")):
            el_text = el.get_text(strip=True)[:200].lower()
            if any(kw.lower() in el_text for kw in keywords):
                return el

        return None

    def _get_section_content(self, heading: Tag) -> list[Tag]:
        """Get all content between this heading and the next heading of same or higher level."""
        if heading is None:
            return []

        level = heading.name  # e.g. "h2"
        content = []

        for sibling in heading.find_next_siblings():
            if sibling.name and sibling.name in ("h1", "h2", "h3", "h4"):
                if sibling.name <= level:
                    break
            content.append(sibling)

        return content

    def _parse_culpability(self) -> list[CulpabilityLevel]:
        """Parse culpability levels from Step 1."""
        levels = []
        heading = self._find_section("culpability", "step 1", "offence category")

        if heading is None:
            return levels

        # Look for culpability content in tables, lists, or structured divs
        section_content = self._get_section_content(heading)
        parent = heading.parent if heading.parent else self._get_main_content()

        # Strategy 1: Parse from tables
        for table in parent.find_all("table"):
            table_text = table.get_text(strip=True).lower()
            if "culpability" not in table_text and "culp" not in table_text:
                continue
            levels.extend(self._parse_culpability_table(table))
            if levels:
                return levels

        # Strategy 2: Parse from headings + lists
        for tag in section_content:
            if isinstance(tag, Tag):
                levels.extend(self._parse_culpability_from_content(tag))

        # Strategy 3: Look for lettered/named categories
        if not levels:
            content_text = " ".join(
                t.get_text() for t in section_content if isinstance(t, Tag)
            )
            levels = self._parse_culpability_from_text(content_text)

        return levels

    def _parse_culpability_table(self, table: Tag) -> list[CulpabilityLevel]:
        """Parse culpability from a table element."""
        levels = []
        rows = table.find_all("tr")

        for row in rows:
            cells = row.find_all(["td", "th"])
            if len(cells) >= 2:
                level_text = cells[0].get_text(strip=True)
                desc = cells[1].get_text(strip=True)

                # Extract bullet points as individual factors
                factors = [li.get_text(strip=True) for li in cells[1].find_all("li")]
                if not factors:
                    factors = [desc] if desc else []

                if level_text and any(
                    c in level_text.upper()
                    for c in ("A", "B", "C", "HIGH", "MEDIUM", "LOW", "LESSER", "GREATER")
                ):
                    levels.append(
                        CulpabilityLevel(
                            level=level_text,
                            description=desc,
                            factors=factors,
                        )
                    )
            elif len(cells) == 1:
                # Single-column table row — might be a header or a factor
                text = cells[0].get_text(strip=True)
                level_match = re.match(
                    r"^(Category\s+)?([ABC]|[123]|High|Medium|Low|Lesser|Greater)",
                    text, re.I,
                )
                if level_match and levels:
                    continue  # This is likely a header for the next level
                elif level_match:
                    levels.append(
                        CulpabilityLevel(level=text, description="", factors=[])
                    )

        return levels

    def _parse_culpability_from_content(self, tag: Tag) -> list[CulpabilityLevel]:
        """Parse culpability from non-table content."""
        levels = []

        for heading in tag.find_all(["h3", "h4", "h5", "strong", "b"]):
            text = heading.get_text(strip=True)
            level_match = re.match(
                r"^(Culpability\s+)?(Category\s+)?([ABC]|High|Medium|Low|Lesser|Greater)",
                text, re.I,
            )
            if level_match:
                # Gather factors from the following list
                factors = []
                next_list = heading.find_next("ul")
                if next_list:
                    factors = [li.get_text(strip=True) for li in next_list.find_all("li")]

                levels.append(
                    CulpabilityLevel(
                        level=level_match.group(0).strip(),
                        description="",
                        factors=factors,
                    )
                )

        return levels

    def _parse_culpability_from_text(self, text: str) -> list[CulpabilityLevel]:
        """Last resort: parse culpability from raw text."""
        levels = []
        # Look for patterns like "Culpability A:" or "High culpability"
        for match in re.finditer(
            r"(Culpability\s+)?([ABC]|High|Medium|Low|Greater|Lesser)\s*(?:culpability)?[:\-–]?\s*(.*?)(?=(?:Culpability\s+)?(?:[ABC]|High|Medium|Low|Greater|Lesser)\s|$)",
            text,
            re.I | re.S,
        ):
            level = match.group(2).strip()
            desc = match.group(3).strip()[:500]
            levels.append(CulpabilityLevel(level=level, description=desc, factors=[]))

        return levels

    def _parse_harm(self) -> list[HarmLevel]:
        """Parse harm categories from Step 1."""
        levels = []
        heading = self._find_section("harm", "step 1", "offence category")

        if heading is None:
            return levels

        section_content = self._get_section_content(heading)
        parent = heading.parent if heading.parent else self._get_main_content()

        # Strategy 1: Tables
        for table in parent.find_all("table"):
            table_text = table.get_text(strip=True).lower()
            if "harm" not in table_text and "category" not in table_text:
                continue
            levels.extend(self._parse_harm_table(table))
            if levels:
                return levels

        # Strategy 2: Headings + lists
        for tag in section_content:
            if isinstance(tag, Tag):
                for heading_tag in tag.find_all(["h3", "h4", "h5", "strong", "b"]):
                    text = heading_tag.get_text(strip=True)
                    cat_match = re.match(
                        r"^(Harm\s+)?(Category\s+)?(\d|[123]|High|Medium|Low)", text, re.I
                    )
                    if cat_match:
                        factors = []
                        next_list = heading_tag.find_next("ul")
                        if next_list:
                            factors = [
                                li.get_text(strip=True) for li in next_list.find_all("li")
                            ]
                        levels.append(
                            HarmLevel(
                                category=cat_match.group(0).strip(),
                                description="",
                                factors=factors,
                            )
                        )

        return levels

    def _parse_harm_table(self, table: Tag) -> list[HarmLevel]:
        """Parse harm levels from a table."""
        levels = []
        for row in table.find_all("tr"):
            cells = row.find_all(["td", "th"])
            if len(cells) >= 2:
                cat_text = cells[0].get_text(strip=True)
                desc = cells[1].get_text(strip=True)
                factors = [li.get_text(strip=True) for li in cells[1].find_all("li")]
                if not factors:
                    factors = [desc] if desc else []

                if re.search(r"\d|High|Medium|Low", cat_text, re.I):
                    levels.append(
                        HarmLevel(category=cat_text, description=desc, factors=factors)
                    )

        return levels

    def _parse_sentencing_table(self) -> list[SentencingRange]:
        """Parse the sentencing starting points and ranges from Step 2."""
        ranges = []
        heading = self._find_section(
            "starting point", "step 2", "sentence", "category range"
        )

        content = self._get_main_content()

        # Find the sentencing table — it typically has culpability as columns
        # and harm as rows (or vice versa)
        for table in content.find_all("table"):
            table_text = table.get_text(strip=True).lower()
            if any(
                kw in table_text
                for kw in ("starting point", "category range", "custody", "fine", "community")
            ):
                parsed = self._parse_sentencing_grid(table)
                if parsed:
                    ranges.extend(parsed)
                    break

        return ranges

    def _parse_sentencing_grid(self, table: Tag) -> list[SentencingRange]:
        """Parse a sentencing grid table.

        These tables typically look like:

                     | Culpability A | Culpability B | Culpability C
        Harm Cat 1   | SP / Range    | SP / Range    | SP / Range
        Harm Cat 2   | SP / Range    | SP / Range    | SP / Range
        Harm Cat 3   | SP / Range    | SP / Range    | SP / Range

        But the exact format varies. Sometimes SP and Range are in separate rows.
        """
        ranges = []
        rows = table.find_all("tr")
        if not rows:
            return ranges

        # Try to identify column headers (culpability levels)
        header_row = rows[0]
        headers = [th.get_text(strip=True) for th in header_row.find_all(["th", "td"])]

        # Identify which columns are culpability levels
        culp_columns = {}
        for i, h in enumerate(headers):
            if re.search(r"[ABC]|High|Medium|Low|Lesser|Greater|Culpability", h, re.I):
                culp_columns[i] = h

        # Parse data rows
        current_harm = ""
        for row in rows[1:]:
            cells = row.find_all(["td", "th"])
            if not cells:
                continue

            cell_texts = [c.get_text(strip=True) for c in cells]

            # First cell is often the harm category
            first_cell = cell_texts[0] if cell_texts else ""
            if re.search(r"Category|Harm|Cat\s*\d|\d", first_cell, re.I):
                current_harm = first_cell

            # Try to extract starting point and range from cells
            for col_idx, culp_label in culp_columns.items():
                if col_idx < len(cell_texts):
                    cell_text = cell_texts[col_idx]

                    # Cell might contain both starting point and range
                    sp, cr = self._split_sp_and_range(cell_text)

                    if sp or cr:
                        ranges.append(
                            SentencingRange(
                                culpability=culp_label,
                                harm=current_harm or f"Row {rows.index(row)}",
                                starting_point=sp,
                                category_range=cr,
                            )
                        )

        # If the columnar approach didn't work, try a simpler row-based parse
        if not ranges:
            ranges = self._parse_sentencing_rows(rows)

        return ranges

    def _split_sp_and_range(self, text: str) -> tuple[str, str]:
        """Split a cell into starting point and category range.

        Common formats:
            "Starting point: X\nCategory range: Y"
            "X (range: Y)"
            Just "X" (starting point only)
        """
        sp, cr = "", ""

        # Pattern: "Starting point: X Category range: Y"
        sp_match = re.search(r"starting\s*point[:\s]*(.*?)(?:category\s*range|range|$)", text, re.I | re.S)
        cr_match = re.search(r"(?:category\s*)?range[:\s]*(.*?)$", text, re.I | re.S)

        if sp_match:
            sp = sp_match.group(1).strip().rstrip("–—- ")
        if cr_match:
            cr = cr_match.group(1).strip()

        # If no explicit labels, take the whole text as starting point
        if not sp and not cr:
            sp = text.strip()

        return sp, cr

    def _parse_sentencing_rows(self, rows: list[Tag]) -> list[SentencingRange]:
        """Fallback: parse sentencing as simple rows."""
        ranges = []

        for row in rows:
            cells = row.find_all(["td", "th"])
            texts = [c.get_text(strip=True) for c in cells]

            if len(texts) >= 3:
                ranges.append(
                    SentencingRange(
                        culpability=texts[0],
                        harm=texts[1] if len(texts) > 3 else "",
                        starting_point=texts[-2] if len(texts) > 2 else texts[-1],
                        category_range=texts[-1],
                    )
                )

        return ranges

    def _parse_factors(self, keyword: str) -> list[str]:
        """Parse aggravating or mitigating factors."""
        factors = []
        content = self._get_main_content()

        # Find sections containing the keyword
        for heading in content.find_all(["h2", "h3", "h4", "h5"]):
            if keyword.lower() in heading.get_text(strip=True).lower():
                # Gather list items from the following content
                for sibling in heading.find_next_siblings():
                    if sibling.name in ("h2", "h3") and sibling != heading:
                        break
                    if sibling.name == "ul" or sibling.name == "ol":
                        for li in sibling.find_all("li"):
                            text = li.get_text(strip=True)
                            if text:
                                factors.append(text)
                    elif sibling.name == "table":
                        for cell in sibling.find_all(["td", "li"]):
                            text = cell.get_text(strip=True)
                            if text and len(text) > 5:
                                factors.append(text)

        # Deduplicate while preserving order
        seen = set()
        unique = []
        for f in factors:
            if f not in seen:
                seen.add(f)
                unique.append(f)

        return unique

    def _parse_additional_steps(self) -> list[dict]:
        """Parse additional steps (guilty plea, totality, etc.)."""
        steps = []
        content = self._get_main_content()

        # Look for steps beyond step 2
        step_pattern = re.compile(r"step\s*(\d+)", re.I)
        for heading in content.find_all(["h2", "h3", "h4"]):
            text = heading.get_text(strip=True)
            match = step_pattern.search(text)
            if match and int(match.group(1)) > 2:
                step_content = []
                for sibling in heading.find_next_siblings():
                    if sibling.name in ("h2", "h3"):
                        break
                    step_content.append(sibling.get_text(strip=True))

                steps.append(
                    {
                        "step": int(match.group(1)),
                        "title": text,
                        "content": "\n".join(step_content),
                    }
                )

        return steps

    def _capture_raw_sections(self) -> dict:
        """Capture raw text of major sections as a fallback.

        This ensures we don't lose data even if the structured parsing
        misses something due to unexpected HTML layouts.
        """
        sections = {}
        content = self._get_main_content()

        current_section = "preamble"
        current_text = []

        for child in content.children:
            if isinstance(child, Tag) and child.name in ("h1", "h2", "h3"):
                if current_text:
                    sections[current_section] = "\n".join(current_text).strip()
                current_section = child.get_text(strip=True)
                current_text = []
            elif isinstance(child, Tag):
                text = child.get_text(strip=True)
                if text:
                    current_text.append(text)

        if current_text:
            sections[current_section] = "\n".join(current_text).strip()

        return sections
