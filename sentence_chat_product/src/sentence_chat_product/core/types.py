"""Core types shared by calculator and API."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from typing import Literal

PleaStage = Literal[
    "first_stage",
    "after_first_stage_before_trial",
    "day_of_trial",
    "after_trial_begins",
    "not_guilty",
]

SentenceType = Literal[
    "conditional_discharge",
    "fine",
    "community_order",
    "youth_rehabilitation_order",
    "determinate_custodial_sentence",
    "suspended_sentence_order",
    "dto",
    "yoi_detention",
    "extended_sentence",
    "special_custodial_sentence",
    "discretionary_life_sentence",
    "mandatory_life_sentence",
]


@dataclass(slots=True)
class OffenceRecord:
    offence_id: str
    canonical_name: str
    short_name: str
    offence_category: str
    provision: str
    guideline_url: str
    legislation_url: str
    maximum_sentence_type: str
    maximum_sentence_amount: str
    minimum_sentence_code: str
    specified_violent: bool
    specified_sexual: bool
    specified_terrorist: bool
    listed_offence: bool
    schedule18a_offence: bool
    schedule19za: bool
    cta_notification: bool


@dataclass(slots=True)
class SentenceCalculationInput:
    offence: OffenceRecord
    offence_date: date
    conviction_date: date
    sentence_date: date
    age_at_offence: int
    age_at_conviction: int
    age_at_sentence: int
    plea_stage: PleaStage
    sentence_type: SentenceType
    culpability: str | None = None
    harm: str | None = None
    pre_plea_term_months: float | None = None
    extension_months: float = 0.0
    fine_amount: float | None = None
    dangerousness_assessed: bool = False
    prior_listed_offence_with_custody: bool = False
    prior_domestic_burglary_count: int = 0
    prior_class_a_trafficking_count: int = 0
    prior_relevant_weapon_conviction: bool = False
    terrorism_flag: bool = False
    minimum_sentence_unjust_or_exceptional: bool = False
    replicate_ace_release_bug: bool = True


@dataclass(slots=True)
class SentencingRangeRecord:
    culpability: str
    harm: str
    starting_point_text: str
    category_range_text: str


@dataclass(slots=True)
class SentenceCalculationResult:
    offence_id: str
    offence_name: str
    sentence_type: SentenceType
    pre_plea_term_months: float | None
    post_plea_term_months: float | None
    minimum_sentence_triggered: bool
    minimum_floor_pre_plea_months: float | None
    minimum_floor_post_plea_months: float | None
    release_fraction: float | None
    estimated_time_in_custody_months: float | None
    victim_surcharge_gbp: float
    matched_range: SentencingRangeRecord | None = None
    warnings: list[str] = field(default_factory=list)
    trace: list[str] = field(default_factory=list)
