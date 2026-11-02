"""New-merchant research hypotheses, distinct from observed customer history.

The deterministic toolkit prepares and validates work. A merchant or an external
agent performs authorized web research and supplies the structured synthesis.
"""

from datetime import datetime
from pathlib import Path
from urllib.parse import urlsplit
from uuid import uuid4

from merchmind.models import (
    Evidence,
    Merchant,
    NicheBrief,
    ResearchPolicy,
    SegmentHypothesis,
    StarterProfile,
    StarterResearch,
)
from merchmind.reports import escape
from merchmind.storage import now, private_path, record_hash, write


def check_brief(brief: NicheBrief, merchant: Merchant) -> list[str]:
    if brief.merchant_id != merchant.merchant_id or brief.market_country != merchant.market_country:
        raise ValueError("Niche brief merchant or market does not match workspace")
    hosts = brief.sourcing_hosts or merchant.allowed_marketplaces
    if set(hosts) - set(merchant.allowed_marketplaces):
        raise ValueError("Sourcing hosts must already be approved in merchant.yaml")
    return list(dict.fromkeys(hosts))


def research_plan(brief: NicheBrief, merchant: Merchant, policy: ResearchPolicy) -> dict:
    hosts = check_brief(brief, merchant)
    market = "Bangladesh" if brief.market_country == "BD" else brief.market_country
    return {
        "brief": brief.model_dump(mode="json"),
        "sales_history_required": False,
        "requested_segments": brief.segment_count,
        "research_queries": [
            f"{market} {brief.niche} buying guide beginner complaints",
            f"{market} {brief.niche} customer reviews product selection",
            f"{market} {brief.niche} compact portable alternatives",
            f"{market} {brief.niche} local prices returns common problems",
        ],
        "research_languages": brief.research_languages,
        "questions": [
            "What different use situations or problems appear in the evidence?",
            "What features, price objections and purchase triggers are mentioned?",
            "Which findings apply to this market, and which may not transfer?",
            "What contradicts each proposed segment or is still unknown?",
        ],
        "sourcing_hosts": hosts,
        "constraints": {
            "product_constraints": brief.product_constraints,
            "excluded_categories": merchant.excluded_categories,
            "max_product_mass_g": str(merchant.constraints.max_product_mass_g),
        },
        "limits": {
            "max_sources": policy.max_sources,
            "max_duration_minutes": policy.max_duration_minutes,
        },
        "instructions": [
            "A merchant or external agent must conduct authorized research; this command performs no search.",
            "Use aggregate market evidence and product-use contexts. Do not infer preferences from sensitive traits or location alone.",
            "Retail listings establish advertised availability or price, not actual demand or buying psychology.",
            "For the agent handoff, return AgentSubmission with source captures and three/four distinct hypotheses. Existing manual imports may still use StarterResearch JSON.",
            "All segments remain unvalidated hypotheses. Do not fabricate budgets, audience sizes, sales or supplier terms.",
        ],
    }


def seed_segments(brief: NicheBrief) -> list[SegmentHypothesis]:
    # These are intentionally generic questions, not purported market findings.
    contexts = [
        (
            "first-purchase",
            "People exploring a first purchase",
            "getting started",
            "starter accessories",
            "Uncertainty about which features are necessary",
        ),
        (
            "space-limited",
            "People evaluating space-saving options",
            "using products in limited space",
            "compact accessories",
            "Storage and setup space",
        ),
        (
            "portable",
            "People evaluating portable options",
            "using products in more than one place",
            "portable accessories",
            "Portability versus durability",
        ),
        (
            "upgrade",
            "People considering an upgrade",
            "improving an existing setup",
            "replacement upgrade accessories",
            "Whether an upgrade adds enough value",
        ),
    ]
    return [
        SegmentHypothesis(
            segment_id=key,
            name=name,
            use_context=f"Research whether {context} is a relevant use situation for {brief.niche} in {brief.market_country}.",
            possible_goals=[f"Explore {context}; no customer preference has been established."],
            possible_buying_triggers=[
                "A specific unmet need, to be confirmed through research or interviews."
            ],
            possible_objections=[objection + "; this is an assumption to test."],
            product_search_terms=[f"{brief.niche} {keywords}"],
            validation_questions=[
                f"Does this use situation actually occur among potential buyers of {brief.niche}?",
                "What would disprove this segment, and what would a small product test measure?",
            ],
        )
        for key, name, context, keywords, objection in contexts[: brief.segment_count]
    ]


def build_starter_profile(
    brief: NicheBrief,
    merchant: Merchant,
    policy: ResearchPolicy,
    research: StarterResearch | None = None,
    *,
    at: datetime | None = None,
) -> StarterProfile:
    check_brief(brief, merchant)
    at = Evidence.aware(at or now())
    research = (
        research.model_copy(deep=True)
        if research
        else StarterResearch(
            brief_id=brief.brief_id,
            segments=seed_segments(brief),
        )
    )
    if research.brief_id != brief.brief_id or len(research.segments) != brief.segment_count:
        raise ValueError("Research brief ID or segment count does not match niche brief")
    if len(research.sources) > policy.max_sources:
        raise ValueError("Starter research exceeds source budget")
    sources = {e.evidence_id: e for e in research.sources}
    missing = ["No first-party sales outcomes validate these customer hypotheses."]
    for segment in research.segments:
        supporting = [sources[key] for key in segment.evidence_ids]
        valid = [
            e
            for e in supporting
            if e.verification_status in {"verified", "merchant_provided"}
            and e.freshness_status == "current"
            and e.retrieved_at <= at
        ]
        independent = {
            urlsplit(e.source_uri).hostname if e.source_uri else e.source_record_ref for e in valid
        }
        if (
            segment.kind == "merchant_hypothesis"
            or len(valid) != len(supporting)
            or len(independent) < 2
            or segment.counterevidence_ids
        ):
            segment.confidence = "low"
        if not supporting:
            missing.append(
                f"{segment.segment_id}: supporting customer or market research is missing."
            )
        elif len(valid) != len(supporting):
            missing.append(
                f"{segment.segment_id}: cited evidence is stale, unverified or not dated before this run."
            )
        elif len(independent) < 2:
            missing.append(
                f"{segment.segment_id}: independent support for this hypothesis is limited."
            )
        if segment.counterevidence_ids:
            missing.append(
                f"{segment.segment_id}: review contradictory evidence before choosing a product."
            )
    identity = record_hash(
        {"brief": brief.model_dump(mode="json"), "research": research.model_dump(mode="json")}
    )[:24]
    return StarterProfile(
        profile_id=f"starter-{identity}",
        profile_version=identity,
        merchant_id=merchant.merchant_id,
        built_at=at,
        brief=brief,
        research=research,
        missing_evidence=missing,
        limitations=[
            "This is a set of possible customer groups, not simulated people or a validated psychological model.",
            "Generic seeds are unresearched prompts. An external agent or merchant must perform source research and synthesis.",
            "Research confidence is capped at medium; hypothetical fit is not observed demand or willingness to pay.",
            "Product directions are search ideas, not verified listings, supplier endorsements or recommendations to purchase.",
            "Do not convert these hypotheses automatically into evidence-backed opportunity scores. Review and test them first.",
        ],
    )


def discovery_plan(profile: StarterProfile, merchant: Merchant) -> dict:
    hosts = check_brief(profile.brief, merchant)
    return {
        "profile_id": profile.profile_id,
        "profile_version": profile.profile_version,
        "mode": "guided_read_only",
        "requires_sales_history": False,
        "constraints": {
            "product_constraints": profile.brief.product_constraints,
            "max_product_mass_g": str(merchant.constraints.max_product_mass_g),
            "excluded_categories": merchant.excluded_categories,
        },
        "segments": [
            {
                "segment_id": s.segment_id,
                "confidence": s.confidence,
                "status": s.status,
                "search_terms": s.product_search_terms,
                "sourcing_queries": [
                    {"host": host, "query": f"site:{host} {term}"}
                    for host in hosts
                    for term in s.product_search_terms
                ],
                "validation_questions": s.validation_questions,
            }
            for s in profile.research.segments
        ],
        "next_steps": [
            "Use authorized search tools or manual exports to find candidate listings on approved sources.",
            "Check every candidate against the supplied niche constraints, exact variant and merchant restrictions.",
            "Pass a candidate URL/name to research prepare/run; verify supplier terms, local prices, safety and costs there.",
            "Collect interview or sample-test feedback before treating hypothetical preferences as observed outcomes.",
        ],
        "network_requests_performed": 0,
        "purchasing": False,
    }


def save_starter_profile(
    profile: StarterProfile, merchant: Merchant, workspace: Path, policy: ResearchPolicy
) -> list[Path]:
    plan = discovery_plan(profile, merchant)
    lines = [
        f"# Customer hypotheses for {escape(profile.brief.niche)}",
        "",
        "Status: unvalidated starter hypotheses. No sales history was used.",
        "",
        f"Market: {profile.brief.market_country}",
        "",
    ]
    for s in profile.research.segments:
        lines.extend(
            [
                f"## {escape(s.name)}",
                "",
                escape(s.use_context),
                "",
                f"Basis: {s.kind}. Confidence: {s.confidence}. Status: {s.status}.",
                "",
            ]
        )
        for label, values in [
            ("Possible goals", s.possible_goals),
            ("Possible buying triggers", s.possible_buying_triggers),
            ("Possible objections", s.possible_objections),
            ("Product search ideas", s.product_search_terms),
            ("Questions to test", s.validation_questions),
        ]:
            lines.extend([f"### {label}", "", *(f"- {escape(v)}" for v in values), ""])
        lines.extend(
            [
                "Supporting evidence: " + escape(", ".join(s.evidence_ids) or "None"),
                "Counterevidence: " + escape(", ".join(s.counterevidence_ids) or "None"),
                "",
            ]
        )
    lines.extend(["## Sources", ""])
    for e in profile.research.sources:
        link = f"[source](<{e.source_uri}>)" if e.source_uri else "private merchant record"
        lines.append(
            f"- {e.evidence_id}: {escape(e.assertion)}; {e.verification_status}; {e.freshness_status}; {e.retrieved_at.isoformat()}; {link}."
        )
    lines.extend(
        [
            "",
            "## Missing evidence",
            "",
            *(f"- {escape(v)}" for v in profile.missing_evidence),
            "",
            "## Limits",
            "",
            *(f"- {escape(v)}" for v in profile.limitations),
        ]
    )
    rendered = "\n".join(lines)
    import json

    if (
        len(profile.model_dump_json(indent=2).encode())
        + len(rendered.encode())
        + len(json.dumps(plan, indent=2, ensure_ascii=False).encode())
        + 3
        > policy.max_report_bytes
    ):
        raise ValueError("Starter profile exceeds report storage budget")
    root = private_path(workspace, f"profiles/starter/{profile.profile_version}-{uuid4().hex[:8]}")
    return [
        write(root / "starter-profile.json", profile),
        write(root / "starter-profile.md", rendered, text=True),
        write(root / "product-discovery-plan.json", plan),
    ]
