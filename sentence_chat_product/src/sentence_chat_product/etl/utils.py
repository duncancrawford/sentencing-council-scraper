"""ETL utility functions."""

from __future__ import annotations

import hashlib
import json
import re
import uuid
from pathlib import Path
from urllib.parse import urlparse
from zipfile import ZipFile

WORD_RE = re.compile(r"\w+")


def normalize_space(value: str | None) -> str:
    if not value:
        return ""
    return re.sub(r"\s+", " ", value).strip()


def yes_no_to_bool(value: str | bool | None) -> bool:
    if isinstance(value, bool):
        return value
    if value is None:
        return False
    return normalize_space(str(value)).lower() == "yes"


def short_offence_name(full_name: str) -> str:
    text = normalize_space(full_name)
    if ":" not in text:
        return text
    left, right = text.split(":", 1)
    if not right.strip():
        return left.strip()
    return right.strip()


def stable_uuid(namespace: str, value: str) -> str:
    ns = uuid.uuid5(uuid.NAMESPACE_URL, namespace)
    return str(uuid.uuid5(ns, value))


def hash_file(path: Path) -> str:
    hasher = hashlib.sha256()
    with path.open("rb") as handle:
        while True:
            block = handle.read(1024 * 1024)
            if not block:
                break
            hasher.update(block)
    return hasher.hexdigest()


def extract_slug_from_url(url: str | None) -> str:
    if not url:
        return ""
    parsed = urlparse(url)
    path = parsed.path.rstrip("/")
    if not path:
        return ""
    parts = [p for p in path.split("/") if p]
    if not parts:
        return ""
    ignored = {
        "offences",
        "guidelines",
        "item",
        "crown-court",
        "magistrates-court",
        "both-courts",
    }
    candidate = ""
    for part in parts[::-1]:
        if part.lower() in ignored:
            continue
        candidate = part
        break
    return normalize_slug(candidate)


def normalize_slug(value: str) -> str:
    text = normalize_space(value).lower()
    text = text.replace("_", "-")
    text = re.sub(r"[^a-z0-9\-]+", "-", text)
    # Normalize numeric groups like 5-000 -> 5000 for cross-source slug matching.
    text = re.sub(r"(?<=\d)-(?=\d)", "", text)
    text = re.sub(r"-{2,}", "-", text)
    return text.strip("-")


def normalize_name_for_match(name: str) -> str:
    text = normalize_space(name).lower()
    text = re.sub(r"\([^)]*\)", "", text)
    text = re.sub(r"[^a-z0-9 ]+", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text


def estimate_tokens(text: str) -> int:
    # Approximation that works well enough for chunk sizing and metadata.
    return max(1, int(len(text) / 4))


def chunk_text(text: str, max_chars: int = 1200, overlap_chars: int = 160) -> list[str]:
    body = normalize_space(text)
    if not body:
        return []
    if len(body) <= max_chars:
        return [body]

    chunks: list[str] = []
    cursor = 0
    text_len = len(body)

    while cursor < text_len:
        end = min(cursor + max_chars, text_len)
        if end < text_len:
            split = body.rfind(" ", cursor + int(max_chars * 0.6), end)
            if split > cursor:
                end = split
        piece = body[cursor:end].strip()
        if piece:
            chunks.append(piece)
        if end >= text_len:
            break
        cursor = max(0, end - overlap_chars)

    return chunks


def read_json_from_zip_or_file(path: Path, json_name: str = "offences.json") -> list[dict]:
    if path.suffix.lower() == ".zip":
        with ZipFile(path, "r") as zf:
            target = None
            for info in zf.infolist():
                name = info.filename.strip("/")
                if name.lower().endswith(json_name.lower()):
                    target = name
                    break
            if not target:
                raise FileNotFoundError(f"{json_name} not found in {path}")
            with zf.open(target, "r") as handle:
                return json.loads(handle.read().decode("utf-8"))

    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)
