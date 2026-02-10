# Sentence Chat Product (Standalone)

This folder contains a standalone MVP for building a sentencing-calculation product for chat clients.

It combines:
- A **deterministic rules engine** (from `sentenceACE_spec.md`)
- A **retrieval layer** over scraped guideline text (for explanations and citations)
- A **FastAPI service** with endpoints suitable for ChatGPT Actions or your own chat backend

All code is isolated under this new root so you can move it later.

## What this includes

- `src/sentence_chat_product/db/schema.sql`
  - Postgres/Supabase schema (`offence_catalog`, `guidelines`, `offence_guideline_links`, `sentencing_matrix`, `guideline_chunks`)
- `src/sentence_chat_product/etl/build_dataset.py`
  - Normalizes and merges:
    - scraped data (`data/guidelines.json`, optional `data/pages.json`)
    - `sentenceACE` offences (`sentenceACE.zip` or `offences.json`)
- `src/sentence_chat_product/etl/load_to_postgres.py`
  - Loads the generated JSONL artifacts into Postgres/Supabase
- `src/sentence_chat_product/core/rules.py`
  - Deterministic sentence logic: validation, minimum sentence rules, plea reduction, release point, victim surcharge
- `src/sentence_chat_product/api/main.py`
  - API endpoints:
    - `POST /v1/calculate_sentence`
    - `POST /v1/search_guidelines`
    - `POST /v1/chat_turn`

## Quick start

```bash
cd /Users/duncancrawford/development/workspace/hmcts/sentencing-council-scraper/sentence_chat_product
python -m venv .venv
source .venv/bin/activate
pip install -e .[dev]
```

### 1) Build normalized dataset

```bash
python -m sentence_chat_product.etl.build_dataset \
  --scraped-guidelines /Users/duncancrawford/development/workspace/hmcts/sentencing-council-scraper/data/guidelines.json \
  --scraped-pages /Users/duncancrawford/development/workspace/hmcts/sentencing-council-scraper/data/pages.json \
  --sentenceace /Users/duncancrawford/Downloads/sentenceACE.zip \
  --output-dir /Users/duncancrawford/development/workspace/hmcts/sentencing-council-scraper/sentence_chat_product/build
```

Outputs in `build/`:
- `offence_catalog.jsonl`
- `guidelines.jsonl`
- `offence_guideline_links.jsonl`
- `sentencing_matrix.jsonl`
- `guideline_factors.jsonl`
- `guideline_chunks.jsonl`
- `etl_report.json`

### 2) Apply DB schema

Run `src/sentence_chat_product/db/schema.sql` against your Supabase/Postgres database.

### 3) Load dataset into DB

```bash
export DATABASE_URL="postgresql://..."
python -m sentence_chat_product.etl.load_to_postgres \
  --dataset-dir /Users/duncancrawford/development/workspace/hmcts/sentencing-council-scraper/sentence_chat_product/build
```

### 4) Start API

```bash
export DATABASE_URL="postgresql://..."
# Optional: for embedding-based retrieval and optional LLM response generation
export OPENAI_API_KEY="..."

uvicorn sentence_chat_product.api.main:app --reload --port 8010
```

API docs:
- `http://localhost:8010/docs`

## ChatGPT integration path

Use this API as ChatGPT Actions tools:

- `POST /v1/calculate_sentence`
- `POST /v1/search_guidelines`

Recommended flow in chat product:
1. Ask user for missing structured facts.
2. Call `calculate_sentence` for deterministic result.
3. Call `search_guidelines` for supporting authority text.
4. Return answer with citations.

## Notes on current coverage

- This MVP implements core rules from the reverse-engineered spec, including:
  - minimum sentence groups `A/B/C1/C2/C3/C4/D/E`
  - release point logic (with optional sentenceACE inconsistency toggle)
  - plea discounts
  - victim surcharge date bands
- It does **not** yet implement every multi-count edge case from legacy UI behavior.

## Tests

```bash
pytest
```

