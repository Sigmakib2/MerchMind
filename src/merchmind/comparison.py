"""Explicit feature matching against hypotheses, never simulated buying votes."""

from decimal import Decimal, localcontext

from merchmind.journey_models import ComparisonInput, ComparisonReport, CriterionMatch, SegmentMatch
from merchmind.models import Merchant, StarterProfile, decimal_string
from merchmind.reports import amount, escape
from merchmind.starter import check_brief
from merchmind.storage import now


def hypothesis_text(profile: StarterProfile, segment_id: str, field: str, index: int) -> str:
    segment = next((s for s in profile.research.segments if s.segment_id == segment_id), None)
    if segment is None:
        raise ValueError("Unknown segment in starter profile")
    values = getattr(segment, field)
    if isinstance(values, str):
        if index != 0:
            raise ValueError("Single hypothesis fields require index 0")
        return values
    if index >= len(values):
        raise ValueError("Hypothesis index is outside the selected field")
    return values[index]


def compare_products(
    data: ComparisonInput, profile: StarterProfile, merchant: Merchant
) -> ComparisonReport:
    check_brief(profile.brief, merchant)
    if (data.profile_id, data.profile_version) != (profile.profile_id, profile.profile_version):
        raise ValueError("Comparison must reference this exact profile and version")
    at = now()
    sources = {e.evidence_id: e for e in data.sources}
    for criterion in data.criteria:
        hypothesis_text(
            profile, criterion.segment_id, criterion.hypothesis_field, criterion.hypothesis_index
        )
    results = []
    with localcontext() as context:
        context.prec = 38
        for product in data.products:
            facts = {f.attribute: f for f in product.facts}
            constraints = []
            excluded = product.category in merchant.excluded_categories
            if excluded:
                constraints.append("Product category is excluded")
            if product.mass_g is None:
                constraints.append("Product mass is unknown")
            elif product.mass_g > merchant.constraints.max_product_mass_g:
                constraints.append("Product mass exceeds merchant limit")
                excluded = True
            if profile.brief.product_constraints:
                constraints.append(
                    "Free-text niche restrictions require a separate merchant review"
                )
            for segment in profile.research.segments:
                checks, known, matched, total = [], Decimal("0"), Decimal("0"), Decimal("0")
                for criterion in (c for c in data.criteria if c.segment_id == segment.segment_id):
                    total += criterion.weight
                    fact = facts.get(criterion.product_attribute)
                    usable = fact is not None and all(
                        sources[key].verification_status in {"verified", "merchant_provided"}
                        and sources[key].freshness_status == "current"
                        and sources[key].retrieved_at <= at
                        for key in fact.evidence_ids
                    )
                    status, reason = (
                        "unknown",
                        "Attribute is missing or its evidence is unverified, stale or future-dated",
                    )
                    if usable:
                        try:
                            if criterion.operator == "equals":
                                match = (
                                    fact.value.casefold().strip()
                                    == criterion.expected_value.casefold().strip()
                                )
                            elif criterion.operator == "contains":
                                match = criterion.expected_value.casefold() in fact.value.casefold()
                            elif criterion.operator == "lte":
                                match = decimal_string(fact.value) <= decimal_string(
                                    criterion.expected_value
                                )
                            else:
                                match = decimal_string(fact.value) >= decimal_string(
                                    criterion.expected_value
                                )
                            known += criterion.weight
                            if match:
                                matched += criterion.weight
                            status = "match" if match else "mismatch"
                            reason = "Explicit product-attribute rule applied to supplied current evidence"
                        except ValueError:
                            reason = "A numeric product attribute could not be interpreted safely"
                    checks.append(
                        CriterionMatch(
                            criterion_id=criterion.criterion_id,
                            description=criterion.description,
                            original_hypothesis=hypothesis_text(
                                profile,
                                criterion.segment_id,
                                criterion.hypothesis_field,
                                criterion.hypothesis_index,
                            ),
                            status=status,
                            expected_value=criterion.expected_value,
                            observed_value=fact.value if fact else None,
                            evidence_ids=fact.evidence_ids if fact else [],
                            reason=reason,
                        )
                    )
                coverage = known / total if total else Decimal("0")
                score = (
                    matched / known * 100 if known and coverage >= data.minimum_coverage else None
                )
                verdict = "excluded" if excluded else "insufficient_evidence"
                if not excluded and score is not None and product.mass_g is not None:
                    verdict = "possible_fit" if score >= 50 else "poor_fit"
                results.append(
                    SegmentMatch(
                        product_id=product.product_id,
                        product_name=product.name,
                        segment_id=segment.segment_id,
                        segment_name=segment.name,
                        coverage=coverage,
                        attribute_match_score=score,
                        verdict=verdict,
                        checks=checks,
                        constraints=constraints,
                    )
                )
    return ComparisonReport(
        compared_at=at,
        profile_id=profile.profile_id,
        profile_version=profile.profile_version,
        results=results,
        input_snapshot=data,
        profile_snapshot=profile,
        sources=data.sources,
        limitations=[
            "Feature matching is conditional on unvalidated customer hypotheses, not willingness to pay or probability of purchase.",
            "Criterion choices and weights are merchant/agent assumptions preserved in the input snapshot.",
            "This score does not replace opportunity scoring or safety/economic review.",
        ],
    )


def comparison_markdown(report: ComparisonReport) -> str:
    lines = [
        "# Product and customer hypothesis comparison",
        "",
        "Feature matching against unvalidated hypotheses; no purchase prediction is made.",
        "",
        "| Product | Customer hypothesis | Attribute match /100 | Coverage | Result |",
        "| --- | --- | ---: | ---: | --- |",
    ]
    for row in report.results:
        lines.append(
            f"| {escape(row.product_name)} | {escape(row.segment_name)} | {amount(row.attribute_match_score)} | {amount(row.coverage * 100)}% | {row.verdict} |"
        )
    for row in report.results:
        lines.extend(["", f"## {escape(row.product_name)} and {escape(row.segment_name)}", ""])
        for check in row.checks:
            lines.append(
                f"- {escape(check.description)}: **{check.status}**; expected {escape(check.expected_value)}, supplied {escape(check.observed_value or 'unknown')}. {escape(check.reason)}. Evidence: {escape(', '.join(check.evidence_ids) or 'none')}."
            )
            lines.append(f"  Hypothesis: {escape(check.original_hypothesis)}")
        lines.extend(f"- {escape(value)}" for value in row.constraints)
    lines.extend(["", "## Limits", "", *(f"- {escape(v)}" for v in report.limitations)])
    return "\n".join(lines)
