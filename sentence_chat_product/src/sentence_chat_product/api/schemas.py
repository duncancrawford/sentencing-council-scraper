"""Pydantic API schemas."""

from __future__ import annotations

from datetime import date
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

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


class CalculateSentenceRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    offence_id: str | None = None
    offence_query: str | None = None

    offence_date: date
    conviction_date: date
    sentence_date: date

    age_at_offence: int = Field(ge=10, le=120)
    age_at_conviction: int = Field(ge=10, le=120)
    age_at_sentence: int = Field(ge=10, le=120)

    plea_stage: PleaStage
    sentence_type: SentenceType

    culpability: str | None = None
    harm: str | None = None

    pre_plea_term_months: float | None = Field(default=None, ge=0)
    extension_months: float = Field(default=0, ge=0)
    fine_amount: float | None = Field(default=None, ge=0)

    dangerousness_assessed: bool = False
    prior_listed_offence_with_custody: bool = False
    prior_domestic_burglary_count: int = Field(default=0, ge=0)
    prior_class_a_trafficking_count: int = Field(default=0, ge=0)
    prior_relevant_weapon_conviction: bool = False
    terrorism_flag: bool = False

    minimum_sentence_unjust_or_exceptional: bool = False
    replicate_ace_release_bug: bool = True

    @model_validator(mode="after")
    def validate_offence_selector(self) -> "CalculateSentenceRequest":
        if not self.offence_id and not self.offence_query:
            raise ValueError("Provide either offence_id or offence_query")
        return self


class SentencingRangeOut(BaseModel):
    culpability: str
    harm: str
    starting_point_text: str
    category_range_text: str


class CalculateSentenceResponse(BaseModel):
    offence_id: str
    offence_name: str
    sentence_type: str
    pre_plea_term_months: float | None
    post_plea_term_months: float | None
    minimum_sentence_triggered: bool
    minimum_floor_pre_plea_months: float | None
    minimum_floor_post_plea_months: float | None
    release_fraction: float | None
    estimated_time_in_custody_months: float | None
    victim_surcharge_gbp: float
    matched_range: SentencingRangeOut | None = None
    warnings: list[str]
    trace: list[str]


class SearchGuidelinesRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    query: str
    offence_id: str | None = None
    top_k: int = Field(default=6, ge=1, le=20)


class GuidelineChunkOut(BaseModel):
    chunk_id: str
    guideline_id: str
    offence_id: str | None
    section_type: str | None
    section_heading: str | None
    chunk_text: str
    source_url: str | None
    score: float | None = None


class SearchGuidelinesResponse(BaseModel):
    results: list[GuidelineChunkOut]


class ChatTurnRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    message: str
    offence_id: str | None = None
    offence_query: str | None = None
    calculation: CalculateSentenceRequest | None = None
    top_k: int = Field(default=5, ge=1, le=20)


class ChatTurnResponse(BaseModel):
    reply: str
    calculation: CalculateSentenceResponse | None = None
    citations: list[GuidelineChunkOut] = Field(default_factory=list)
    follow_up_questions: list[str] = Field(default_factory=list)
