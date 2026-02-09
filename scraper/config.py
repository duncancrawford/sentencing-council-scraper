"""Configuration for the Sentencing Council scraper."""

BASE_URL = "https://www.sentencingcouncil.org.uk"

# Index pages — offence data is embedded as JSON in a <script> tag
# inside tab-panel-0 on each of these pages.
INDEX_URLS = {
    "magistrates": f"{BASE_URL}/guidelines/magistrates/",
    "crown_court": f"{BASE_URL}/guidelines/crown-court/",
}

# Request settings
REQUEST_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-GB,en;q=0.9",
    "Accept-Encoding": "gzip, deflate, br",
}

# Be polite — delay between requests in seconds
REQUEST_DELAY = 1.0

# Retry settings
MAX_RETRIES = 3
RETRY_BACKOFF = 2.0  # exponential backoff multiplier

# Output
OUTPUT_DIR = "data"
