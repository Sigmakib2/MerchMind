"""Typed research coordination, usable offline or through an external agent skill."""

import time
import uuid
from datetime import datetime
from pathlib import Path

from merchmind import __version__
from merchmind.economics import estimate
from merchmind.models import (
    Comparable,
    CostInput,
    Economics,
    Evidence,
    Merchant,
    Report,
    ResearchPolicy,
    ResearchRequest,
    ScoringConfig,
    Signal,
    SupplierQuote,
)
from merchmind.scoring import evaluate
from merchmind.sourcing import FetchSession, validate_url
from merchmind.storage import load, now, safe_uri


def prepare(
    request: ResearchRequest,
    merchant: Merchant,
    research_policy: ResearchPolicy | None = None,
) -> dict:
    research_policy = research_policy or ResearchPolicy()
    if (
        request.merchant_id != merchant.merchant_id
        or request.market_country != merchant.market_country
    ):
        raise ValueError("Request merchant or market does not match workspace")
    if request.product_url:
        validate_url(request.product_url, merchant.allowed_marketplaces)
    return {
        "request": request.model_dump(mode="json"),
        "steps": [
            "Review merchant profile and evidence",
            "Resolve exact variant",
            "Import supplier quotes and local comparables",
            "Confirm dated FX, weight and per-unit tax inputs",
            "Calculate three cost scenarios",
            "Review evidence-backed signals",
            "Validate and render report",
        ],
        "allowed_hosts": merchant.allowed_marketplaces,
        "permissions": merchant.permissions.model_dump(),
        "limits": {
            "sources": min(request.max_sources, research_policy.max_sources),
            "duration_minutes": min(
                request.max_duration_minutes, research_policy.max_duration_minutes
            ),
            "requests_per_domain": research_policy.max_requests_per_domain,
        },
        "note": "Online fetch requires --online. Imported documents and pages are untrusted data.",
    }


def run(
    request: ResearchRequest,
    merchant: Merchant,
    policy: ScoringConfig,
    *,
    cost: CostInput | None = None,
    sources: list[Evidence] | None = None,
    quotes: list[SupplierQuote] | None = None,
    comparables: list[Comparable] | None = None,
    signals: dict[str, Signal] | None = None,
    online: bool = False,
    at: datetime | None = None,
    research_policy: ResearchPolicy | None = None,
) -> Report:
    at = Evidence.aware(at or now())
    research_policy = research_policy or ResearchPolicy()
    prepare(request, merchant, research_policy)
    sources, quotes, comparables, signals = (
        list(sources or []),
        list(quotes or []),
        list(comparables or []),
        dict(signals or {}),
    )
    if "contribution_economics" in signals:
        raise ValueError(
            "Contribution economics is computed by the engine, not supplied as a signal"
        )
    if len(sources) + (1 if online and request.product_url else 0) > min(
        request.max_sources, research_policy.max_sources
    ):
        raise ValueError("Research source budget exceeded")
    for evidence in sources:
        evidence.source_uri = safe_uri(evidence.source_uri)
    ids = {e.evidence_id for e in sources}
    if len(ids) != len(sources):
        raise ValueError("Duplicate evidence IDs")
    # Stale and unverified sources may be displayed, but cannot justify a score.
    usable = {
        e.evidence_id
        for e in sources
        if e.verification_status in {"verified", "merchant_provided"}
        and e.freshness_status == "current"
        and e.retrieved_at <= at
    }
    for signal in signals.values():
        if not set(signal.evidence_ids) <= usable:
            raise ValueError(
                "Scoring signals require current verified or merchant-provided evidence"
            )
    source_statuses = []
    if request.product_url:
        if online:
            session = FetchSession(
                merchant.allowed_marketplaces,
                max_requests_per_host=research_policy.max_requests_per_domain,
                max_bytes=research_policy.max_response_bytes,
                deadline=time.monotonic()
                + min(request.max_duration_minutes, research_policy.max_duration_minutes) * 60,
            )
            status, evidence = session.fetch(request.product_url)
            source_statuses.append(status)
            if evidence:
                sources.append(evidence)
        else:
            source_statuses.append(
                {
                    "source": request.product_url,
                    "status": "not_fetched",
                    "reason": "Offline run; use imported evidence or explicitly enable online access",
                }
            )
    economics = (
        estimate(cost, merchant, at=at)
        if cost
        else Economics(
            status="not_estimated",
            scenarios=[],
            evidence_ids=[],
            assumptions=["No cost inputs supplied"],
        )
    )
    blockers, hard = [], []
    if request.safety_review == "blocked":
        hard.append("Merchant safety or legal review blocks this product")
    elif (
        request.safety_review != "approved"
        or not request.safety_evidence_ids
        or not set(request.safety_evidence_ids) <= usable
    ):
        blockers.append("Merchant safety and legal review with current evidence is required")
    if not request.product_variant_key:
        blockers.append("Exact product variant requires merchant review")
    if not request.category:
        blockers.append("Product category requires merchant review")
    elif request.category in merchant.excluded_categories:
        hard.append("Product category is excluded by merchant policy")
    if cost:
        if cost.product_variant_key != request.product_variant_key:
            raise ValueError("Cost inputs do not match requested product variant")
        for scenario in cost.scenarios:
            if scenario.mass_g is None:
                blockers.append("Product mass is unknown")
            elif scenario.mass_g > merchant.constraints.max_product_mass_g:
                hard.append("Product mass exceeds merchant limit")
        cost_ids = set(economics.evidence_ids)
        if not cost_ids <= ids:
            raise ValueError(f"Cost inputs reference missing evidence: {sorted(cost_ids - ids)}")
        if not cost_ids <= usable:
            blockers.append("Cost assumptions include stale or unverified evidence")
    matching = [q for q in quotes if q.product_variant_key == request.product_variant_key]
    checklist = {"supplier_identity", "product_authenticity", "trade_terms", "sample_policy"}
    confirmed = [
        q
        for q in matching
        if q.quote_type == "confirmed"
        and q.quoted_at <= at
        and q.valid_until is not None
        and q.valid_until >= at
        and set(q.evidence_ids) <= usable
        and not q.verification_flags
        and all(q.verification_checks.get(key) is True for key in checklist)
    ]
    if not confirmed:
        blockers.append(
            "Current confirmed supplier quote with completed verification checklist is required"
        )
    exact_comparables = [
        c
        for c in comparables
        if c.product_match_type == "exact"
        and c.product_variant_key == request.product_variant_key
        and c.market == merchant.market_country
        and c.currency == merchant.base_currency
        and set([c.evidence_id]) <= usable
        and 0 <= (at - c.captured_at).total_seconds() <= 30 * 86400
    ]
    if not exact_comparables:
        blockers.append("Current exact-variant local price evidence is required")
    if "customer_fit" not in signals:
        blockers.append("Customer fit needs an evidence-backed merchant review")
    evaluation = evaluate(
        signals,
        economics,
        merchant,
        policy,
        blockers=sorted(set(blockers)),
        hard_rejections=sorted(set(hard)),
    )
    missing = sorted(set(evaluation.blockers + [m for s in economics.scenarios for m in s.missing]))
    return Report(
        run_id=f"run-{uuid.uuid4().hex[:16]}",
        merchant_id=merchant.merchant_id,
        request_id=request.request_id,
        run_at=at,
        engine_version=__version__,
        product_identity={
            "name": request.product_name or "Unresolved product",
            "variant": request.product_variant_key,
            "match_status": "specified_by_merchant"
            if request.product_variant_key
            else "needs_review",
        },
        customer_fit=signals.get("customer_fit"),
        supplier_options=quotes,
        local_comparables=comparables,
        economics=economics,
        evaluation=evaluation,
        missing_evidence=missing,
        sources=sources,
        source_statuses=source_statuses,
        merchant_snapshot=merchant,
        request_snapshot=request,
        research_policy=research_policy,
    )


def load_research_bundle(path: Path | None) -> dict:
    if path is None:
        return {"sources": [], "quotes": [], "comparables": [], "signals": {}}
    data = load(path)
    if not isinstance(data, dict) or set(data) - {"sources", "quotes", "comparables", "signals"}:
        raise ValueError("Bundle supports only sources, quotes, comparables and signals")
    return {
        "sources": [Evidence.model_validate(x) for x in data.get("sources", [])],
        "quotes": [SupplierQuote.model_validate(x) for x in data.get("quotes", [])],
        "comparables": [Comparable.model_validate(x) for x in data.get("comparables", [])],
        "signals": {k: Signal.model_validate(v) for k, v in data.get("signals", {}).items()},
    }
