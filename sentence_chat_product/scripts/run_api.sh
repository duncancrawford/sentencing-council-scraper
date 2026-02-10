#!/usr/bin/env bash
set -euo pipefail

uvicorn sentence_chat_product.api.main:app --reload --host 0.0.0.0 --port 8010
