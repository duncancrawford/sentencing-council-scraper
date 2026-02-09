#!/usr/bin/env python3
"""
Diagnostic script: tests the updated crawler and dumps a single guideline
page structure so we can validate the parser.

Run: python debug_structure.py
"""

from scraper.crawler import SentencingCrawler
from scraper.parser import GuidelineParser


def main():
    crawler = SentencingCrawler(delay=0.5)

    # Step 1: Test offence discovery from the magistrates index
    print("=" * 80)
    print("Step 1: Discovering offences from magistrates index...")
    print("=" * 80)

    offences = crawler.discover_offences_from_index(
        "https://www.sentencingcouncil.org.uk/guidelines/magistrates/",
        "magistrates",
    )
    print(f"\nFound {len(offences)} offences")
    for o in offences[:10]:
        print(f"  [{o.court_type}] {o.name}")
        print(f"    Category: {o.category}")
        print(f"    URL: {o.url}")
    if len(offences) > 10:
        print(f"  ... and {len(offences) - 10} more")

    if not offences:
        print("\nNo offences found — check the crawler logic.")
        return

    # Step 2: Fetch the first guideline page and dump its structure
    print("\n" + "=" * 80)
    print("Step 2: Fetching a single guideline page to inspect structure...")
    print("=" * 80)

    test_url = offences[0].url
    print(f"\nFetching: {test_url}")

    soup = crawler.get_soup(test_url)
    parser = GuidelineParser(soup, test_url)
    content = parser._get_main_content()

    # Title
    h1 = content.find("h1") or soup.find("h1")
    print(f"\nH1: {h1.get_text(strip=True) if h1 else 'N/A'}")

    # All headings
    print("\n--- Headings ---")
    for h in content.find_all(["h1", "h2", "h3", "h4"]):
        text = h.get_text(strip=True)
        if text.lower() in ("give feedback about this page", "related content"):
            continue
        print(f"  <{h.name}> {text[:100]}")

    # Tabs / accordions / steps
    print("\n--- Tabs/Panels/Steps/Accordions ---")
    for el in content.find_all(
        lambda tag: any(
            kw in str(tag.get("class", "")).lower() + str(tag.get("id", "")).lower()
            for kw in ("tab", "panel", "step", "accordion")
        )
    )[:30]:
        el_id = el.get("id", "")
        el_class = el.get("class", [])
        text_preview = el.get_text(strip=True)[:100]
        print(f"  <{el.name} id='{el_id}' class='{el_class}'> {text_preview}")

    # Tables
    print("\n--- Tables ---")
    for i, table in enumerate(content.find_all("table")):
        rows = table.find_all("tr")
        print(f"\n  Table {i}: {len(rows)} rows")
        for row in rows[:5]:
            cells = row.find_all(["td", "th"])
            cell_texts = [c.get_text(strip=True)[:50] for c in cells]
            print(f"    | {'  |  '.join(cell_texts)} |")
        if len(rows) > 5:
            print(f"    ... {len(rows) - 5} more rows")

    # Lists that might be factors
    print("\n--- Unordered lists (possible factors) ---")
    for ul in content.find_all("ul")[:10]:
        prev = ul.find_previous(["h2", "h3", "h4", "strong"])
        heading = prev.get_text(strip=True)[:60] if prev else "(no heading)"
        items = ul.find_all("li")
        print(f"\n  Under '{heading}': {len(items)} items")
        for li in items[:3]:
            print(f"    - {li.get_text(strip=True)[:80]}")
        if len(items) > 3:
            print(f"    ... {len(items) - 3} more")

    # Dump main content HTML (first 8000 chars)
    print("\n--- Main content HTML (first 8000 chars) ---")
    if content:
        print(content.prettify()[:8000])


if __name__ == "__main__":
    main()
