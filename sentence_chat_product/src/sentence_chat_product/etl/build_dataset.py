"""Build normalized dataset artifacts for the sentence chat product."""

from __future__ import annotations

import argparse
import json
from collections import defaultdict
from pathlib import Path
from typing import Any

try:
    from rapidfuzz import fuzz, process
except ImportError:  # pragma: no cover - fallback for minimal environments
    from difflib import SequenceMatcher

    class _FallbackFuzz:
        @staticmethod
        def token_set_ratio(a: str, b: str) -> float:
            a_tokens = " ".join(sorted(set(a.split())))
            b_tokens = " ".join(sorted(set(b.split())))
            return SequenceMatcher(None, a_tokens, b_tokens).ratio() * 100

    class _FallbackProcess:
        @staticmethod
        def extractOne(query: str, choices: list[str], scorer) -> tuple[str, float, int] | None:
            if not choices:
                return None
            best_choice = choices[0]
            best_score = scorer(query, best_choice)
            best_index = 0
            for idx, choice in enumerate(choices[1:], start=1):
                score = scorer(query, choice)
                if score > best_score:
                    best_choice = choice
                    best_score = score
                    best_index = idx
            return best_choice, best_score, best_index

    fuzz = _FallbackFuzz()
    process = _FallbackProcess()

from .utils import (
    canonicalize_url,
    chunk_text,
    estimate_tokens,
    extract_slug_from_url,
    hash_file,
    normalize_name_for_match,
    normalize_slug,
    normalize_space,
    read_json_from_zip_or_file,
    short_offence_name,
    stable_uuid,
    yes_no_to_bool,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build normalized dataset for sentence chat product")
    parser.add_argument(
        "--scraped-guidelines",
        required=True,
        type=Path,
        help="Path to scraped guidelines.json",
    )
    parser.add_argument(
        "--scraped-pages",
        required=False,
        type=Path,
        help="Optional path to pages.json",
    )
    parser.add_argument(
        "--sentenceace",
        required=True,
        type=Path,
        help="Path to sentenceACE zip or offences.json",
    )
    parser.add_argument(
        "--output-dir",
        required=True,
        type=Path,
        help="Directory where JSONL artifacts are written",
    )
    parser.add_argument(
        "--fuzzy-threshold",
        type=int,
        default=90,
        help="Minimum fuzzy match score for linking unmapped offences",
    )
    return parser.parse_args()


def load_json(path: Path) -> list[dict[str, Any]]:
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    with path.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=False) + "\n")


def cleaned_legislation(text: str) -> str:
    value = normalize_space(text)
    if not value:
        return ""
    if len(value) <= 800:
        return value
    marker = value.lower().find("step 1")
    if marker > 80:
        value = value[:marker]
    return value[:800]


def guideline_doc_from_offence_guideline(item: dict[str, Any]) -> dict[str, Any]:
    url = canonicalize_url(item.get("url", ""))
    slug = extract_slug_from_url(url) or normalize_slug(item.get("offence_name", ""))
    guideline_id = stable_uuid("guideline", url or slug)
    return {
        "guideline_id": guideline_id,
        "slug": slug,
        "offence_name": normalize_space(item.get("offence_name", "Unknown offence")),
        "url": url,
        "court_type": normalize_space(item.get("court_type", "")),
        "category": normalize_space(item.get("category", "")),
        "source_tab": normalize_space(item.get("source_tab", "Offences")),
        "effective_from": normalize_space(item.get("effective_from", "")),
        "legislation_text": cleaned_legislation(item.get("legislation", "")),
        "page_type": "offence",
        "source_payload": item,
    }


def guideline_doc_from_page(item: dict[str, Any]) -> dict[str, Any]:
    url = canonicalize_url(item.get("url", ""))
    slug = extract_slug_from_url(url) or normalize_slug(item.get("title", ""))
    guideline_id = stable_uuid("guideline", url or slug)
    return {
        "guideline_id": guideline_id,
        "slug": slug,
        "offence_name": normalize_space(item.get("title", "Untitled page")),
        "url": url,
        "court_type": normalize_space(item.get("court_type", "")),
        "category": normalize_space(item.get("category", "")),
        "source_tab": normalize_space(item.get("source_tab", "")),
        "effective_from": "",
        "legislation_text": "",
        "page_type": normalize_space(item.get("page_type", "page")) or "page",
        "source_payload": item,
    }


def load_guideline_documents(
    scraped_guidelines: list[dict[str, Any]],
    pages: list[dict[str, Any]] | None,
) -> list[dict[str, Any]]:
    docs_by_key: dict[str, dict[str, Any]] = {}

    for row in scraped_guidelines:
        doc = guideline_doc_from_offence_guideline(row)
        key = doc["url"] or doc["slug"] or doc["guideline_id"]
        docs_by_key[key] = doc

    if pages:
        for page in pages:
            page_type = normalize_space(page.get("page_type", ""))
            if page_type == "offence":
                continue
            doc = guideline_doc_from_page(page)
            key = doc["url"] or doc["slug"] or doc["guideline_id"]
            if key in docs_by_key:
                continue
            docs_by_key[key] = doc

    return list(docs_by_key.values())


def select_guideline_candidate(
    offence_name: str,
    candidates: list[dict[str, Any]],
) -> tuple[dict[str, Any], float]:
    if len(candidates) == 1:
        return candidates[0], 0.99

    query = normalize_name_for_match(short_offence_name(offence_name))
    scored: list[tuple[float, dict[str, Any]]] = []
    for item in candidates:
        candidate_name = normalize_name_for_match(item["offence_name"])
        score = fuzz.token_set_ratio(query, candidate_name) / 100.0
        scored.append((score, item))
    scored.sort(key=lambda pair: pair[0], reverse=True)
    return scored[0][1], scored[0][0]


def slug_variants(slug: str) -> list[str]:
    value = slug.strip()
    if not value:
        return []
    variants = [value]
    stripped_version = value.rsplit("-", 1)[0] if value.rsplit("-", 1)[-1].isdigit() else value
    if stripped_version != value:
        variants.append(stripped_version)
    if "-5-000-" in value:
        variants.append(value.replace("-5-000-", "-5000-"))
    if "-5000-" in value:
        variants.append(value.replace("-5000-", "-5-000-"))
    # Preserve order while dropping duplicates.
    ordered: list[str] = []
    seen: set[str] = set()
    for entry in variants:
        if entry in seen:
            continue
        seen.add(entry)
        ordered.append(entry)
    return ordered


def build_offence_catalog_and_links(
    sentenceace_rows: list[dict[str, Any]],
    guideline_docs: list[dict[str, Any]],
    fuzzy_threshold: int,
) -> tuple[
    list[dict[str, Any]],
    list[dict[str, Any]],
    dict[str, str],
    list[dict[str, Any]],
]:
    docs_by_slug: dict[str, list[dict[str, Any]]] = defaultdict(list)
    docs_by_norm_name: dict[str, list[dict[str, Any]]] = defaultdict(list)

    for doc in guideline_docs:
        slug = doc["slug"]
        if slug:
            docs_by_slug[slug].append(doc)
        norm_name = normalize_name_for_match(doc["offence_name"])
        if norm_name:
            docs_by_norm_name[norm_name].append(doc)

    fuzzy_choices = list(docs_by_norm_name.keys())

    offence_rows: list[dict[str, Any]] = []
    link_rows: list[dict[str, Any]] = []
    primary_offence_by_guideline: dict[str, tuple[str, float]] = {}
    mapping_issues: list[dict[str, Any]] = []

    for raw in sentenceace_rows:
        full_name = normalize_space(raw.get("offencename", "Unknown offence"))
        provision = normalize_space(raw.get("provision", ""))
        offence_key = f"{provision}|{full_name}"
        offence_id = stable_uuid("offence", offence_key)

        row = {
            "offence_id": offence_id,
            "canonical_name": full_name,
            "short_name": short_offence_name(full_name),
            "offence_category": normalize_space(raw.get("offencecategory", "")),
            "provision": provision,
            "guideline_url": normalize_space(raw.get("guideline", "")),
            "legislation_url": normalize_space(raw.get("hyperlink", "")),
            "maximum_sentence_type": normalize_space(raw.get("maximumsentencetype", "")),
            "maximum_sentence_amount": normalize_space(raw.get("maximumsentenceamount", "")),
            "minimum_sentence_code": normalize_space(raw.get("minimumsentence", "")),
            "specified_violent": yes_no_to_bool(raw.get("specifiedviolentoffence")),
            "specified_sexual": yes_no_to_bool(raw.get("specifiedsexualoffence")),
            "specified_terrorist": yes_no_to_bool(raw.get("specifiedterroristoffence")),
            "listed_offence": yes_no_to_bool(raw.get("listedoffence")),
            "schedule18a_offence": yes_no_to_bool(raw.get("schedule18Aoffence")),
            "schedule19za": yes_no_to_bool(raw.get("schedule19za")),
            "cta_notification": yes_no_to_bool(raw.get("ctanotification")),
            "shpo": yes_no_to_bool(raw.get("shpo")),
            "disqualification": yes_no_to_bool(raw.get("disqualification")),
            "safeguarding1": yes_no_to_bool(raw.get("safeguarding1")),
            "safeguarding2": yes_no_to_bool(raw.get("safeguarding2")),
            "safeguarding3": yes_no_to_bool(raw.get("safeguarding3")),
            "safeguarding4": yes_no_to_bool(raw.get("safeguarding4")),
            "source_payload": raw,
        }
        offence_rows.append(row)

        matched_doc: dict[str, Any] | None = None
        match_method = "none"
        match_confidence = 0.0

        guideline_slug = extract_slug_from_url(row["guideline_url"])
        guideline_candidates: list[dict[str, Any]] = []
        if guideline_slug:
            for variant in slug_variants(guideline_slug):
                guideline_candidates.extend(docs_by_slug.get(variant, []))
        if guideline_candidates:
            matched_doc, match_confidence = select_guideline_candidate(full_name, guideline_candidates)
            match_method = "guideline_slug"
        else:
            generated_slug = normalize_slug(short_offence_name(full_name))
            generated_candidates: list[dict[str, Any]] = []
            for variant in slug_variants(generated_slug):
                generated_candidates.extend(docs_by_slug.get(variant, []))
            if generated_candidates:
                matched_doc, match_confidence = select_guideline_candidate(
                    full_name,
                    generated_candidates,
                )
                match_method = "name_slug"
            else:
                query = normalize_name_for_match(short_offence_name(full_name))
                if query and fuzzy_choices:
                    fuzzy_match = process.extractOne(query, fuzzy_choices, scorer=fuzz.token_set_ratio)
                    if fuzzy_match and fuzzy_match[1] >= fuzzy_threshold:
                        matched_doc = docs_by_norm_name[fuzzy_match[0]][0]
                        match_confidence = fuzzy_match[1] / 100.0
                        match_method = "fuzzy_name"

        if not matched_doc:
            mapping_issues.append(
                {
                    "offence_id": offence_id,
                    "canonical_name": full_name,
                    "guideline_url": row["guideline_url"],
                    "issue": "No guideline match",
                }
            )
            continue

        guideline_id = matched_doc["guideline_id"]
        link_row = {
            "link_id": stable_uuid("offence_guideline_link", f"{offence_id}|{guideline_id}"),
            "offence_id": offence_id,
            "guideline_id": guideline_id,
            "match_method": match_method,
            "match_confidence": round(match_confidence, 4),
            "is_primary": True,
        }
        link_rows.append(link_row)

        existing = primary_offence_by_guideline.get(guideline_id)
        if not existing or match_confidence > existing[1]:
            primary_offence_by_guideline[guideline_id] = (offence_id, match_confidence)

    primary_map = {guideline_id: payload[0] for guideline_id, payload in primary_offence_by_guideline.items()}
    return offence_rows, link_rows, primary_map, mapping_issues


def guideline_sections(doc: dict[str, Any]) -> list[dict[str, str]]:
    payload = doc["source_payload"]
    page_type = doc["page_type"]

    sections: list[dict[str, str]] = []

    if page_type != "offence":
        top_sections = payload.get("sections", [])
        for section in top_sections:
            heading = normalize_space(section.get("heading", "Section"))
            body_parts = [normalize_space(section.get("text", ""))]
            bullets = [normalize_space(b) for b in section.get("bullets", []) if normalize_space(b)]
            if bullets:
                body_parts.append("Bullets: " + " | ".join(bullets))
            tables = section.get("tables", [])
            if tables:
                table_rows = []
                for table in tables[:2]:
                    for row in table[:20]:
                        table_rows.append(" | ".join(normalize_space(cell) for cell in row if normalize_space(cell)))
                if table_rows:
                    body_parts.append("Tables: " + " || ".join(table_rows))
            text = normalize_space(" ".join(body_parts))
            if text:
                sections.append({"section_type": "supplementary_section", "heading": heading, "text": text})
        return sections

    sections.append(
        {
            "section_type": "overview",
            "heading": "Offence overview",
            "text": normalize_space(
                " ".join(
                    [
                        f"Offence: {doc['offence_name']}",
                        f"Court: {doc.get('court_type', '')}",
                        f"Category: {doc.get('category', '')}",
                        f"Effective from: {doc.get('effective_from', '')}",
                    ]
                )
            ),
        }
    )

    legislation = cleaned_legislation(payload.get("legislation", ""))
    if legislation:
        sections.append(
            {
                "section_type": "legislation",
                "heading": "Legislation",
                "text": legislation,
            }
        )

    culpability_rows = []
    for row in payload.get("culpability_levels", []):
        level = normalize_space(row.get("level", ""))
        description = normalize_space(row.get("description", ""))
        factors = [normalize_space(item) for item in row.get("factors", []) if normalize_space(item)]
        row_text = f"{level}: {description}"
        if factors:
            row_text += " Factors: " + " | ".join(factors)
        culpability_rows.append(normalize_space(row_text))
    if culpability_rows:
        sections.append(
            {
                "section_type": "culpability",
                "heading": "Culpability levels",
                "text": " || ".join(culpability_rows),
            }
        )

    harm_rows = []
    for row in payload.get("harm_levels", []):
        category = normalize_space(row.get("category", ""))
        description = normalize_space(row.get("description", ""))
        factors = [normalize_space(item) for item in row.get("factors", []) if normalize_space(item)]
        row_text = f"{category}: {description}"
        if factors:
            row_text += " Factors: " + " | ".join(factors)
        harm_rows.append(normalize_space(row_text))
    if harm_rows:
        sections.append(
            {
                "section_type": "harm",
                "heading": "Harm categories",
                "text": " || ".join(harm_rows),
            }
        )

    ranges = payload.get("sentencing_ranges", [])
    range_rows = []
    for row in ranges:
        range_rows.append(
            normalize_space(
                " ".join(
                    [
                        f"Culpability {row.get('culpability', '')}",
                        f"Harm {row.get('harm', '')}",
                        f"Starting point {row.get('starting_point', '')}",
                        f"Range {row.get('category_range', '')}",
                    ]
                )
            )
        )
    if range_rows:
        sections.append(
            {
                "section_type": "sentencing_ranges",
                "heading": "Starting points and ranges",
                "text": " || ".join(row for row in range_rows if row),
            }
        )

    aggravating = [normalize_space(item) for item in payload.get("aggravating_factors", []) if normalize_space(item)]
    if aggravating:
        sections.append(
            {
                "section_type": "aggravating",
                "heading": "Aggravating factors",
                "text": " | ".join(aggravating),
            }
        )

    mitigating = [normalize_space(item) for item in payload.get("mitigating_factors", []) if normalize_space(item)]
    if mitigating:
        sections.append(
            {
                "section_type": "mitigating",
                "heading": "Mitigating factors",
                "text": " | ".join(mitigating),
            }
        )

    steps = payload.get("additional_steps", [])
    if steps:
        step_rows = []
        for entry in steps:
            if isinstance(entry, str):
                step_rows.append(normalize_space(entry))
                continue
            if isinstance(entry, dict):
                pieces = [
                    normalize_space(str(entry.get("step", ""))),
                    normalize_space(str(entry.get("title", ""))),
                    normalize_space(str(entry.get("content", ""))),
                    normalize_space(str(entry.get("text", ""))),
                ]
                packed = " ".join([piece for piece in pieces if piece])
                if packed:
                    step_rows.append(packed)
        if step_rows:
            sections.append(
                {
                    "section_type": "additional_steps",
                    "heading": "Additional steps",
                    "text": " || ".join(step_rows),
                }
            )

    return [section for section in sections if section.get("text")]


def build_sentencing_rows(
    guideline_docs: list[dict[str, Any]],
    primary_map: dict[str, str],
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for doc in guideline_docs:
        payload = doc["source_payload"]
        ranges = payload.get("sentencing_ranges", [])
        for idx, entry in enumerate(ranges):
            matrix_id = stable_uuid("sentencing_matrix", f"{doc['guideline_id']}|{idx}")
            rows.append(
                {
                    "matrix_id": matrix_id,
                    "guideline_id": doc["guideline_id"],
                    "offence_id": primary_map.get(doc["guideline_id"]),
                    "culpability": normalize_space(entry.get("culpability", "")),
                    "harm": normalize_space(entry.get("harm", "")),
                    "starting_point_text": normalize_space(entry.get("starting_point", "")),
                    "category_range_text": normalize_space(entry.get("category_range", "")),
                    "source_payload": entry,
                }
            )
    return rows


def build_factor_rows(
    guideline_docs: list[dict[str, Any]],
    primary_map: dict[str, str],
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for doc in guideline_docs:
        payload = doc["source_payload"]
        offence_id = primary_map.get(doc["guideline_id"])

        for factor in payload.get("aggravating_factors", []):
            text = normalize_space(factor)
            if not text:
                continue
            rows.append(
                {
                    "factor_id": stable_uuid(
                        "guideline_factor",
                        f"{doc['guideline_id']}|aggravating|{text}",
                    ),
                    "guideline_id": doc["guideline_id"],
                    "offence_id": offence_id,
                    "factor_type": "aggravating",
                    "factor_text": text,
                    "source_payload": {"text": text},
                }
            )

        for factor in payload.get("mitigating_factors", []):
            text = normalize_space(factor)
            if not text:
                continue
            rows.append(
                {
                    "factor_id": stable_uuid(
                        "guideline_factor",
                        f"{doc['guideline_id']}|mitigating|{text}",
                    ),
                    "guideline_id": doc["guideline_id"],
                    "offence_id": offence_id,
                    "factor_type": "mitigating",
                    "factor_text": text,
                    "source_payload": {"text": text},
                }
            )

        for step in payload.get("additional_steps", []):
            text = normalize_space(json.dumps(step, ensure_ascii=False) if isinstance(step, dict) else str(step))
            if not text:
                continue
            rows.append(
                {
                    "factor_id": stable_uuid(
                        "guideline_factor",
                        f"{doc['guideline_id']}|additional_step|{text}",
                    ),
                    "guideline_id": doc["guideline_id"],
                    "offence_id": offence_id,
                    "factor_type": "additional_step",
                    "factor_text": text,
                    "source_payload": {"text": text},
                }
            )

    return rows


def build_chunk_rows(
    guideline_docs: list[dict[str, Any]],
    primary_map: dict[str, str],
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []

    for doc in guideline_docs:
        sections = guideline_sections(doc)
        offence_id = primary_map.get(doc["guideline_id"])

        chunk_index = 0
        for section in sections:
            chunks = chunk_text(section["text"], max_chars=1200, overlap_chars=180)
            for chunk in chunks:
                rows.append(
                    {
                        "chunk_id": stable_uuid(
                            "guideline_chunk",
                            f"{doc['guideline_id']}|{section['section_type']}|{chunk_index}|{chunk}",
                        ),
                        "guideline_id": doc["guideline_id"],
                        "offence_id": offence_id,
                        "section_type": section["section_type"],
                        "section_heading": section["heading"],
                        "chunk_index": chunk_index,
                        "chunk_text": chunk,
                        "token_estimate": estimate_tokens(chunk),
                        "metadata": {"page_type": doc["page_type"], "source_tab": doc.get("source_tab", "")},
                        "source_url": doc["url"],
                        "embedding": None,
                    }
                )
                chunk_index += 1
                if chunk_index >= 64:
                    break
            if chunk_index >= 64:
                break

    return rows


def build_source_versions(
    scraped_guidelines_path: Path,
    scraped_pages_path: Path | None,
    sentenceace_path: Path,
) -> list[dict[str, Any]]:
    rows = [
        {
            "source_version_id": stable_uuid("source_version", f"scraped_guidelines|{scraped_guidelines_path}"),
            "source_name": "scraped_guidelines",
            "source_path": str(scraped_guidelines_path),
            "source_hash": hash_file(scraped_guidelines_path),
            "metadata": {},
        },
        {
            "source_version_id": stable_uuid("source_version", f"sentenceace|{sentenceace_path}"),
            "source_name": "sentenceace",
            "source_path": str(sentenceace_path),
            "source_hash": hash_file(sentenceace_path),
            "metadata": {},
        },
    ]

    if scraped_pages_path and scraped_pages_path.exists():
        rows.append(
            {
                "source_version_id": stable_uuid("source_version", f"scraped_pages|{scraped_pages_path}"),
                "source_name": "scraped_pages",
                "source_path": str(scraped_pages_path),
                "source_hash": hash_file(scraped_pages_path),
                "metadata": {},
            }
        )
    return rows


def main() -> None:
    args = parse_args()
    args.output_dir.mkdir(parents=True, exist_ok=True)

    scraped_guidelines = load_json(args.scraped_guidelines)
    pages = load_json(args.scraped_pages) if args.scraped_pages and args.scraped_pages.exists() else None
    sentenceace_rows = read_json_from_zip_or_file(args.sentenceace, json_name="offences.json")

    guideline_docs = load_guideline_documents(scraped_guidelines, pages)
    offence_rows, link_rows, primary_map, mapping_issues = build_offence_catalog_and_links(
        sentenceace_rows,
        guideline_docs,
        args.fuzzy_threshold,
    )

    sentencing_rows = build_sentencing_rows(guideline_docs, primary_map)
    factor_rows = build_factor_rows(guideline_docs, primary_map)
    chunk_rows = build_chunk_rows(guideline_docs, primary_map)
    source_versions = build_source_versions(args.scraped_guidelines, args.scraped_pages, args.sentenceace)

    guideline_rows = []
    for doc in guideline_docs:
        guideline_rows.append(
            {
                "guideline_id": doc["guideline_id"],
                "slug": doc["slug"],
                "offence_name": doc["offence_name"],
                "url": doc["url"],
                "court_type": doc.get("court_type", ""),
                "category": doc.get("category", ""),
                "source_tab": doc.get("source_tab", ""),
                "effective_from": doc.get("effective_from", ""),
                "legislation_text": doc.get("legislation_text", ""),
                "source_payload": doc["source_payload"],
            }
        )

    write_jsonl(args.output_dir / "source_versions.jsonl", source_versions)
    write_jsonl(args.output_dir / "offence_catalog.jsonl", offence_rows)
    write_jsonl(args.output_dir / "guidelines.jsonl", guideline_rows)
    write_jsonl(args.output_dir / "offence_guideline_links.jsonl", link_rows)
    write_jsonl(args.output_dir / "sentencing_matrix.jsonl", sentencing_rows)
    write_jsonl(args.output_dir / "guideline_factors.jsonl", factor_rows)
    write_jsonl(args.output_dir / "guideline_chunks.jsonl", chunk_rows)
    write_jsonl(args.output_dir / "mapping_issues.jsonl", mapping_issues)

    report = {
        "counts": {
            "sentenceace_offences": len(sentenceace_rows),
            "guidelines": len(guideline_rows),
            "offence_catalog": len(offence_rows),
            "offence_guideline_links": len(link_rows),
            "sentencing_matrix": len(sentencing_rows),
            "guideline_factors": len(factor_rows),
            "guideline_chunks": len(chunk_rows),
            "mapping_issues": len(mapping_issues),
        },
        "mapping": {
            "coverage": round((len(link_rows) / len(offence_rows)) * 100, 2) if offence_rows else 0,
            "linked_offence_ids": len({row['offence_id'] for row in link_rows}),
            "linked_guideline_ids": len({row['guideline_id'] for row in link_rows}),
        },
    }

    with (args.output_dir / "etl_report.json").open("w", encoding="utf-8") as handle:
        json.dump(report, handle, indent=2, ensure_ascii=False)

    print(json.dumps(report, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
