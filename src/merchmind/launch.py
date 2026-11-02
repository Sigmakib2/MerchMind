"""Deterministic startup cash planning; no purchases or invented financial inputs."""

from decimal import localcontext

from merchmind.economics import estimate
from merchmind.journey_models import LaunchInput, LaunchReport, LaunchScenario
from merchmind.models import Merchant
from merchmind.reports import amount, escape
from merchmind.storage import now


def estimate_launch(data: LaunchInput, merchant: Merchant) -> LaunchReport:
    at = now()
    quote = data.supplier_quote
    cost = data.cost_input
    if data.currency != merchant.base_currency:
        raise ValueError("Launch cash amounts must use the merchant base currency")
    if quote.product_variant_key != cost.product_variant_key:
        raise ValueError("Launch quote and cost scenarios must describe the same product variant")
    if data.order_quantity < quote.moq:
        raise ValueError("Order quantity is below the supplier MOQ")
    tier = max(
        (p for p in quote.price_tiers if p.min_qty <= data.order_quantity), key=lambda p: p.min_qty
    )
    if tier.currency != cost.fx.source_currency:
        raise ValueError("Supplier quote currency differs from the cost input source currency")
    economics = estimate(cost, merchant, at=at)
    usable = {
        e.evidence_id
        for e in data.sources
        if e.verification_status in {"verified", "merchant_provided"}
        and e.freshness_status == "current"
        and e.retrieved_at <= at
    }
    shared_missing = []
    needed = set(economics.evidence_ids + quote.evidence_ids + data.cash_evidence_ids)
    if not needed <= usable:
        shared_missing.append("Current reviewed cost, quote and startup-cash evidence")
    checklist = {"supplier_identity", "product_authenticity", "trade_terms", "sample_policy"}
    if (
        quote.quote_type != "confirmed"
        or quote.quoted_at > at
        or quote.valid_until is None
        or quote.valid_until < at
        or quote.verification_flags
        or not all(quote.verification_checks.get(k) is True for k in checklist)
    ):
        shared_missing.append(
            "Current confirmed supplier quote and completed verification checklist"
        )
    scenarios = []
    with localcontext() as context:
        context.prec = 38
        for original, result in zip(cost.scenarios, economics.scenarios, strict=True):
            missing = list(shared_missing)
            if original.unit_price_source < tier.unit_price:
                missing.append(
                    "Scenario purchase price is below the confirmed tier applicable to this order quantity"
                )
            import_keys = (
                "purchase_local",
                "freight_local",
                "import_duties",
                "brokerage",
                "local_inbound",
                "other_import_costs",
            )
            import_values = [result.breakdown[key] for key in import_keys]
            vat = (
                original.import_vat
                if original.tax_inputs_confirmed and original.tax_evidence_ids
                else None
            )
            if vat is None or any(v is None for v in import_values):
                import_cash = None
                missing.append("Complete purchase, freight and confirmed import-tax cash amounts")
            else:
                # All import VAT is cash paid up front, even if it is later recoverable.
                import_cash = (sum(import_values) + vat) * data.order_quantity
            items = {
                "import_cash_including_all_vat": import_cash,
                "initial_packaging_stock": original.packaging * data.order_quantity
                if original.packaging is not None
                else None,
                "samples": data.sample_cost_local,
                "setup": data.setup_cost_local,
                "initial_ad_budget": data.initial_ad_budget_local,
                "upfront_selling_costs": data.upfront_selling_costs_local,
                "working_capital_reserve": data.working_capital_reserve_local,
            }
            for key, value in items.items():
                if value is None:
                    missing.append(key)
            if data.contingency_ratio is None:
                missing.append("contingency_ratio")
            subtotal = (
                None
                if any(v is None for v in items.values())
                else sum(v for key, v in items.items() if key != "working_capital_reserve")
            )
            contingency = (
                subtotal * data.contingency_ratio
                if subtotal is not None and data.contingency_ratio is not None
                else None
            )
            items["contingency"] = contingency
            total = (
                subtotal + contingency + data.working_capital_reserve_local if not missing else None
            )
            balance = (
                data.available_budget_local - total
                if total is not None and data.available_budget_local is not None
                else None
            )
            budget_status = (
                "not_estimated"
                if total is None
                else "budget_unknown"
                if balance is None
                else "within_budget"
                if balance >= 0
                else "over_budget"
            )
            scenarios.append(
                LaunchScenario(
                    name=original.name,
                    status="estimated" if total is not None else "not_estimated",
                    cash_items=items,
                    required_cash=total,
                    budget_status=budget_status,
                    budget_remaining=balance,
                    missing=sorted(set(missing)),
                )
            )
    return LaunchReport(
        estimated_at=at,
        merchant_id=merchant.merchant_id,
        currency=merchant.base_currency,
        order_quantity=data.order_quantity,
        scenarios=scenarios,
        economics=economics,
        input_snapshot=data,
        merchant_snapshot=merchant,
        sources=data.sources,
        assumptions=[
            "All ordered units are assumed sellable. Batch/import charges must already be allocated consistently in the supplied per-unit cost inputs.",
            "All import VAT is included in upfront cash. Recoverable VAT is excluded from product expense by the economics engine, but no immediate tax refund is assumed.",
            "Packaging for the full order is bought up front. Fulfillment/payment costs are paid from sales unless explicitly included in upfront selling costs.",
            "Initial advertising is counted once as the supplied launch budget, not again as per-sale marketing cost multiplied by stock quantity.",
            "Contingency applies to upfront costs before the working-capital reserve. The reserve is cash held aside, not an expense or an automatic cash-flow forecast.",
            "Sample/setup costs and other one-off launch costs are not silently folded into per-unit contribution. This is a scenario estimate, not an order or a guarantee of sufficient capital.",
        ],
    )


def launch_markdown(report: LaunchReport) -> str:
    lines = [
        "# Total launch cash estimate",
        "",
        f"Currency: {report.currency}. Order quantity: {report.order_quantity} units.",
        "",
        "| Scenario | Required cash | Remaining budget | Result |",
        "| --- | ---: | ---: | --- |",
    ]
    for scenario in report.scenarios:
        lines.append(
            f"| {scenario.name} | {amount(scenario.required_cash)} | {amount(scenario.budget_remaining)} | {scenario.budget_status} |"
        )
        lines.extend(
            [
                "",
                f"## {scenario.name.title()} cash breakdown",
                "",
                "| Item | Amount |",
                "| --- | ---: |",
            ]
        )
        lines.extend(
            f"| {escape(key)} | {amount(value)} |" for key, value in scenario.cash_items.items()
        )
        lines.extend(f"- Missing: {escape(v)}" for v in scenario.missing)
    lines.extend(["", "## Assumptions", "", *(f"- {escape(v)}" for v in report.assumptions)])
    return "\n".join(lines)
