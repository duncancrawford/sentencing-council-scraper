"""Data models for sentencing guidelines."""

from dataclasses import dataclass, field, asdict
from typing import Optional
import json


@dataclass
class SentencingRange:
    """A sentencing range for a specific culpability/harm combination."""

    culpability: str  # e.g. "A", "B", "C" or "High", "Medium", "Low"
    harm: str  # e.g. "1", "2", "3" or "Category 1", "Category 2"
    starting_point: str  # e.g. "4 years' custody"
    category_range: str  # e.g. "3 – 6 years' custody"


@dataclass
class CulpabilityLevel:
    """A culpability level with its description and factors."""

    level: str  # e.g. "A", "B", "C" or "High", "Medium", "Low"
    description: str
    factors: list[str] = field(default_factory=list)


@dataclass
class HarmLevel:
    """A harm category with its description and factors."""

    category: str  # e.g. "1", "2", "3"
    description: str
    factors: list[str] = field(default_factory=list)


@dataclass
class Guideline:
    """A complete sentencing guideline for an offence."""

    offence_name: str
    url: str
    court_type: str  # "magistrates" or "crown_court" or "both"
    legislation: str = ""
    effective_from: str = ""

    # Step 1: Culpability and Harm
    culpability_levels: list[CulpabilityLevel] = field(default_factory=list)
    harm_levels: list[HarmLevel] = field(default_factory=list)

    # Step 2: Sentencing table
    sentencing_ranges: list[SentencingRange] = field(default_factory=list)

    # Aggravating and mitigating factors
    aggravating_factors: list[str] = field(default_factory=list)
    mitigating_factors: list[str] = field(default_factory=list)

    # Additional data that may vary by offence
    additional_steps: list[dict] = field(default_factory=list)
    raw_sections: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return asdict(self)

    def to_json(self, indent: int = 2) -> str:
        return json.dumps(self.to_dict(), indent=indent, ensure_ascii=False)


@dataclass
class SupplementarySection:
    """A section within a supplementary information page."""

    heading: str
    level: str  # e.g. "h2", "h3"
    text: str
    bullets: list[str] = field(default_factory=list)
    tables: list[list[list[str]]] = field(default_factory=list)


@dataclass
class SupplementaryPage:
    """A supplementary information page with structured sections."""

    page_title: str
    url: str
    court_type: str
    sections: list[SupplementarySection] = field(default_factory=list)
    page_type: str = "supplementary"

    def to_dict(self) -> dict:
        return asdict(self)

    def to_json(self, indent: int = 2) -> str:
        return json.dumps(self.to_dict(), indent=indent, ensure_ascii=False)


@dataclass
class OffenceLink:
    """A link to an offence guideline found on the index page."""

    name: str
    url: str
    court_type: str
    category: str = ""  # e.g. "Assault", "Theft", "Drug offences"
    source_tab: str = ""  # e.g. "Offences", "Overarching guidelines"
