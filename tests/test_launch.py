from decimal import Decimal

import pytest

from merchmind.journey_models import LaunchInput
from merchmind.launch import estimate_launch


def launch_input(fixture, **updates):
    data = dict(
        currency="BDT",
        cost_input=fixture["cost"],
        supplier_quote=fixture["bundle"]["quotes"][0],
        order_quantity=100,
        sample_cost_local="500",
        setup_cost_local="1000",
        initial_ad_budget_local="2000",
        upfront_selling_costs_local="0",
        working_capital_reserve_local="3000",
        contingency_ratio="0.10",
        available_budget_local="62000",
        cash_evidence_ids=[fixture["bundle"]["sources"][1].evidence_id],
        sources=fixture["bundle"]["sources"],
    )
    return LaunchInput(**(data | updates))


def test_launch_cash_matches_independent_batch_calculation(fixture):
    report = estimate_launch(launch_input(fixture), fixture["merchant"])
    # Conservative: imports 494*100 + packaging 20*100 + samples 500
    # + setup 1000 + ads 2000 = 54900; 10% contingency + 3000 reserve = 63390.
    assert [s.required_cash for s in report.scenarios] == [
        Decimal("59650"),
        Decimal("61520"),
        Decimal("63390"),
    ]
    assert report.scenarios[-1].budget_status == "over_budget"
    assert report.scenarios[1].budget_status == "within_budget"


def test_recoverable_vat_is_still_upfront_cash(fixture):
    original = estimate_launch(launch_input(fixture), fixture["merchant"])
    fixture["merchant"].finance.merchant_vat_treatment = "recoverable"
    result = estimate_launch(launch_input(fixture), fixture["merchant"])
    assert result.scenarios[-1].required_cash == original.scenarios[-1].required_cash
    assert result.economics.scenarios[-1].landed == original.economics.scenarios[-1].landed - 20


def test_initial_ads_are_not_double_counted_as_per_sale_marketing(fixture):
    original = estimate_launch(launch_input(fixture), fixture["merchant"])
    fixture["cost"].scenarios[-1].marketing_cost = Decimal("999")
    result = estimate_launch(launch_input(fixture), fixture["merchant"])
    assert result.scenarios[-1].required_cash == original.scenarios[-1].required_cash
    assert (
        result.economics.scenarios[-1].contribution != original.economics.scenarios[-1].contribution
    )


@pytest.mark.parametrize(
    "field",
    [
        "sample_cost_local",
        "setup_cost_local",
        "initial_ad_budget_local",
        "working_capital_reserve_local",
        "contingency_ratio",
    ],
)
def test_unknown_launch_amounts_never_become_zero(fixture, field):
    report = estimate_launch(launch_input(fixture, **{field: None}), fixture["merchant"])
    assert all(s.required_cash is None and s.status == "not_estimated" for s in report.scenarios)


def test_supplier_moq_is_enforced(fixture):
    with pytest.raises(ValueError, match="below the supplier MOQ"):
        estimate_launch(launch_input(fixture, order_quantity=9), fixture["merchant"])


def test_tier_prices_are_checked_against_actual_order_size(fixture):
    report = estimate_launch(launch_input(fixture, order_quantity=10), fixture["merchant"])
    assert (
        report.scenarios[0].required_cash is None
    )  # 10 CNY assumed versus confirmed 12 CNY at this tier.
    assert report.scenarios[-1].required_cash is not None


def test_unknown_available_budget_does_not_prevent_cost_estimate(fixture):
    report = estimate_launch(
        launch_input(fixture, available_budget_local=None), fixture["merchant"]
    )
    assert all(
        s.required_cash is not None and s.budget_status == "budget_unknown"
        for s in report.scenarios
    )
