# Sentencing Council Guideline Scraper

A web crawler that extracts structured sentencing guideline data from the [UK Sentencing Council](https://www.sentencingcouncil.org.uk/) website.

Built to feed data into the [sentence calculator prototype](https://github.com/TimBrittenMOJ/sentence_builder), replacing hard-coded static data with comprehensive coverage of all offence types.

## What it does

The scraper crawls the Sentencing Council's magistrates' court and Crown Court guideline pages and extracts:

- **Offence names** and legislation references
- **Culpability levels** (A/B/C or High/Medium/Low) with factors
- **Harm categories** with factors
- **Sentencing tables** — starting points and category ranges for each culpability/harm combination
- **Aggravating factors**
- **Mitigating factors**
- **Additional steps** (guilty plea reduction, totality, ancillary orders, etc.)

Output is JSON (per offence + combined), plus a CSV summary of all sentencing ranges. Supplementary and overarching pages are exported separately, and a unified `pages.json` provides a consistent API-friendly envelope.

## Publish to Supabase Storage

The workflow **Publish data to Supabase Storage** runs the scraper and uploads the `data/` folder to a Supabase Storage bucket using the S3-compatible endpoint.

Required GitHub secrets:

- `SUPABASE_S3_ENDPOINT` (e.g. `https://<project-ref>.supabase.co/storage/v1/s3`)
- `SUPABASE_ACCESS_KEY`
- `SUPABASE_SECRET_KEY`
- `SUPABASE_BUCKET`
- `SUPABASE_PREFIX` (optional folder prefix inside the bucket)
- `SUPABASE_REGION` (optional, defaults to `us-east-1`)

If the bucket is public, files are accessible at:

- `https://<project-ref>.supabase.co/storage/v1/object/public/<bucket>/<prefix>/pages.json`
- `https://<project-ref>.supabase.co/storage/v1/object/public/<bucket>/<prefix>/guidelines.json`
- `https://<project-ref>.supabase.co/storage/v1/object/public/<bucket>/<prefix>/supplementary.json`
- `https://<project-ref>.supabase.co/storage/v1/object/public/<bucket>/<prefix>/overarching.json`

To run it immediately, trigger the workflow manually in GitHub Actions.

Note: the workflow uploads JSON files only. If you want CSVs too, allow `text/csv` in the bucket MIME type settings and add a CSV upload step.

## Setup

```bash
python -m venv venv
source venv/bin/activate  # or venv\Scripts\activate on Windows
pip install -r requirements.txt
```

## Usage

```bash
# Scrape all guidelines (magistrates + Crown Court)
python main.py

# Scrape only magistrates' court guidelines
python main.py --court magistrates

# Scrape only Crown Court guidelines
python main.py --court crown

# Just list discovered offences without scraping detail pages
python main.py --list-only

# Limit the number of items processed (after discovery/filtering)
python main.py --limit 5

# Limit by tab type (default: offences)
python main.py --tab supplementary --limit 5
python main.py --tab overarching --limit 5
python main.py --tab all --limit 5

# Scrape a single guideline page
python main.py --url https://www.sentencingcouncil.org.uk/offences/crown-court/item/assault-occasioning-actual-bodily-harm/

# Custom output directory and delay between requests
python main.py --output my_data --delay 2.0

# Verbose logging
python main.py -v
```

## Output

All output goes to the `data/` directory by default:

| File | Description |
|------|-------------|
| `guidelines.json` | All guidelines in a single JSON array |
| `guidelines/<offence>.json` | Individual JSON file per offence |
| `sentencing_ranges.csv` | Flat CSV of all sentencing ranges (useful for analysis) |
| `offence_index.json` | Summary index of all offences found |
| `supplementary.json` | Supplementary information pages (structured sections) |
| `supplementary/<page>.json` | Individual supplementary pages |
| `overarching.json` | Overarching guideline pages (structured sections) |
| `overarching/<page>.json` | Individual overarching pages |
| `pages.json` | Unified envelope for API use (offence + supplementary + overarching) |
| `errors.json` | Any offences that failed to scrape |

### JSON structure

Each guideline in the JSON output looks like:

```json
{
  "offence_name": "Common assault",
  "url": "https://www.sentencingcouncil.org.uk/offences/...",
  "court_type": "magistrates",
  "legislation": "Criminal Justice Act 1988, s.39",
  "culpability_levels": [
    {
      "level": "A",
      "description": "High culpability",
      "factors": ["Use of weapon", "Targeting vulnerable victim", "..."]
    }
  ],
  "harm_levels": [
    {
      "category": "1",
      "description": "...",
      "factors": ["Serious physical injury", "..."]
    }
  ],
  "sentencing_ranges": [
    {
      "culpability": "A",
      "harm": "Category 1",
      "starting_point": "1 year's custody",
      "category_range": "26 weeks' – 2 years' custody"
    }
  ],
  "aggravating_factors": ["Previous convictions", "..."],
  "mitigating_factors": ["No previous convictions", "..."],
  "additional_steps": [],
  "raw_sections": {}
}
```

### Unified pages.json structure

Each item in `pages.json` uses a common envelope with a type-specific payload:

```json
{
  "schema_version": 1,
  "page_type": "offence",
  "title": "Common assault",
  "url": "https://www.sentencingcouncil.org.uk/...",
  "court_type": "magistrates",
  "source_tab": "Offences",
  "category": "Assault offences",
  "guideline": { "...": "offence-specific fields" },
  "sections": []
}
```

```json
{
  "schema_version": 1,
  "page_type": "supplementary",
  "title": "Ancillary orders",
  "url": "https://www.sentencingcouncil.org.uk/supplementary-information/ancillary-orders/",
  "court_type": "magistrates",
  "source_tab": "Supplementary information",
  "category": "Supplementary information",
  "guideline": null,
  "sections": [
    {
      "heading": "Eligibility",
      "level": "h2",
      "text": "...",
      "bullets": ["..."],
      "tables": [[["Col 1", "Col 2"], ["...","..."]]]
    }
  ]
}
```

## Why Beautiful Soup?

The Sentencing Council site serves static HTML, so a full browser automation tool (Selenium/Playwright) isn't needed. `requests` + `BeautifulSoup` with `lxml` is fast, lightweight, and sufficient.

The main challenge is that the HTML structure varies between offences — some use tables for culpability/harm, others use headings and lists, and some use accordion/tab layouts. The parser uses multiple strategies with fallbacks to handle this.

If the site ever moves to client-side rendering, swap in `httpx` + `playwright` — the parser layer stays the same.

## Architecture

```
scraper/
├── config.py    # URLs, headers, rate limiting settings
├── models.py    # Dataclasses: Guideline, SentencingRange, etc.
├── crawler.py   # Page discovery — finds all offence links
├── parser.py    # HTML parsing — extracts structured data
└── export.py    # JSON/CSV output
main.py          # CLI entry point
```

## Notes

- The scraper includes a 1-second delay between requests by default (configurable via `--delay`). Be respectful of the Sentencing Council's servers.
- The `raw_sections` field in each guideline captures all section text as a fallback, so data isn't lost even when the structured parser can't match the HTML layout.
- The site structure may change over time. If the scraper stops finding offences, check the index page URLs in `scraper/config.py` and the link-matching logic in `scraper/crawler.py`.
