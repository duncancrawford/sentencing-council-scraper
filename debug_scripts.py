#!/usr/bin/env python3
"""Quick diagnostic: what do the script tags actually look like?"""

import requests
from bs4 import BeautifulSoup

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    ),
}

url = "https://www.sentencingcouncil.org.uk/guidelines/magistrates/"
r = requests.get(url, headers=HEADERS, timeout=15)
print(f"Status: {r.status_code}")
print(f"Content length: {len(r.text)}")

# Check if guidelineData appears in the raw HTML at all
raw = r.text
idx = raw.find("guidelineData")
if idx >= 0:
    print(f"\n'guidelineData' found in raw HTML at position {idx}")
    print(f"Context (200 chars around it):")
    print(raw[max(0, idx - 50) : idx + 150])
else:
    print("\n'guidelineData' NOT found in raw HTML at all")

# Now check BeautifulSoup parsing
soup = BeautifulSoup(r.text, "lxml")

print(f"\n--- All <script> tags ---")
scripts = soup.find_all("script")
print(f"Total script tags: {len(scripts)}")

for i, script in enumerate(scripts):
    src = script.get("src", "")
    has_string = script.string is not None
    text_len = len(script.get_text()) if script.get_text() else 0
    string_len = len(script.string) if script.string else 0

    print(f"\n  Script {i}: src='{src}' .string={has_string} (len={string_len}) .get_text() len={text_len}")

    # Check for guidelineData in each
    content = script.string or script.get_text() or ""
    if "guidelineData" in content:
        print(f"    >>> CONTAINS guidelineData!")
        print(f"    First 200 chars: {content[:200]}")
    elif text_len > 0:
        print(f"    First 100 chars: {content[:100]}")

# Also try html.parser instead of lxml
print("\n\n--- Trying with html.parser instead of lxml ---")
soup2 = BeautifulSoup(r.text, "html.parser")
for i, script in enumerate(soup2.find_all("script")):
    content = script.string or script.get_text() or ""
    if "guidelineData" in content:
        print(f"  Script {i}: CONTAINS guidelineData! Length={len(content)}")
        print(f"  First 200 chars: {content[:200]}")
        break
else:
    print("  guidelineData not found in any script tag with html.parser either")

    # Check if it's in a specific div
    panel = soup2.find(id="tab-panel-0")
    if panel:
        panel_text = str(panel)
        if "guidelineData" in panel_text:
            idx = panel_text.find("guidelineData")
            print(f"\n  But found in tab-panel-0 raw HTML at pos {idx}")
            print(f"  Context: {panel_text[max(0,idx-50):idx+150]}")
