#!/usr/bin/env bash
set -euo pipefail

ROOT="/Users/duncancrawford/development/workspace/hmcts/sentencing-council-scraper"
PROJECT="$ROOT/sentence_chat_product"

python -m sentence_chat_product.etl.build_dataset \
  --scraped-guidelines "$ROOT/data/guidelines.json" \
  --scraped-pages "$ROOT/data/pages.json" \
  --sentenceace "/Users/duncancrawford/Downloads/sentenceACE.zip" \
  --output-dir "$PROJECT/build"
