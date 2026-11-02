from decimal import Decimal

import pytest
from pydantic import ValidationError

from merchmind.comparison import compare_products, comparison_markdown
from merchmind.journey_models import ComparisonInput
from merchmind.models import NicheBrief, ResearchPolicy
from merchmind.starter import build_starter_profile


def profile_for(fixture):
    brief = NicheBrief(
        brief_id="fit-demo",
        merchant_id="cozy-vibe-demo",
        niche="desk accessories",
        description="Explore useful small accessories for home desks.",
        market_country="BD",
    )
    return build_starter_profile(brief, fixture["merchant"], ResearchPolicy())


def comparison_input(fixture, profile):
    evidence = fixture["bundle"]["sources"][0]
    return ComparisonInput(
        profile_id=profile.profile_id,
        profile_version=profile.profile_version,
        products=[
            {
                "product_id": "folding-stand",
                "name": "Synthetic folding stand",
                "variant": "small",
                "category": "desk-decor",
                "mass_g": "200",
                "facts": [
                    {
                        "attribute": "foldable",
                        "value": "true",
                        "evidence_ids": [evidence.evidence_id],
                    }
                ],
            }
        ],
        criteria=[
            {
                "criterion_id": "folding",
                "segment_id": "first-purchase",
                "hypothesis_field": "use_context",
                "description": "Merchant hypothesis: folding may help this use case",
                "product_attribute": "foldable",
                "operator": "equals",
                "expected_value": "true",
            }
        ],
        sources=[evidence],
    )


def test_feature_match_is_explicit_and_does_not_validate_customer_hypothesis(fixture):
    profile = profile_for(fixture)
    report = compare_products(comparison_input(fixture, profile), profile, fixture["merchant"])
    row = report.results[0]
    assert row.verdict == "possible_fit" and row.attribute_match_score == 100
    assert row.checks[0].original_hypothesis == profile.research.segments[0].use_context
    assert all(s.status == "unvalidated" for s in report.profile_snapshot.research.segments)
    assert all(r.attribute_match_score is None for r in report.results[1:])
    assert "no purchase prediction" in comparison_markdown(report)


@pytest.mark.parametrize("problem", ["missing", "unverified", "stale"])
def test_unknown_attributes_do_not_receive_match_points(fixture, problem):
    profile = profile_for(fixture)
    data = comparison_input(fixture, profile)
    if problem == "missing":
        data.products[0].facts = []
    elif problem == "unverified":
        data.sources[0].verification_status = "unverified"
    else:
        data.sources[0].freshness_status = "stale"
    row = compare_products(data, profile, fixture["merchant"]).results[0]
    assert row.coverage == 0 and row.attribute_match_score is None
    assert row.checks[0].status == "unknown"


def test_known_mismatch_is_different_from_missing_data(fixture):
    profile = profile_for(fixture)
    data = comparison_input(fixture, profile)
    data.products[0].facts[0].value = "false"
    row = compare_products(data, profile, fixture["merchant"]).results[0]
    assert row.coverage == 1 and row.attribute_match_score == 0
    assert row.verdict == "poor_fit" and row.checks[0].status == "mismatch"


def test_hard_product_mass_limit_overrides_good_feature_match(fixture):
    profile = profile_for(fixture)
    data = comparison_input(fixture, profile)
    data.products[0].mass_g = Decimal("900")
    assert compare_products(data, profile, fixture["merchant"]).results[0].verdict == "excluded"


def test_comparison_rejects_wrong_profile_version(fixture):
    profile = profile_for(fixture)
    data = comparison_input(fixture, profile)
    data.profile_version = "old-version"
    with pytest.raises(ValueError, match="exact profile"):
        compare_products(data, profile, fixture["merchant"])


def test_comparison_rejects_dangling_product_evidence(fixture):
    profile = profile_for(fixture)
    raw = comparison_input(fixture, profile).model_dump(mode="json")
    raw["products"][0]["facts"][0]["evidence_ids"] = ["ev-missing"]
    with pytest.raises(ValidationError, match="missing evidence"):
        ComparisonInput.model_validate(raw)
