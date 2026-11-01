from decimal import ROUND_HALF_UP, Decimal
from pathlib import Path

from merchmind.models import Report
from merchmind.storage import jsonl, write


def escape(value: object) -> str:
    return (
        str(value)
        .replace("\\", "\\\\")
        .replace("|", "\\|")
        .replace("\n", " ")
        .replace("\r", " ")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace("[", "\\[")
        .replace("]", "\\]")
        .replace("`", "\\`")
    )


def amount(value: Decimal | None) -> str:
    return (
        "Unknown" if value is None else str(value.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP))
    )


def markdown(report: Report) -> str:
    result = [
        f"# Product evaluation for {escape(report.product_identity.name)}",
        "",
        f"Decision: **{report.evaluation.decision.upper()}**",
        "",
        f"Merchant: {escape(report.merchant_snapshot.name)} | Run: {report.run_id} | Date: {report.run_at.isoformat()}",
        "",
        f"Variant: {escape(report.product_identity.variant or 'unresolved')} ({report.product_identity.match_status})",
        "",
        f"Score: {amount(report.evaluation.score)}/100 | Evidence coverage: {amount(report.evaluation.coverage * 100)}%",
        "",
        report.evaluation.rationale,
        "",
        "## Economics",
        "",
        f"Currency: {report.merchant_snapshot.base_currency}. All values per sellable unit; prices exclude collected tax.",
        "",
        "| Scenario | Landed cost | Contribution | Margin | Status |",
        "| --- | ---: | ---: | ---: | --- |",
    ]
    for scenario in report.economics.scenarios:
        margin = (
            "Unknown"
            if scenario.contribution_margin is None
            else amount(scenario.contribution_margin * 100) + "%"
        )
        result.append(
            f"| {scenario.name} | {amount(scenario.landed)} | {amount(scenario.contribution)} | {margin} | {scenario.status} |"
        )
    if not report.economics.scenarios:
        result.append("| No inputs | Unknown | Unknown | Unknown | not_estimated |")
    for scenario in report.economics.scenarios:
        result.extend(
            [
                "",
                f"### {scenario.name.title()} breakdown",
                "",
                "| Item | Amount |",
                "| --- | ---: |",
            ]
        )
        result.extend(
            f"| {escape(key)} | {amount(value)} |" for key, value in scenario.breakdown.items()
        )
        if scenario.missing:
            result.extend(["", "Missing: " + ", ".join(escape(m) for m in scenario.missing)])
    result.extend(
        [
            "",
            "## Score components",
            "",
            "| Criterion | Score | Evidence and rationale |",
            "| --- | ---: | --- |",
        ]
    )
    for key, signal in report.evaluation.components.items():
        result.append(
            f"| {key} | {amount(signal.score) if signal else 'Unscored'} | {escape(', '.join(signal.evidence_ids) + ': ' + signal.rationale) if signal else 'Insufficient evidence'} |"
        )
    result.extend(["", "## Supplier options", ""])
    if not report.supplier_options:
        result.append("No supplier terms imported.")
    for quote in report.supplier_options:
        result.extend(
            [
                f"- {escape(quote.supplier_id)}: {quote.quote_type}; variant {escape(quote.product_variant_key)}; MOQ {quote.moq}; evidence {', '.join(quote.evidence_ids)}.",
                f"  Price tiers: {escape('; '.join(f'{p.min_qty}+ at {p.unit_price} {p.currency}' for p in quote.price_tiers))}. Verification flags: {escape(', '.join(quote.verification_flags) or 'none declared by merchant')}.",
            ]
        )
    result.extend(["", "## Local comparables", ""])
    if not report.local_comparables:
        result.append("No local market comparables imported.")
    for item in report.local_comparables:
        result.append(
            f"- {escape(item.retailer)}: {item.price} {item.currency}, {item.price_type}, {item.product_match_type} match; evidence {item.evidence_id}."
        )
    result.extend(["", "## Missing evidence and blockers", ""])
    result.extend(f"- {escape(item)}" for item in report.missing_evidence)
    if not report.missing_evidence:
        result.append("No configured blockers. Review evidence and supplier terms before sampling.")
    result.extend(["", "## Assumptions", ""])
    result.extend(f"- {escape(item)}" for item in report.economics.assumptions)
    result.extend(["", "## Source access", ""])
    result.extend(
        f"- {escape(s.get('source'))}: {escape(s.get('status'))}; {escape(s.get('reason', 'Manual fact review required'))}."
        for s in report.source_statuses
    )
    result.extend(["", "## Evidence manifest", ""])
    for evidence in report.sources:
        link = (
            f"[source](<{evidence.source_uri}>)"
            if evidence.source_uri
            else "private merchant record"
        )
        result.append(
            f"- **{evidence.evidence_id}**: {escape(evidence.assertion)} ({evidence.verification_status}, {evidence.freshness_status}, {evidence.retrieved_at.isoformat()}); {link}."
        )
    result.extend(
        [
            "",
            "Inputs, full-precision arithmetic, policy versions and source hashes are preserved in report.json.",
            "",
        ]
    )
    return "\n".join(result)


def save_report(report: Report, root: Path) -> list[Path]:
    rendered = markdown(report)
    manifest = jsonl(report.sources)
    total_bytes = (
        len(report.model_dump_json(indent=2).encode())
        + len(rendered.encode())
        + len(manifest.encode())
    )
    if total_bytes > report.research_policy.max_report_bytes:
        raise ValueError("Report exceeds configured storage budget")
    target = root / report.run_id
    target.mkdir(parents=True, exist_ok=False)
    return [
        write(target / "report.json", report),
        write(target / "report.md", rendered, text=True),
        write(target / "sources.jsonl", manifest, text=True),
        write(
            target / "run-log.jsonl",
            '{"event":"report_saved","run_id":"'
            + report.run_id
            + '","at":"'
            + report.run_at.isoformat()
            + '"}',
            text=True,
        ),
    ]
