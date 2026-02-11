# Local Run Summary

This documents the exact steps used to get the sentence chat product running locally against Supabase Postgres.

## 1) Go to project and create virtual environment

```bash
cd /Users/duncancrawford/development/workspace/hmcts/sentencing-council-scraper/sentence_chat_product
python -m venv .venv
source .venv/bin/activate
pip install -e '.[dev]'
```

Notes:
- On `zsh`, `pip install -e .[dev]` fails due shell expansion. Use quotes: `'.[dev]'`.

## 2) Apply DB schema in Supabase

Run this file in Supabase SQL Editor:

`/Users/duncancrawford/development/workspace/hmcts/sentencing-council-scraper/sentence_chat_product/src/sentence_chat_product/db/schema.sql`

Expected warning in Supabase UI:
- "Query has destructive operation" is expected because the schema contains `drop trigger if exists ...`.

## 3) Build normalized dataset

```bash
PYTHONPATH=src python -m sentence_chat_product.etl.build_dataset \
  --scraped-guidelines /Users/duncancrawford/development/workspace/hmcts/sentencing-council-scraper/data/guidelines.json \
  --scraped-pages /Users/duncancrawford/development/workspace/hmcts/sentencing-council-scraper/data/pages.json \
  --sentenceace /Users/duncancrawford/Downloads/sentenceACE.zip \
  --output-dir /Users/duncancrawford/development/workspace/hmcts/sentencing-council-scraper/sentence_chat_product/build
```

## 4) Configure Supabase connection

Use the Supabase pooler URL in `DATABASE_URL`.

Example shape:

```bash
export DATABASE_URL='postgresql://postgres.<project-ref>:<password>@aws-1-eu-central-1.pooler.supabase.com:5432/postgres?sslmode=require'
```

Notes:
- Wrong username/password will fail authentication.
- If password contains special characters, URL-encode it.
- Confirm active URL values in shell before running loaders.

## 5) Load data into Supabase

```bash
PYTHONPATH=src python -m sentence_chat_product.etl.load_to_postgres \
  --dataset-dir /Users/duncancrawford/development/workspace/hmcts/sentencing-council-scraper/sentence_chat_product/build \
  --truncate
```

Working load output observed:

```json
{
  "loaded": {
    "source_versions": 3,
    "offence_catalog": 912,
    "guidelines": 252,
    "offence_guideline_links": 296,
    "sentencing_matrix": 4257,
    "guideline_factors": 9553,
    "guideline_chunks": 12212
  }
}
```

## 6) Generate embeddings (recommended)

```bash
export OPENAI_API_KEY='sk-...'
PYTHONPATH=src python -m sentence_chat_product.etl.embed_chunks --limit 12212
```

## 7) Start API locally

```bash
PYTHONPATH=src python -m uvicorn sentence_chat_product.api.main:app --host 127.0.0.1 --port 8010 --log-level debug
```

Expected startup logs include:
- `Application startup complete`
- `Uvicorn running on http://127.0.0.1:8010`

## 8) Validate endpoints

### Health

```bash
curl http://127.0.0.1:8010/v1/health
```

Expected:

```json
{"status":"ok"}
```

### Search

```bash
curl -s -X POST http://127.0.0.1:8010/v1/search_guidelines \
  -H "Content-Type: application/json" \
  -d '{"query":"common assault starting point category range", "top_k": 5}' | jq .
```

### Calculate sentence

```bash
curl -s -X POST http://127.0.0.1:8010/v1/calculate_sentence \
  -H "Content-Type: application/json" \
  -d '{
    "offence_query":"common assault",
    "offence_date":"2024-01-10",
    "conviction_date":"2024-02-15",
    "sentence_date":"2024-03-01",
    "age_at_offence":30,
    "age_at_conviction":30,
    "age_at_sentence":30,
    "plea_stage":"first_stage",
    "sentence_type":"determinate_custodial_sentence",
    "pre_plea_term_months":12
  }' | jq .
```

### Calculate sentence (turn off sentenceACE release inconsistency)

```bash
curl -s -X POST http://127.0.0.1:8010/v1/calculate_sentence \
  -H "Content-Type: application/json" \
  -d '{
    "offence_query":"common assault",
    "offence_date":"2024-01-10",
    "conviction_date":"2024-02-15",
    "sentence_date":"2024-03-01",
    "age_at_offence":30,
    "age_at_conviction":30,
    "age_at_sentence":30,
    "plea_stage":"first_stage",
    "sentence_type":"determinate_custodial_sentence",
    "pre_plea_term_months":12,
    "replicate_ace_release_bug":false
  }' | jq .
```

## Troubleshooting that occurred

- `ModuleNotFoundError: psycopg`
  - Fix: install dependencies in `.venv` with `pip install -e '.[dev]'`.
- `nodename nor servname provided, or not known`
  - Fix: use Supabase pooler host instead of unresolved direct host.
- `password authentication failed`
  - Fix: correct DB username/password in `DATABASE_URL`.
- `duplicate key value violates unique constraint "guidelines_slug_key"`
  - Fixed in ETL by canonicalizing URLs before guideline dedupe/ID generation.

