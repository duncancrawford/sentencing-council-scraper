"""Export scraped guidelines to various formats."""

import json
import csv
import os
import logging
from pathlib import Path
from typing import Optional

from .models import Guideline
from .config import OUTPUT_DIR

logger = logging.getLogger(__name__)


def export_json(
    guidelines: list[Guideline],
    output_path: Optional[str] = None,
    pretty: bool = True,
) -> str:
    """Export all guidelines to a single JSON file."""
    path = output_path or os.path.join(OUTPUT_DIR, "guidelines.json")
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)

    data = [g.to_dict() for g in guidelines]

    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2 if pretty else None, ensure_ascii=False)

    logger.info(f"Exported {len(guidelines)} guidelines to {path}")
    return path


def export_individual_json(
    guidelines: list[Guideline],
    output_dir: Optional[str] = None,
) -> list[str]:
    """Export each guideline as a separate JSON file."""
    directory = output_dir or os.path.join(OUTPUT_DIR, "guidelines")
    os.makedirs(directory, exist_ok=True)

    paths = []
    for guideline in guidelines:
        # Create a safe filename from the offence name
        safe_name = _safe_filename(guideline.offence_name)
        path = os.path.join(directory, f"{safe_name}.json")

        with open(path, "w", encoding="utf-8") as f:
            f.write(guideline.to_json())

        paths.append(path)

    logger.info(f"Exported {len(paths)} individual guideline files to {directory}")
    return paths


def export_csv_summary(
    guidelines: list[Guideline],
    output_path: Optional[str] = None,
) -> str:
    """Export a CSV summary of all sentencing ranges across guidelines."""
    path = output_path or os.path.join(OUTPUT_DIR, "sentencing_ranges.csv")
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)

    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow([
            "offence_name",
            "court_type",
            "culpability",
            "harm",
            "starting_point",
            "category_range",
            "url",
        ])

        for guideline in guidelines:
            for sr in guideline.sentencing_ranges:
                writer.writerow([
                    guideline.offence_name,
                    guideline.court_type,
                    sr.culpability,
                    sr.harm,
                    sr.starting_point,
                    sr.category_range,
                    guideline.url,
                ])

    logger.info(f"Exported sentencing ranges CSV to {path}")
    return path


def export_offence_index(
    guidelines: list[Guideline],
    output_path: Optional[str] = None,
) -> str:
    """Export a simple index of all offences found."""
    path = output_path or os.path.join(OUTPUT_DIR, "offence_index.json")
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)

    index = []
    for g in guidelines:
        index.append({
            "offence_name": g.offence_name,
            "court_type": g.court_type,
            "legislation": g.legislation,
            "url": g.url,
            "num_sentencing_ranges": len(g.sentencing_ranges),
            "num_aggravating_factors": len(g.aggravating_factors),
            "num_mitigating_factors": len(g.mitigating_factors),
        })

    with open(path, "w", encoding="utf-8") as f:
        json.dump(index, f, indent=2, ensure_ascii=False)

    logger.info(f"Exported offence index to {path}")
    return path


def _safe_filename(name: str) -> str:
    """Convert an offence name to a safe filename."""
    safe = name.lower()
    safe = safe.replace(" ", "_")
    safe = "".join(c for c in safe if c.isalnum() or c in ("_", "-"))
    safe = safe[:100]  # Limit length
    return safe or "unknown"
