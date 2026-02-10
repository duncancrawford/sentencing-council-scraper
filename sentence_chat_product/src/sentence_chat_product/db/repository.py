"""Database access layer."""

from __future__ import annotations

from contextlib import contextmanager
from typing import Any, Iterator

import psycopg
from pgvector.psycopg import register_vector
from psycopg.rows import dict_row
from psycopg.types.json import Json

from sentence_chat_product.core.types import OffenceRecord


class Repository:
    """Thin repository around Postgres queries."""

    def __init__(self, database_url: str):
        self.database_url = database_url

    @contextmanager
    def connect(self) -> Iterator[psycopg.Connection]:
        with psycopg.connect(self.database_url, row_factory=dict_row) as conn:
            register_vector(conn)
            yield conn

    def fetch_offence_by_id(self, offence_id: str) -> OffenceRecord | None:
        sql = "SELECT * FROM offence_catalog WHERE offence_id = %s::uuid"
        with self.connect() as conn, conn.cursor() as cur:
            cur.execute(sql, (offence_id,))
            row = cur.fetchone()
            return self._to_offence_record(row) if row else None

    def search_offences(self, query: str, limit: int = 5) -> list[OffenceRecord]:
        sql = """
        SELECT *,
          greatest(
            similarity(canonical_name, %(q)s),
            similarity(coalesce(short_name, ''), %(q)s),
            similarity(coalesce(provision, ''), %(q)s)
          ) as score
        FROM offence_catalog
        ORDER BY score DESC, canonical_name ASC
        LIMIT %(limit)s;
        """
        with self.connect() as conn, conn.cursor() as cur:
            cur.execute(sql, {"q": query, "limit": limit})
            rows = cur.fetchall()
        return [self._to_offence_record(row) for row in rows if row]

    def fetch_sentencing_matrix(self, offence_id: str) -> list[dict[str, Any]]:
        sql = """
        SELECT DISTINCT ON (sm.matrix_id)
          sm.matrix_id::text,
          sm.guideline_id::text,
          sm.offence_id::text,
          sm.culpability,
          sm.harm,
          sm.starting_point_text,
          sm.category_range_text
        FROM sentencing_matrix sm
        LEFT JOIN offence_guideline_links ogl
          ON ogl.guideline_id = sm.guideline_id
        WHERE sm.offence_id = %(offence_id)s::uuid
           OR ogl.offence_id = %(offence_id)s::uuid
        ORDER BY sm.matrix_id, sm.guideline_id;
        """
        with self.connect() as conn, conn.cursor() as cur:
            cur.execute(sql, {"offence_id": offence_id})
            return [dict(row) for row in cur.fetchall()]

    def search_guideline_chunks(
        self,
        query_text: str,
        top_k: int,
        offence_id: str | None = None,
        query_embedding: list[float] | None = None,
    ) -> list[dict[str, Any]]:
        if query_embedding is not None:
            return self._search_guideline_chunks_hybrid(
                query_text=query_text,
                top_k=top_k,
                offence_id=offence_id,
                query_embedding=query_embedding,
            )

        return self._search_guideline_chunks_text_only(
            query_text=query_text,
            top_k=top_k,
            offence_id=offence_id,
        )

    def _search_guideline_chunks_hybrid(
        self,
        query_text: str,
        top_k: int,
        offence_id: str | None,
        query_embedding: list[float],
    ) -> list[dict[str, Any]]:
        sql = """
        SELECT
          gc.chunk_id::text,
          gc.guideline_id::text,
          gc.offence_id::text,
          gc.section_type,
          gc.section_heading,
          gc.chunk_text,
          gc.source_url,
          coalesce(1 - (gc.embedding <=> %(embedding)s::vector), 0) AS vector_score,
          ts_rank_cd(gc.tsv, plainto_tsquery('english', %(query)s)) AS text_score,
          (
            coalesce(1 - (gc.embedding <=> %(embedding)s::vector), 0) * 0.75
            + ts_rank_cd(gc.tsv, plainto_tsquery('english', %(query)s)) * 0.25
          ) AS score
        FROM guideline_chunks gc
        WHERE (
          %(offence_id)s::uuid IS NULL
          OR gc.offence_id = %(offence_id)s::uuid
          OR gc.guideline_id IN (
            SELECT guideline_id FROM offence_guideline_links WHERE offence_id = %(offence_id)s::uuid
          )
        )
        ORDER BY score DESC
        LIMIT %(top_k)s;
        """
        params = {
            "embedding": query_embedding,
            "query": query_text,
            "offence_id": offence_id,
            "top_k": top_k,
        }

        with self.connect() as conn, conn.cursor() as cur:
            cur.execute(sql, params)
            return [dict(row) for row in cur.fetchall()]

    def _search_guideline_chunks_text_only(
        self,
        query_text: str,
        top_k: int,
        offence_id: str | None,
    ) -> list[dict[str, Any]]:
        sql = """
        SELECT
          gc.chunk_id::text,
          gc.guideline_id::text,
          gc.offence_id::text,
          gc.section_type,
          gc.section_heading,
          gc.chunk_text,
          gc.source_url,
          ts_rank_cd(gc.tsv, plainto_tsquery('english', %(query)s)) AS score
        FROM guideline_chunks gc
        WHERE (
          %(offence_id)s::uuid IS NULL
          OR gc.offence_id = %(offence_id)s::uuid
          OR gc.guideline_id IN (
            SELECT guideline_id FROM offence_guideline_links WHERE offence_id = %(offence_id)s::uuid
          )
        )
        ORDER BY score DESC, similarity(gc.chunk_text, %(query)s) DESC
        LIMIT %(top_k)s;
        """
        params = {
            "query": query_text,
            "offence_id": offence_id,
            "top_k": top_k,
        }
        with self.connect() as conn, conn.cursor() as cur:
            cur.execute(sql, params)
            return [dict(row) for row in cur.fetchall()]

    def store_calculation_audit(
        self,
        offence_id: str | None,
        request_payload: dict[str, Any],
        result_payload: dict[str, Any],
    ) -> None:
        sql = """
        INSERT INTO calculation_audit (offence_id, request_payload, result_payload)
        VALUES (%(offence_id)s::uuid, %(request_payload)s::jsonb, %(result_payload)s::jsonb)
        """
        params = {
            "offence_id": offence_id,
            "request_payload": Json(request_payload),
            "result_payload": Json(result_payload),
        }
        with self.connect() as conn, conn.cursor() as cur:
            cur.execute(sql, params)
            conn.commit()

    @staticmethod
    def _to_offence_record(row: dict[str, Any]) -> OffenceRecord:
        return OffenceRecord(
            offence_id=str(row["offence_id"]),
            canonical_name=row["canonical_name"],
            short_name=row["short_name"],
            offence_category=row.get("offence_category") or "",
            provision=row.get("provision") or "",
            guideline_url=row.get("guideline_url") or "",
            legislation_url=row.get("legislation_url") or "",
            maximum_sentence_type=row.get("maximum_sentence_type") or "",
            maximum_sentence_amount=row.get("maximum_sentence_amount") or "",
            minimum_sentence_code=row.get("minimum_sentence_code") or "",
            specified_violent=bool(row.get("specified_violent")),
            specified_sexual=bool(row.get("specified_sexual")),
            specified_terrorist=bool(row.get("specified_terrorist")),
            listed_offence=bool(row.get("listed_offence")),
            schedule18a_offence=bool(row.get("schedule18a_offence")),
            schedule19za=bool(row.get("schedule19za")),
            cta_notification=bool(row.get("cta_notification")),
        )
