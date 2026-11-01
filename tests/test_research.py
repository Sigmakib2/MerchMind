from datetime import timedelta
from decimal import Decimal

import pytest
from pydantic import ValidationError

from merchmind.models import Report, ScoringConfig, Signal
from merchmind.research import run


def research(fixture, **kwargs):
    bundle = fixture["bundle"] | kwargs
    return run(
        fixture["request"], fixture["merchant"], fixture["policy"], cost=fixture["cost"], **bundle
    )


def test_full_synthetic_research_decision(fixture):
    report = research(fixture)
    assert report.evaluation.decision == "test"
    assert report.evaluation.score == Decimal("81")
    assert report.evaluation.coverage == 1
    assert report.missing_evidence == []
    assert Report.model_validate_json(report.model_dump_json()) == report


def test_unknown_signals_do_not_receive_neutral_scores(fixture):
    report = research(fixture, signals={})
    assert report.evaluation.decision == "investigate"
    assert report.evaluation.score is None
    assert report.evaluation.coverage == Decimal("0.25")
    assert report.evaluation.components["customer_fit"] is None


def test_weights_must_sum_to_one():
    with pytest.raises(ValidationError):
        ScoringConfig.model_validate({"weights": {"customer_fit": "0.5"}})


def test_negative_conservative_margin_is_hard_rejection(fixture):
    fixture["cost"].scenarios[2].selling_price_net = Decimal("300")
    report = research(fixture)
    assert report.evaluation.decision == "reject"
    assert any("not positive" in x for x in report.evaluation.blockers)


def test_excluded_category_is_hard_rejection(fixture):
    fixture["request"].category = "regulated-products"
    assert research(fixture).evaluation.decision == "reject"


def test_excess_mass_is_hard_rejection(fixture):
    fixture["cost"].scenarios[2].mass_g = Decimal("1000")
    assert research(fixture).evaluation.decision == "reject"


def test_ambiguous_variants_require_review(fixture):
    fixture["request"].product_variant_key = None
    fixture["cost"] = None
    report = research(fixture)
    assert report.product_identity.match_status == "needs_review"
    assert report.evaluation.decision == "investigate"


def test_similar_lamp_is_not_exact_comparable(fixture):
    fixture["bundle"]["comparables"][0].product_variant_key = "lamp-b:rgb-battery"
    assert research(fixture).evaluation.decision == "investigate"


@pytest.mark.parametrize(
    "failure", ["advertised", "expired", "unverified_checklist", "wrong_variant"]
)
def test_supplier_listing_does_not_replace_verified_quote(fixture, failure):
    quote = fixture["bundle"]["quotes"][0]
    if failure == "advertised":
        quote.quote_type = "advertised"
    elif failure == "expired":
        quote.quoted_at -= timedelta(days=30)
        quote.valid_until -= timedelta(days=20)
    elif failure == "unverified_checklist":
        quote.verification_checks = {}
    else:
        quote.product_variant_key = "lamp-b:rgb-battery"
    assert research(fixture).evaluation.decision == "investigate"


def test_evidence_ids_must_exist(fixture):
    fixture["cost"].fx.evidence_id = "ev-missing"
    with pytest.raises(ValueError, match="missing evidence"):
        research(fixture)


def test_unverified_page_cannot_support_a_score(fixture):
    fixture["bundle"]["sources"][3].verification_status = "unverified"
    with pytest.raises(ValueError, match="Scoring signals"):
        research(fixture)


def test_reserved_economic_score_cannot_override_arithmetic(fixture):
    signal = next(iter(fixture["bundle"]["signals"].values()))
    fixture["bundle"]["signals"]["contribution_economics"] = signal
    with pytest.raises(ValueError, match="computed by the engine"):
        research(fixture)


def test_source_budget_enforced(fixture):
    fixture["request"].max_sources = 2
    with pytest.raises(ValueError, match="budget"):
        research(fixture)


def test_unavailable_inputs_produce_valid_partial_report(fixture):
    fixture["request"].safety_review = "pending"
    fixture["request"].safety_evidence_ids = []
    report = run(fixture["request"], fixture["merchant"], fixture["policy"])
    assert report.evaluation.decision == "investigate"
    assert report.economics.status == "not_estimated"
    assert report.source_statuses[0]["status"] == "not_fetched"
    assert report.missing_evidence


def test_dangling_supplier_reference_rejected(fixture):
    fixture["bundle"]["quotes"][0].evidence_ids = ["ev-nonexistent"]
    with pytest.raises(ValidationError, match="Unknown evidence"):
        research(fixture)


def test_signal_rejects_unbounded_scores():
    with pytest.raises(ValidationError):
        Signal(score="101", evidence_ids=["ev-a"], rationale="test")
