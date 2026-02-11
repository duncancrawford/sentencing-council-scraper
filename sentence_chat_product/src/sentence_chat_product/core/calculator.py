"""Sentence calculator orchestration."""

from __future__ import annotations

from .rules import (
    apply_minimum_sentence_floor,
    has_life_maximum,
    minimum_sentence_decision,
    release_decision,
    sentence_after_plea,
    validate_input,
    victim_surcharge,
)
from .types import (
    SentenceCalculationInput,
    SentenceCalculationResult,
    SentencingRangeRecord,
)


def pick_sentencing_range(
    culpability: str | None,
    harm: str | None,
    matrix_rows: list[dict],
) -> SentencingRangeRecord | None:
    if not culpability or not harm:
        return None

    desired_culp = culpability.strip().lower()
    desired_harm = harm.strip().lower()

    for row in matrix_rows:
        row_culp = (row.get("culpability") or "").strip().lower()
        row_harm = (row.get("harm") or "").strip().lower()
        if row_culp == desired_culp and row_harm == desired_harm:
            return SentencingRangeRecord(
                culpability=row.get("culpability") or "",
                harm=row.get("harm") or "",
                starting_point_text=row.get("starting_point_text") or "",
                category_range_text=row.get("category_range_text") or "",
            )

    # fallback: containment match (useful for values like "Category 1")
    for row in matrix_rows:
        row_culp = (row.get("culpability") or "").strip().lower()
        row_harm = (row.get("harm") or "").strip().lower()
        if desired_culp in row_culp and desired_harm in row_harm:
            return SentencingRangeRecord(
                culpability=row.get("culpability") or "",
                harm=row.get("harm") or "",
                starting_point_text=row.get("starting_point_text") or "",
                category_range_text=row.get("category_range_text") or "",
            )

    return None


def build_warnings(data: SentenceCalculationInput, pre_plea_term_months: float | None) -> list[str]:
    warnings: list[str] = []
    offence = data.offence

    if (
        offence.listed_offence
        and data.age_at_sentence >= 18
        and data.prior_listed_offence_with_custody
        and (pre_plea_term_months or 0) >= 120
    ):
        warnings.append(
            "Mandatory life sentence route may be engaged for repeat listed offence; review SC283/SC273 conditions."
        )

    if offence.specified_violent or offence.specified_sexual or offence.specified_terrorist:
        if data.dangerousness_assessed and has_life_maximum(offence):
            warnings.append(
                "Dangerousness + specified offence + life max may trigger mandatory life provisions; review SC285/SC274/SC258."
            )

    if data.sentence_type == "special_custodial_sentence" and not offence.schedule18a_offence:
        warnings.append(
            "Special custodial sentence selected but offence is not marked Schedule 18A in offence metadata."
        )

    return warnings


def calculate_sentence(
    data: SentenceCalculationInput,
    matrix_rows: list[dict],
) -> SentenceCalculationResult:
    errors = validate_input(data)
    if errors:
        raise ValueError("; ".join(errors))

    trace: list[str] = []

    pre_plea = data.pre_plea_term_months
    post_plea = sentence_after_plea(pre_plea, data.plea_stage)
    if pre_plea is not None:
        trace.append(f"Applied plea factor for {data.plea_stage}: pre={pre_plea} -> post={post_plea}")

    min_decision = minimum_sentence_decision(data)
    if min_decision.triggered:
        trace.append(min_decision.reason or "Minimum sentence rule triggered")

    pre_plea, post_plea, floor_trace = apply_minimum_sentence_floor(pre_plea, post_plea, min_decision)
    trace.extend(floor_trace)

    release = release_decision(data, post_plea)
    trace.append(release.reason)

    estimated_time = None
    if post_plea is not None and release.release_fraction is not None:
        estimated_time = round(post_plea * release.release_fraction, 2)

    surcharge = victim_surcharge(
        offence_date=data.offence_date,
        age_at_offence=data.age_at_offence,
        sentence_type=data.sentence_type,
        fine_amount=data.fine_amount,
        custodial_term_months=post_plea,
    )

    matched_range = pick_sentencing_range(data.culpability, data.harm, matrix_rows)
    warnings = build_warnings(data, pre_plea)

    return SentenceCalculationResult(
        offence_id=data.offence.offence_id,
        offence_name=data.offence.canonical_name,
        sentence_type=data.sentence_type,
        pre_plea_term_months=pre_plea,
        post_plea_term_months=post_plea,
        minimum_sentence_triggered=min_decision.triggered,
        minimum_floor_pre_plea_months=min_decision.floor_pre_months,
        minimum_floor_post_plea_months=min_decision.floor_post_months,
        release_fraction=release.release_fraction,
        estimated_time_in_custody_months=estimated_time,
        victim_surcharge_gbp=round(surcharge, 2),
        matched_range=matched_range,
        warnings=warnings,
        trace=trace,
    )
