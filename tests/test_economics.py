from datetime import timedelta
from decimal import Decimal, localcontext

import pytest
from pydantic import ValidationError

from merchmind.economics import estimate
from merchmind.models import CostInput, Merchant


def test_independent_golden_costs(fixture):
    result = estimate(fixture["cost"], fixture["merchant"])
    # Hand calculation, conservative: 12*17 + 200 + 40+20+10+15+5 = 494.
    # Contribution = 1100 - 494 - (20+60+15+150+30) = 331.
    expected = {
        "optimistic": ("460", "585"),
        "base": ("477", "498"),
        "conservative": ("494", "331"),
    }
    for scenario in result.scenarios:
        landed, contribution = expected[scenario.name]
        assert scenario.landed == Decimal(landed)
        assert scenario.contribution == Decimal(contribution)
        with localcontext() as context:
            context.prec = 38
            assert (
                scenario.contribution_margin
                == scenario.contribution / scenario.breakdown["selling_price_net"]
            )


def test_recoverable_vat_is_not_an_expense(fixture):
    merchant = fixture["merchant"].model_copy(deep=True)
    merchant.finance.merchant_vat_treatment = "recoverable"
    result = estimate(fixture["cost"], merchant)
    assert result.scenarios[-1].landed == Decimal("474")
    assert result.scenarios[-1].breakdown["nonrecoverable_vat"] == 0


@pytest.mark.parametrize(
    "field",
    [
        "import_duties",
        "import_vat",
        "mass_g",
        "packaging_mass_g",
        "marketing_cost",
        "brokerage",
        "expected_return_loss",
    ],
)
def test_missing_cost_is_not_zero(fixture, field):
    cost = fixture["cost"].model_copy(deep=True)
    setattr(cost.scenarios[1], field, None)
    result = estimate(cost, fixture["merchant"])
    assert result.status == "not_estimated"
    assert result.scenarios[1].landed is None
    assert result.scenarios[1].contribution is None
    assert result.scenarios[1].missing


def test_unknown_vat_treatment_blocks_totals(fixture):
    merchant = fixture["merchant"].model_copy(deep=True)
    merchant.finance.merchant_vat_treatment = "unknown"
    assert estimate(fixture["cost"], merchant).status == "not_estimated"


def test_unconfirmed_taxes_are_not_displayed_as_verified(fixture):
    fixture["cost"].scenarios[0].tax_inputs_confirmed = False
    scenario = estimate(fixture["cost"], fixture["merchant"]).scenarios[0]
    assert scenario.status == "not_estimated"
    assert scenario.breakdown["import_duties"] is None


@pytest.mark.parametrize("days", [-1, 31])
def test_future_and_stale_fx_block_totals(fixture, days):
    cost = fixture["cost"]
    result = estimate(cost, fixture["merchant"], at=cost.fx.as_of + timedelta(days=days))
    assert result.status == "not_estimated"
    assert result.scenarios[0].breakdown["purchase_local"] is None


def test_freight_uses_greater_of_actual_and_volumetric_mass(fixture):
    fixture["cost"].scenarios[0].volumetric_mass_g = Decimal("350")
    result = estimate(fixture["cost"], fixture["merchant"])
    assert result.scenarios[0].breakdown["freight_local"] == 350


def test_minimum_and_fixed_freight(fixture):
    merchant = fixture["merchant"]
    merchant.freight.minimum_charge = Decimal("250")
    assert estimate(fixture["cost"], merchant).scenarios[0].breakdown["freight_local"] == 250
    merchant.freight.mode = "fixed_per_unit"
    merchant.freight.rate = Decimal("300")
    assert estimate(fixture["cost"], merchant).scenarios[0].breakdown["freight_local"] == 300


@pytest.mark.parametrize("value", [12.34, "NaN", "Infinity", "-1"])
def test_invalid_money_rejected(fixture, value):
    raw = fixture["raw"]["cost"]
    raw["scenarios"][0]["unit_price_source"] = value
    with pytest.raises(ValidationError):
        CostInput.model_validate(raw)


def test_decimal_precision_no_binary_float(fixture):
    fixture["cost"].fx.rate = Decimal("0.1")
    fixture["cost"].scenarios[0].unit_price_source = Decimal("0.2")
    assert estimate(fixture["cost"], fixture["merchant"]).scenarios[0].breakdown[
        "purchase_local"
    ] == Decimal("0.02")


def test_mismatched_currencies_rejected(fixture):
    fixture["cost"].fx.target_currency = "USD"
    with pytest.raises(ValueError, match="FX target"):
        estimate(fixture["cost"], fixture["merchant"])


def test_invalid_financial_unit_and_country_rejected(fixture):
    raw = fixture["raw"]["merchant"]
    raw["freight"]["mode"] = "per_kg"
    with pytest.raises(ValidationError):
        Merchant.model_validate(raw)
    raw["freight"]["mode"] = "per_gram"
    raw["market_country"] = "XX"
    with pytest.raises(ValidationError):
        Merchant.model_validate(raw)


def test_explicit_kilograms_normalize_to_grams_and_preserve_input(fixture):
    raw = fixture["raw"]["cost"]
    scenario = raw["scenarios"][0]
    scenario.pop("mass_g")
    scenario.pop("packaging_mass_g")
    scenario["mass"] = {"value": "0.18", "unit": "kg"}
    scenario["packaging_mass"] = {"value": "0.02", "unit": "kg"}
    cost = CostInput.model_validate(raw)
    assert cost.scenarios[0].mass_g == 180
    result = estimate(cost, fixture["merchant"])
    assert result.scenarios[0].breakdown["freight_local"] == 200
    assert result.input_snapshot.scenarios[0].mass.unit == "kg"


def test_conflicting_mass_units_are_rejected(fixture):
    raw = fixture["raw"]["cost"]
    raw["scenarios"][0]["mass"] = {"value": "180", "unit": "kg"}
    with pytest.raises(ValidationError, match="conflicts"):
        CostInput.model_validate(raw)
