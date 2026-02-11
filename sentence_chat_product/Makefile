PYTHONPATH ?= src

.PHONY: test etl load embed api

test:
	PYTHONPATH=$(PYTHONPATH) pytest -q

etl:
	PYTHONPATH=$(PYTHONPATH) python -m sentence_chat_product.etl.build_dataset \
	  --scraped-guidelines ../data/guidelines.json \
	  --scraped-pages ../data/pages.json \
	  --sentenceace /Users/duncancrawford/Downloads/sentenceACE.zip \
	  --output-dir ./build

load:
	PYTHONPATH=$(PYTHONPATH) python -m sentence_chat_product.etl.load_to_postgres --dataset-dir ./build

embed:
	PYTHONPATH=$(PYTHONPATH) python -m sentence_chat_product.etl.embed_chunks --limit 5000

api:
	PYTHONPATH=$(PYTHONPATH) uvicorn sentence_chat_product.api.main:app --reload --port 8010
