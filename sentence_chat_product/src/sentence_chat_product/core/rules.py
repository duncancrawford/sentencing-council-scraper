"""Deterministic sentencing rules derived from sentenceACE spec."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date

from .types import OffenceRecord, SentenceCalculationInput

PLEA_FACTORS: dict[str, float] = {
    "first_stage": 2.0 / 3.0,
    "after_first_stage_before_trial": 3.0 / 4.0,
    "day_of_trial": 9.0 / 10.0,
    "after_trial_begins": 19.0 / 20.0,
    "not_guilty": 1.0,
}

CUSTODIAL_SENTENCE_TYPES = {
    "determinate_custodial_sentence",
    "dto",
    "yoi_detention",
    "extended_sentence",
    "special_custodial_sentence",
    "discretionary_life_sentence",
    "mandatory_life_sentence",
}

SUSPENDED_OR_NON_IMMEDIATE = {"suspended_sentence_order"}

SERIOUS_PROVISION_MARKERS = [
    "manslaughter",
    "soliciting to commit murder",
    "grievous bodily harm with intent",
    "wounding with intent",
    "gbh with intent",
]

FORTY_PERCENT_EXCLUSIONS = [
    "serious crime act 2015 s.76",
    "serious crime act 2015 s.75a",
    "sentencing act 2020 s.363",
    "family law act 1996 s.42a",
    "domestic abuse act 2021 s.39",
    "national security act",
    "official secrets act",
]


@dataclass(slots=True)
class MinimumSentenceDecision:
    triggered: bool
    floor_pre_months: float | None
    floor_post_months: float | None
    reason: str | None


@dataclass(slots=True)
class ReleaseDecision:
    release_fraction: float | None
    reason: str


def validate_input(data: SentenceCalculationInput) -> list[str]:
    errors: list[str] = []

    if data.offence_date > data.conviction_date:
        errors.append("offence_date must be on or before conviction_date")
    if data.conviction_date > data.sentence_date:
        errors.append("conviction_date must be on or before sentence_date")

    if not (10 <= data.age_at_offence <= 120):
        errors.append("age_at_offence must be between 10 and 120")
    if data.age_at_conviction < data.age_at_offence:
        errors.append("age_at_conviction must be >= age_at_offence")
    if data.age_at_sentence < data.age_at_conviction:
        errors.append("age_at_sentence must be >= age_at_conviction")

    if data.pre_plea_term_months is not None and data.pre_plea_term_months < 0:
        errors.append("pre_plea_term_months must be non-negative")
    if data.extension_months < 0:
        errors.append("extension_months must be non-negative")
    if data.fine_amount is not None and data.fine_amount < 0:
        errors.append("fine_amount must be non-negative")

    return errors


def is_custodial(sentence_type: str) -> bool:
    return sentence_type in CUSTODIAL_SENTENCE_TYPES


def is_immediate_custody(sentence_type: str) -> bool:
    return is_custodial(sentence_type) and sentence_type not in SUSPENDED_OR_NON_IMMEDIATE


def has_life_maximum(offence: OffenceRecord) -> bool:
    return "life" in (offence.maximum_sentence_amount or "").lower()


def plea_factor(stage: str) -> float:
    return PLEA_FACTORS.get(stage, 1.0)


def minimum_sentence_decision(data: SentenceCalculationInput) -> MinimumSentenceDecision:
    if data.minimum_sentence_unjust_or_exceptional:
        return MinimumSentenceDecision(False, None, None, "minimum disapplied by input override")

    code = (data.offence.minimum_sentence_code or "").strip().upper()
    if not code:
        return MinimumSentenceDecision(False, None, None, None)

    adult = data.age_at_sentence >= 18
    youth_16_17 = 16 <= data.age_at_sentence <= 17
    guilty = data.plea_stage != "not_guilty"

    if code == "A":
        if adult and data.prior_domestic_burglary_count >= 2:
            floor_pre = 36.0
            floor_post = 28.8 if guilty else 36.0
            return MinimumSentenceDecision(True, floor_pre, floor_post, "Domestic burglary minimum")
        return MinimumSentenceDecision(False, None, None, "Conditions for A not met")

    if code == "B":
        if (
            adult
            and data.offence_date >= date(1997, 10, 1)
            and data.prior_class_a_trafficking_count >= 2
        ):
            floor_pre = 84.0
            floor_post = 67.2 if guilty else 84.0
            return MinimumSentenceDecision(True, floor_pre, floor_post, "Class A trafficking minimum")
        return MinimumSentenceDecision(False, None, None, "Conditions for B not met")

    if code in {"C1", "C2", "C3", "C4"}:
        starts = {
            "C1": date(2004, 1, 22),
            "C2": date(2007, 4, 6),
            "C3": date(2014, 7, 14),
            "C4": date(1900, 1, 1),
        }
        if data.offence_date < starts[code]:
            return MinimumSentenceDecision(False, None, None, "Firearms date threshold not met")
        if adult:
            return MinimumSentenceDecision(True, 60.0, 60.0, "Firearms adult minimum")
        if youth_16_17:
            return MinimumSentenceDecision(True, 36.0, 36.0, "Firearms youth minimum")
        return MinimumSentenceDecision(False, None, None, "Under 16")

    if code == "D":
        if data.offence_date < date(2015, 7, 17):
            return MinimumSentenceDecision(False, None, None, "Weapon possession date threshold not met")
        if data.age_at_offence < 16:
            return MinimumSentenceDecision(False, None, None, "Under 16 at offence")
        if not data.prior_relevant_weapon_conviction:
            return MinimumSentenceDecision(False, None, None, "No qualifying prior conviction")

        if data.age_at_conviction >= 18:
            floor_pre = 6.0
            floor_post = 4.8 if guilty else 6.0
            return MinimumSentenceDecision(True, floor_pre, floor_post, "Weapon possession adult minimum")
        if 16 <= data.age_at_conviction <= 17:
            return MinimumSentenceDecision(True, 4.0, None, "Weapon possession youth DTO minimum")
        return MinimumSentenceDecision(False, None, None, "Under 16 at conviction")

    if code == "E":
        if adult:
            floor_pre = 6.0
            floor_post = 4.8 if guilty else 6.0
            return MinimumSentenceDecision(True, floor_pre, floor_post, "Threats with weapon adult minimum")
        if youth_16_17:
            return MinimumSentenceDecision(True, 4.0, None, "Threats with weapon youth DTO minimum")
        return MinimumSentenceDecision(False, None, None, "Under 16")

    return MinimumSentenceDecision(False, None, None, f"Unsupported minimum code {code}")


def is_forty_percent_regime(offence: OffenceRecord, term_months: float) -> bool:
    if term_months > 48 and offence.specified_violent:
        return False

    category = (offence.offence_category or "").lower()
    if "sexual offence" in category:
        return False

    provision = (offence.provision or "").lower()
    if "protection from harassment" in provision and "stalking" in provision:
        return False

    for marker in FORTY_PERCENT_EXCLUSIONS:
        if marker in provision:
            return False

    return True


def release_decision(data: SentenceCalculationInput, post_plea_term_months: float | None) -> ReleaseDecision:
    sentence_type = data.sentence_type
    offence = data.offence

    if sentence_type in {"mandatory_life_sentence", "discretionary_life_sentence"}:
        return ReleaseDecision(None, "Life sentence: release not represented as determinate fraction")

    if sentence_type in {"community_order", "youth_rehabilitation_order", "fine", "conditional_discharge"}:
        return ReleaseDecision(None, "Non-custodial sentence")

    if sentence_type == "suspended_sentence_order":
        return ReleaseDecision(None, "Suspended sentence: no immediate custody term")

    if post_plea_term_months is None:
        return ReleaseDecision(None, "No custodial term provided")

    if sentence_type in {"extended_sentence", "special_custodial_sentence"}:
        return ReleaseDecision(2.0 / 3.0, "Extended/special custodial release at two-thirds")

    if not is_custodial(sentence_type):
        return ReleaseDecision(None, "Sentence type not treated as custodial")

    term = post_plea_term_months
    life_max = has_life_maximum(offence)

    if term >= 84 and life_max and (offence.specified_sexual or offence.specified_violent):
        return ReleaseDecision(2.0 / 3.0, "Term >= 84m + life max + specified offence")

    if offence.schedule19za or data.terrorism_flag:
        return ReleaseDecision(2.0 / 3.0, "Schedule 19ZA / terrorism route")

    provision_or_name = f"{offence.provision} {offence.canonical_name}".lower()
    if term >= 48:
        if life_max and offence.specified_sexual:
            return ReleaseDecision(2.0 / 3.0, "Sexual offence with life max and term >= 48m")
        if any(marker in provision_or_name for marker in SERIOUS_PROVISION_MARKERS):
            return ReleaseDecision(2.0 / 3.0, "Specified serious offence marker with term >= 48m")

    forty_percent = is_forty_percent_regime(offence, term)
    if data.replicate_ace_release_bug:
        if forty_percent:
            return ReleaseDecision(0.5, "Replicating sentenceACE inconsistency for forty-percent regime")
        return ReleaseDecision(0.4, "Replicating sentenceACE inconsistency for non-forty-percent regime")

    if forty_percent:
        return ReleaseDecision(0.4, "Forty-percent regime")
    return ReleaseDecision(0.5, "Halfway release regime")


def sentence_after_plea(
    pre_plea_term_months: float | None,
    stage: str,
) -> float | None:
    if pre_plea_term_months is None:
        return None
    return round(pre_plea_term_months * plea_factor(stage), 2)


def apply_minimum_sentence_floor(
    pre_plea_term_months: float | None,
    post_plea_term_months: float | None,
    decision: MinimumSentenceDecision,
) -> tuple[float | None, float | None, list[str]]:
    trace: list[str] = []
    if not decision.triggered:
        return pre_plea_term_months, post_plea_term_months, trace

    adjusted_pre = pre_plea_term_months
    adjusted_post = post_plea_term_months

    if decision.floor_pre_months is not None:
        if adjusted_pre is None:
            adjusted_pre = decision.floor_pre_months
            trace.append(f"Pre-plea term set to minimum floor {decision.floor_pre_months} months")
        elif adjusted_pre < decision.floor_pre_months:
            trace.append(
                f"Pre-plea term raised from {adjusted_pre} to minimum floor {decision.floor_pre_months} months"
            )
            adjusted_pre = decision.floor_pre_months

    if decision.floor_post_months is not None:
        if adjusted_post is None:
            adjusted_post = decision.floor_post_months
            trace.append(f"Post-plea term set to minimum floor {decision.floor_post_months} months")
        elif adjusted_post < decision.floor_post_months:
            trace.append(
                f"Post-plea term raised from {adjusted_post} to minimum floor {decision.floor_post_months} months"
            )
            adjusted_post = decision.floor_post_months

    return adjusted_pre, adjusted_post, trace


def victim_surcharge(
    offence_date: date,
    age_at_offence: int,
    sentence_type: str,
    fine_amount: float | None,
    custodial_term_months: float | None,
) -> float:
    adult = age_at_offence >= 18

    if offence_date < date(2012, 10, 1):
        return 0.0

    if offence_date >= date(2022, 6, 16):
        adult_band = [26, 0, 2000, 114, 154, 187, 154, 187, 228]
        youth_band = [20, 26, 41]
        fine_pct = 0.40
    elif offence_date >= date(2020, 4, 14):
        adult_band = [22, 34, 190, 95, 128, 156, 128, 156, 190]
        youth_band = [17, 22, 34]
        fine_pct = 0.10
    elif offence_date >= date(2019, 6, 28):
        adult_band = [21, 32, 181, 90, 122, 149, 122, 149, 181]
        youth_band = [16, 21, 32]
        fine_pct = 0.10
    elif offence_date >= date(2016, 4, 8):
        adult_band = [20, 30, 170, 85, 115, 140, 115, 140, 170]
        youth_band = [15, 20, 30]
        fine_pct = 0.10
    else:
        adult_band = [15, 20, 120, 60, 80, 100, 80, 100, 120]
        youth_band = [10, 15, 20]
        fine_pct = 0.10

    if not adult:
        if sentence_type == "conditional_discharge":
            return float(youth_band[0])
        if sentence_type in {"fine", "youth_rehabilitation_order", "community_order"}:
            return float(youth_band[1])
        if sentence_type in CUSTODIAL_SENTENCE_TYPES or sentence_type == "suspended_sentence_order":
            return float(youth_band[2])
        return 0.0

    if sentence_type == "conditional_discharge":
        return float(adult_band[0])

    if sentence_type == "fine":
        if fine_amount is None:
            return 0.0
        if fine_pct == 0.40:
            return float(min(adult_band[2], round(fine_amount * fine_pct)))
        amount = round(fine_amount * fine_pct)
        return float(min(adult_band[2], max(adult_band[1], amount)))

    if sentence_type in {"community_order", "youth_rehabilitation_order"}:
        return float(adult_band[3])

    if sentence_type == "suspended_sentence_order":
        months = custodial_term_months or 0
        return float(adult_band[4] if months <= 6 else adult_band[5])

    if sentence_type in CUSTODIAL_SENTENCE_TYPES:
        months = custodial_term_months or 0
        if months <= 6:
            return float(adult_band[6])
        if months <= 24:
            return float(adult_band[7])
        return float(adult_band[8])

    return 0.0
