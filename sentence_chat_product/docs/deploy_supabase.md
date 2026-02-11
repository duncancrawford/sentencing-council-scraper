# Deploy to Supabase

## 1) Create Postgres objects

Run `/Users/duncancrawford/development/workspace/hmcts/sentencing-council-scraper/sentence_chat_product/src/sentence_chat_product/db/schema.sql` in Supabase SQL editor.

## 2) Build normalized dataset

```bash
cd /Users/duncancrawford/development/workspace/hmcts/sentencing-council-scraper/sentence_chat_product
PYTHONPATH=src python -m sentence_chat_product.etl.build_dataset \
  --scraped-guidelines /Users/duncancrawford/development/workspace/hmcts/sentencing-council-scraper/data/guidelines.json \
  --scraped-pages /Users/duncancrawford/development/workspace/hmcts/sentencing-council-scraper/data/pages.json \
  --sentenceace /Users/duncancrawford/Downloads/sentenceACE.zip \
  --output-dir /Users/duncancrawford/development/workspace/hmcts/sentencing-council-scraper/sentence_chat_product/build
```

## 3) Load into Supabase Postgres

```bash
export DATABASE_URL="postgresql://<user>:<pass>@<host>:5432/postgres?sslmode=require"
PYTHONPATH=src python -m sentence_chat_product.etl.load_to_postgres --dataset-dir ./build
```

Optional (vector retrieval):

```bash
export OPENAI_API_KEY="..."
PYTHONPATH=src python -m sentence_chat_product.etl.embed_chunks --limit 10000
```

## 4) Run API

```bash
export DATABASE_URL="postgresql://<user>:<pass>@<host>:5432/postgres?sslmode=require"
export OPENAI_API_KEY="..."  # optional but recommended for vector retrieval
PYTHONPATH=src uvicorn sentence_chat_product.api.main:app --host 0.0.0.0 --port 8010
```

## 5) Connect ChatGPT Actions

- Action OpenAPI URL: `https://<your-api>/openapi.json`
- Expose endpoints:
  - `POST /v1/calculate_sentence`
  - `POST /v1/search_guidelines`

