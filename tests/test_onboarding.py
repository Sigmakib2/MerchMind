import pytest

from merchmind.economics import estimate
from merchmind.journey_models import OnboardingAnswers
from merchmind.models import Merchant
from merchmind.onboarding import onboard, prompt_answers
from merchmind.storage import load


def answers():
    return OnboardingAnswers(
        merchant_id="fresh-store",
        business_name="Fresh Store",
        market_country="BD",
        base_currency="BDT",
        niche="computer accessories",
        description="Explore lightweight useful accessories for a small desk setup.",
        max_product_mass_g="300",
        sourcing_hosts=["example.com"],
    )


def test_intake_creates_real_config_without_sales_or_demo_values(tmp_path):
    workspace = tmp_path / "store"
    paths, warnings = onboard(answers(), workspace)
    merchant = Merchant.model_validate(load(workspace / "merchant.yaml"))
    assert merchant.merchant_id == "fresh-store"
    assert merchant.freight.rate is None
    assert merchant.finance.merchant_vat_treatment == "unknown"
    assert load(workspace / "niche-brief.json")["niche"] == "computer accessories"
    assert not (workspace / "data").exists()
    assert len(paths) == 7 and warnings


def test_onboarding_does_not_overwrite(tmp_path):
    onboard(answers(), tmp_path / "store")
    with pytest.raises(ValueError, match="empty"):
        onboard(answers(), tmp_path / "store")


def test_unknown_freight_is_not_free_shipping(fixture):
    fixture["merchant"].freight.rate = None
    result = estimate(fixture["cost"], fixture["merchant"])
    assert result.status == "not_estimated"
    assert all(
        s.breakdown["freight_local"] is None and "freight rate" in s.missing
        for s in result.scenarios
    )


def test_interactive_questions_keep_prompts_off_json_output(monkeypatch, capsys):
    values = iter(
        [
            "My Store",
            "my-store",
            "BD",
            "BDT",
            "CN",
            "desk accessories",
            "Small useful products for home desk setups.",
            "home workers",
            "no heavy products",
            "",
            "example.com",
            "English",
            "400",
            "30",
            "",
            "10000",
        ]
    )
    monkeypatch.setattr("builtins.input", lambda: next(values))
    result = prompt_answers()
    output = capsys.readouterr()
    assert output.out == "" and "Business name" in output.err
    assert result.startup_budget_local == 10000
    assert result.freight_rate_per_gram is None


def test_invalid_interactive_margin_has_a_clear_error_and_writes_nothing(
    monkeypatch, capsys, tmp_path
):
    from merchmind.cli import main

    values = iter(
        [
            "My Store",
            "my-store",
            "BD",
            "BDT",
            "CN",
            "desk accessories",
            "Small useful products for home desk setups.",
            "",
            "",
            "",
            "",
            "English",
            "400",
            "not-a-number",
        ]
    )
    monkeypatch.setattr("builtins.input", lambda: next(values))
    workspace = tmp_path / "store"
    assert main(["onboard", "--workspace", str(workspace)]) == 2
    assert "Invalid decimal" in capsys.readouterr().out
    assert not workspace.exists()
