from datetime import date

import pytest

from sentence_chat_product.core.calculator import calculate_sentence
from sentence_chat_product.core.rules import minimum_sentence_decision, release_decision, victim_surcharge
from sentence_chat_product.core.types import OffenceRecord, SentenceCalculationInput


def make_offence(**overrides):
    base = {
        "offence_id": "00000000-0000-0000-0000-000000000001",
        "canonical_name": "Test offence",
        "short_name": "Test offence",
        "offence_category": "Assault offences",
        "provision": "Offences Against the Person Act 1861 s.18",
        "guideline_url": "",
        "legislation_url": "",
        "maximum_sentence_type": "custody",
        "maximum_sentence_amount": "Life",
        "minimum_sentence_code": "",
        "specified_violent": True,
        "specified_sexual": False,
        "specified_terrorist": False,
        "listed_offence": False,
        "schedule18a_offence": False,
        "schedule19za": False,
        "cta_notification": False,
    }
    base.update(overrides)
    return OffenceRecord(**base)


def make_input(**overrides):
    base = {
        "offence": make_offence(),
        "offence_date": date(2024, 1, 1),
        "conviction_date": date(2024, 3, 1),
        "sentence_date": date(2024, 5, 1),
        "age_at_offence": 30,
        "age_at_conviction": 30,
        "age_at_sentence": 30,
        "plea_stage": "first_stage",
        "sentence_type": "determinate_custodial_sentence",
        "pre_plea_term_months": 24.0,
    }
    base.update(overrides)
    return SentenceCalculationInput(**base)


def test_minimum_sentence_a_triggered():
    data = make_input(
        offence=make_offence(minimum_sentence_code="A"),
        prior_domestic_burglary_count=2,
    )
    decision = minimum_sentence_decision(data)
    assert decision.triggered is True
    assert decision.floor_pre_months == 36.0
    assert decision.floor_post_months == pytest.approx(28.8)


def test_minimum_sentence_c1_no_plea_below_floor():
    data = make_input(
        offence=make_offence(minimum_sentence_code="C1"),
        offence_date=date(2024, 1, 1),
        pre_plea_term_months=36,
    )
    decision = minimum_sentence_decision(data)
    assert decision.triggered is True
    assert decision.floor_pre_months == 60.0
    assert decision.floor_post_months == 60.0


def test_release_bug_mode_for_forty_percent_regime():
    data = make_input(
        offence=make_offence(
            specified_violent=False,
            maximum_sentence_amount="10 years",
            provision="Theft Act 1968 s.1",
            offence_category="Theft offences",
        ),
        pre_plea_term_months=12,
        replicate_ace_release_bug=True,
    )
    decision = release_decision(data, post_plea_term_months=8)
    assert decision.release_fraction == 0.5


def test_victim_surcharge_2022_adult_fine():
    amount = victim_surcharge(
        offence_date=date(2024, 1, 1),
        age_at_offence=35,
        sentence_type="fine",
        fine_amount=1000,
        custodial_term_months=None,
    )
    assert amount == 400


def test_calculate_sentence_applies_floor_and_release():
    data = make_input(
        offence=make_offence(minimum_sentence_code="A", specified_violent=False),
        prior_domestic_burglary_count=2,
        pre_plea_term_months=24,
        replicate_ace_release_bug=False,
    )
    result = calculate_sentence(data, matrix_rows=[])
    assert result.minimum_sentence_triggered is True
    assert result.pre_plea_term_months == 36.0
    assert result.post_plea_term_months == pytest.approx(28.8)
    assert result.release_fraction in {0.4, 0.5, 2.0 / 3.0}
