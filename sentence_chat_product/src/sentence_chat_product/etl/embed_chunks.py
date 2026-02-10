"""Generate embeddings for guideline chunks already loaded into Postgres."""

from __future__ import annotations

import argparse
import json

import psycopg
from openai import OpenAI
from pgvector.psycopg import register_vector

from sentence_chat_product.config import get_settings


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Embed guideline chunks in Postgres")
    parser.add_argument("--database-url", type=str, default=None)
    parser.add_argument("--model", type=str, default=None)
    parser.add_argument("--batch-size", type=int, default=64)
    parser.add_argument("--limit", type=int, default=2000)
    return parser.parse_args()


def fetch_rows(
    conn: psycopg.Connection,
    batch_size: int,
) -> list[tuple[str, str]]:
    sql = """
    SELECT chunk_id::text, chunk_text
    FROM guideline_chunks
    WHERE embedding IS NULL
    ORDER BY created_at ASC
    LIMIT %s;
    """
    with conn.cursor() as cur:
        cur.execute(sql, (batch_size,))
        return [(row[0], row[1]) for row in cur.fetchall()]


def update_rows(
    conn: psycopg.Connection,
    rows: list[tuple[list[float], str]],
) -> None:
    sql = "UPDATE guideline_chunks SET embedding = %s WHERE chunk_id = %s::uuid"
    with conn.cursor() as cur:
        cur.executemany(sql, rows)
    conn.commit()


def main() -> None:
    args = parse_args()
    settings = get_settings()

    if not settings.openai_api_key:
        raise ValueError("OPENAI_API_KEY is required for embedding")

    database_url = args.database_url or settings.database_url
    model = args.model or settings.openai_embedding_model

    client = OpenAI(api_key=settings.openai_api_key)
    processed = 0

    with psycopg.connect(database_url) as conn:
        register_vector(conn)

        while processed < args.limit:
            remaining = args.limit - processed
            rows = fetch_rows(conn, min(args.batch_size, remaining))
            if not rows:
                break

            texts = [row[1] for row in rows]
            response = client.embeddings.create(model=model, input=texts)
            vectors = [item.embedding for item in response.data]

            updates = [(vectors[i], rows[i][0]) for i in range(len(rows))]
            update_rows(conn, updates)
            processed += len(rows)

    print(json.dumps({"embedded_rows": processed, "model": model}, indent=2))


if __name__ == "__main__":
    main()
