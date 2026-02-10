"""Load ETL JSONL artifacts into Postgres/Supabase."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

import psycopg
from psycopg.types.json import Json

from sentence_chat_product.config import get_settings

TABLE_CONFIG: dict[str, dict[str, Any]] = {
    "source_versions": {
        "columns": ["source_version_id", "source_name", "source_path", "source_hash", "metadata"],
        "json_fields": {"metadata"},
    },
    "offence_catalog": {
        "columns": [
            "offence_id",
            "canonical_name",
            "short_name",
            "offence_category",
            "provision",
            "guideline_url",
            "legislation_url",
            "maximum_sentence_type",
            "maximum_sentence_amount",
            "minimum_sentence_code",
            "specified_violent",
            "specified_sexual",
            "specified_terrorist",
            "listed_offence",
            "schedule18a_offence",
            "schedule19za",
            "cta_notification",
            "shpo",
            "disqualification",
            "safeguarding1",
            "safeguarding2",
            "safeguarding3",
            "safeguarding4",
            "source_payload",
        ],
        "json_fields": {"source_payload"},
    },
    "guidelines": {
        "columns": [
            "guideline_id",
            "slug",
            "offence_name",
            "url",
            "court_type",
            "category",
            "source_tab",
            "effective_from",
            "legislation_text",
            "source_payload",
        ],
        "json_fields": {"source_payload"},
    },
    "offence_guideline_links": {
        "columns": [
            "link_id",
            "offence_id",
            "guideline_id",
            "match_method",
            "match_confidence",
            "is_primary",
        ],
        "json_fields": set(),
    },
    "sentencing_matrix": {
        "columns": [
            "matrix_id",
            "guideline_id",
            "offence_id",
            "culpability",
            "harm",
            "starting_point_text",
            "category_range_text",
            "source_payload",
        ],
        "json_fields": {"source_payload"},
    },
    "guideline_factors": {
        "columns": [
            "factor_id",
            "guideline_id",
            "offence_id",
            "factor_type",
            "factor_text",
            "source_payload",
        ],
        "json_fields": {"source_payload"},
    },
    "guideline_chunks": {
        "columns": [
            "chunk_id",
            "guideline_id",
            "offence_id",
            "section_type",
            "section_heading",
            "chunk_index",
            "chunk_text",
            "token_estimate",
            "metadata",
            "source_url",
            "embedding",
        ],
        "json_fields": {"metadata"},
    },
}

TABLE_ORDER = [
    "source_versions",
    "offence_catalog",
    "guidelines",
    "offence_guideline_links",
    "sentencing_matrix",
    "guideline_factors",
    "guideline_chunks",
]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Load ETL artifacts into Postgres")
    parser.add_argument("--dataset-dir", type=Path, required=True, help="Path to ETL output directory")
    parser.add_argument(
        "--database-url",
        type=str,
        default=None,
        help="Database URL override; defaults to DATABASE_URL from env",
    )
    parser.add_argument(
        "--truncate",
        action="store_true",
        help="Truncate destination tables before load",
    )
    return parser.parse_args()


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if not line:
                continue
            rows.append(json.loads(line))
    return rows


def adapt_row(
    row: dict[str, Any],
    columns: list[str],
    json_fields: set[str],
) -> tuple[Any, ...]:
    out: list[Any] = []
    for col in columns:
        value = row.get(col)
        if col in json_fields:
            out.append(Json(value if value is not None else {}))
        else:
            out.append(value)
    return tuple(out)


def upsert_table(
    conn: psycopg.Connection,
    table: str,
    rows: list[dict[str, Any]],
    columns: list[str],
    json_fields: set[str],
) -> int:
    if not rows:
        return 0

    placeholders = ", ".join(["%s"] * len(columns))
    columns_sql = ", ".join(columns)

    update_cols = [col for col in columns if not col.endswith("_id")]
    set_clause = ", ".join([f"{col} = EXCLUDED.{col}" for col in update_cols])

    sql = (
        f"INSERT INTO {table} ({columns_sql}) VALUES ({placeholders}) "
        f"ON CONFLICT ({columns[0]}) DO UPDATE SET {set_clause}"
    )

    values = [adapt_row(row, columns, json_fields) for row in rows]

    with conn.cursor() as cur:
        cur.executemany(sql, values)

    conn.commit()
    return len(rows)


def maybe_truncate(conn: psycopg.Connection) -> None:
    sql = """
    TRUNCATE TABLE
      calculation_audit,
      guideline_chunks,
      guideline_factors,
      sentencing_matrix,
      offence_guideline_links,
      guidelines,
      offence_catalog,
      source_versions
    RESTART IDENTITY CASCADE;
    """
    with conn.cursor() as cur:
        cur.execute(sql)
    conn.commit()


def main() -> None:
    args = parse_args()
    settings = get_settings()
    database_url = args.database_url or settings.database_url

    if not args.dataset_dir.exists():
        raise FileNotFoundError(f"Dataset dir not found: {args.dataset_dir}")

    with psycopg.connect(database_url) as conn:
        if args.truncate:
            maybe_truncate(conn)

        counts: dict[str, int] = {}
        for table in TABLE_ORDER:
            file_path = args.dataset_dir / f"{table}.jsonl"
            if not file_path.exists():
                counts[table] = 0
                continue

            config = TABLE_CONFIG[table]
            rows = read_jsonl(file_path)
            loaded = upsert_table(
                conn,
                table,
                rows,
                config["columns"],
                config["json_fields"],
            )
            counts[table] = loaded

    print(json.dumps({"loaded": counts}, indent=2))


if __name__ == "__main__":
    main()
