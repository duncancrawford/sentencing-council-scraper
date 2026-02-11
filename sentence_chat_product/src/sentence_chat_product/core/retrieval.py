"""Guideline retrieval service."""

from __future__ import annotations

from typing import Any

from openai import OpenAI

from sentence_chat_product.config import Settings
from sentence_chat_product.db.repository import Repository


class RetrievalService:
    """Hybrid retrieval over guideline chunks."""

    def __init__(self, repository: Repository, settings: Settings):
        self.repository = repository
        self.settings = settings
        self._client = OpenAI(api_key=settings.openai_api_key) if settings.openai_api_key else None

    def search(self, query: str, offence_id: str | None = None, top_k: int | None = None) -> list[dict[str, Any]]:
        k = top_k or self.settings.retrieval_top_k
        embedding = None

        if self.settings.enable_vector_search and self._client:
            embedding = self._embed(query)

        rows = self.repository.search_guideline_chunks(
            query_text=query,
            top_k=k,
            offence_id=offence_id,
            query_embedding=embedding,
        )
        return rows

    def _embed(self, query: str) -> list[float] | None:
        if not self._client:
            return None
        response = self._client.embeddings.create(
            model=self.settings.openai_embedding_model,
            input=[query],
        )
        if not response.data:
            return None
        return response.data[0].embedding
