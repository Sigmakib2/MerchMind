"""Pure decimal arithmetic. No networking, model calls, or invented taxes."""

from datetime import datetime
from decimal import Decimal, localcontext

from merchmind.models import CostInput, Economics, Merchant, ScenarioResult
from merchmind.storage import now


def estimate(cost: CostInput, merchant: Merchant, *, at: datetime | None = None) -> Economics:
    at = at or now()
    if cost.merchant_id != merchant.merchant_id:
        raise ValueError("Cost inputs belong to a different merchant")
    if cost.destination_country != merchant.market_country:
        raise ValueError("Cost destination differs from merchant market")
    if cost.origin_country not in merchant.source_countries:
        raise ValueError("Cost origin is outside configured source countries")
    if cost.fx.target_currency != merchant.base_currency:
        raise ValueError("FX target differs from merchant base currency")
    if cost.fx.source_currency == cost.fx.target_currency and cost.fx.rate != 1:
        raise ValueError("Same-currency FX must equal 1")
    fx_age = (at - cost.fx.as_of).total_seconds() / 86400
    fx_valid = 0 <= fx_age <= merchant.finance.max_fx_age_days
    scenarios = []
    evidence_ids = set(cost.evidence_ids) | {cost.fx.evidence_id}
    for scenario in cost.scenarios:
        evidence_ids.update(scenario.tax_evidence_ids)
        missing = []
        if merchant.freight.rate is None:
            missing.append("freight rate")
        if not fx_valid:
            missing.append("current dated exchange rate")
        taxes_confirmed = scenario.tax_inputs_confirmed and bool(scenario.tax_evidence_ids)
        if not taxes_confirmed:
            missing.append("merchant-confirmed tax inputs with evidence")
        if merchant.finance.merchant_vat_treatment == "unknown":
            missing.append("merchant VAT treatment")
        fields = (
            "import_duties",
            "import_vat",
            "brokerage",
            "local_inbound",
            "other_import_costs",
            "packaging",
            "fulfillment",
            "payment_fee",
            "marketing_cost",
            "expected_return_loss",
        )
        for field in fields:
            if getattr(scenario, field) is None:
                missing.append(field)
        with localcontext() as context:
            context.prec = 38
            purchase = scenario.unit_price_source * cost.fx.rate + scenario.fixed_sourcing_per_unit
            weight = None
            freight = None
            if merchant.freight.mode == "per_gram":
                if scenario.mass_g is None or scenario.packaging_mass_g is None:
                    missing.append("product and shipping packaging mass")
                else:
                    weight = max(
                        scenario.mass_g + scenario.packaging_mass_g,
                        scenario.volumetric_mass_g or Decimal("0"),
                    )
                    if merchant.freight.rate is not None:
                        freight = max(
                            weight * merchant.freight.rate, merchant.freight.minimum_charge
                        )
            else:
                if merchant.freight.rate is not None:
                    freight = max(merchant.freight.rate, merchant.freight.minimum_charge)
            vat = None
            if (
                scenario.import_vat is not None
                and merchant.finance.merchant_vat_treatment != "unknown"
            ):
                vat = (
                    Decimal("0")
                    if merchant.finance.merchant_vat_treatment == "recoverable"
                    else scenario.import_vat
                )
            breakdown = {
                "purchase_local": purchase if fx_valid else None,
                "billable_mass_g": weight,
                "freight_local": freight,
                "import_duties": scenario.import_duties if taxes_confirmed else None,
                "nonrecoverable_vat": vat if taxes_confirmed else None,
                "brokerage": scenario.brokerage,
                "local_inbound": scenario.local_inbound,
                "other_import_costs": scenario.other_import_costs,
                "selling_price_net": scenario.selling_price_net,
                "packaging": scenario.packaging,
                "fulfillment": scenario.fulfillment,
                "payment_fee": scenario.payment_fee,
                "marketing_cost": scenario.marketing_cost,
                "expected_return_loss": scenario.expected_return_loss,
            }
            landed = contribution = margin = None
            if not missing:
                landed = sum(
                    breakdown[key]
                    for key in (
                        "purchase_local",
                        "freight_local",
                        "import_duties",
                        "nonrecoverable_vat",
                        "brokerage",
                        "local_inbound",
                        "other_import_costs",
                    )
                )
                contribution = (
                    scenario.selling_price_net
                    - landed
                    - sum(
                        getattr(scenario, key)
                        for key in (
                            "packaging",
                            "fulfillment",
                            "payment_fee",
                            "marketing_cost",
                            "expected_return_loss",
                        )
                    )
                )
                margin = contribution / scenario.selling_price_net
            scenarios.append(
                ScenarioResult(
                    name=scenario.name,
                    status="not_estimated" if missing else "complete",
                    missing=missing,
                    currency=merchant.base_currency,
                    breakdown=breakdown,
                    landed=landed,
                    contribution=contribution,
                    contribution_margin=margin,
                )
            )
    return Economics(
        status="complete" if all(s.status == "complete" for s in scenarios) else "not_estimated",
        scenarios=scenarios,
        evidence_ids=sorted(evidence_ids),
        input_snapshot=cost,
        assumptions=[
            "All costs are per sellable unit; batch charges must be allocated before input.",
            "Selling prices exclude collected sales tax; import tax amounts are merchant-confirmed inputs.",
            "Freight excludes customs. FX and cost assumptions are preserved in the input snapshot.",
            "Recoverable import VAT is excluded from expense, but still requires working capital.",
        ],
    )
