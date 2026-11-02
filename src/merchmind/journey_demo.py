"""A recorded, entirely synthetic five-stage journey. Never starts a browser or calls an API."""

from datetime import timedelta
from pathlib import Path

from merchmind.agent import complete_agent_task, prepare_agent_task, save_agent_task
from merchmind.agent_models import AgentActivity, AgentCapture, AgentSubmission
from merchmind.comparison import compare_products, comparison_markdown
from merchmind.demo import data
from merchmind.journey_models import (
    ComparisonInput,
    LaunchInput,
    OnboardingAnswers,
    ValidationEvent,
)
from merchmind.journey_storage import save_artifact
from merchmind.launch import estimate_launch, launch_markdown
from merchmind.models import CostInput, Merchant, ResearchPolicy, SupplierQuote
from merchmind.onboarding import onboard
from merchmind.starter import build_starter_profile, seed_segments
from merchmind.storage import evidence_record, now, private_path, write
from merchmind.validation import add_observation, summarize_validation, validation_markdown


def run_journey_demo(workspace: Path) -> tuple[list[Path], dict]:
    answers = OnboardingAnswers(
        merchant_id="cozy-vibe-demo",
        business_name="Example Desk Store (synthetic)",
        market_country="BD",
        base_currency="BDT",
        niche="lightweight desk accessories",
        description="Explore small useful desk accessories. All example facts and research are fictional.",
        max_product_mass_g="400",
        freight_rate_per_gram="1",
        startup_budget_local="62000",
        merchant_vat_treatment="expense",
        sourcing_hosts=["example.com"],
    )
    paths, _ = onboard(answers, workspace)
    from merchmind.storage import load

    merchant = Merchant.model_validate(load(workspace / "merchant.yaml"))
    policy = ResearchPolicy()
    brief = answers.brief()
    task = prepare_agent_task(brief, merchant, policy, research_hosts=["example.com"])
    paths.extend(save_agent_task(task, workspace))
    capture = AgentCapture(
        capture_id="demo-capture",
        source_uri="https://example.com/synthetic-desk-research",
        retrieved_at=now(),
        title="Fictional desk-use study",
        excerpt="Entirely synthetic desk-use research for an offline demonstration, not real customer evidence.",
    )
    segments = seed_segments(brief)
    contexts = [
        "A possible need for a simple first desk setup; synthetic hypothesis.",
        "A possible need to store accessories on a small desk; synthetic hypothesis.",
        "A possible need to carry accessories between desks; synthetic hypothesis.",
        "A possible need to improve an existing desk setup; synthetic hypothesis.",
    ]
    for segment, context in zip(segments, contexts, strict=True):
        segment.use_context = context
        segment.kind = "research_inference"
        segment.evidence_ids = [capture.capture_id]
    submission = AgentSubmission(
        task_id=task.task_id,
        brief_id=brief.brief_id,
        status="complete",
        runtime="offline-fixture",
        tools_used=["synthetic_fixture"],
        captures=[capture],
        activities=[
            AgentActivity(
                action="browse", performed_at=capture.retrieved_at, source_uri=capture.source_uri
            )
        ],
        segments=segments,
        unresolved=["All research and tool activity in this demo are fictional."],
    )
    inputs = private_path(workspace, "demo-inputs")
    paths.append(write(inputs / "agent-submission.json", submission))
    receipt, agent_paths = complete_agent_task(task, submission, workspace, merchant, policy)
    paths.extend(agent_paths)
    if receipt.research is None:
        raise ValueError("Synthetic agent submission failed")
    profile = build_starter_profile(brief, merchant, policy, receipt.research)
    product_source = evidence_record(
        {"synthetic": True, "setup_simple": "true", "foldable": "true", "mass_g": "180"},
        kind="merchant_record",
        reference="demo:stand-facts",
        assertion="Synthetic product attributes for a fictional stand; not a live supplier claim.",
    )
    product_source.freshness_status = "current"
    comparison_input = ComparisonInput(
        profile_id=profile.profile_id,
        profile_version=profile.profile_version,
        products=[
            {
                "product_id": "stand-a",
                "name": "Fictional compact desk stand",
                "variant": "compact",
                "category": "desk-decor",
                "mass_g": "180",
                "facts": [
                    {"attribute": key, "value": value, "evidence_ids": [product_source.evidence_id]}
                    for key, value in (
                        ("setup_simple", "true"),
                        ("foldable", "true"),
                        ("mass_g", "180"),
                    )
                ],
            }
        ],
        criteria=[
            {
                "criterion_id": f"criterion-{s.segment_id}",
                "segment_id": s.segment_id,
                "hypothesis_field": "use_context",
                "description": "Synthetic merchant-selected feature criterion for this use situation.",
                "product_attribute": attribute,
                "operator": operator,
                "expected_value": expected,
            }
            for s, (attribute, operator, expected) in zip(
                profile.research.segments,
                [
                    ("setup_simple", "equals", "true"),
                    ("foldable", "equals", "true"),
                    ("mass_g", "lte", "250"),
                    ("replaceable_parts", "equals", "true"),
                ],
                strict=True,
            )
        ],
        sources=[product_source],
    )
    paths.append(write(inputs / "comparison.json", comparison_input))
    comparison = compare_products(comparison_input, profile, merchant)
    paths.extend(
        save_artifact(comparison, "comparison", comparison_markdown(comparison), workspace, policy)
    )
    for index, outcome in enumerate(("supports", "contradicts"), start=1):
        source = evidence_record(
            {"synthetic_study": index, "outcome": outcome},
            kind="merchant_record",
            reference=f"demo:study-{index}",
            assertion="Synthetic aggregate study outcome, not real customer research.",
        )
        event = ValidationEvent(
            event_id=f"demo-event-{index}",
            study_id=f"demo-study-{index}",
            profile_id=profile.profile_id,
            profile_version=profile.profile_version,
            segment_id=profile.research.segments[0].segment_id,
            hypothesis_field="use_context",
            method="interview" if index == 1 else "sample_test",
            outcome=outcome,
            occurred_at=now() - timedelta(hours=1),
            recorded_at=now(),
            reviewed_by_merchant=True,
            sample_size=3,
            notes="Entirely fictional aggregate observation for the demo.",
            evidence_ids=[source.evidence_id],
            sources=[source],
        )
        paths.extend(
            [
                write(inputs / f"validation-event-{index}.json", event),
                add_observation(event, profile, merchant, workspace, policy),
            ]
        )
    summary = summarize_validation(profile, merchant, workspace, policy)
    paths.extend(
        save_artifact(
            summary, "validation-summary", validation_markdown(summary), workspace, policy
        )
    )
    fixture = data()
    fixture["cost"]["product_variant_key"] = "stand-a:compact"
    fixture["bundle"]["quotes"][0]["product_variant_key"] = "stand-a:compact"
    from merchmind.models import Evidence

    sources = [Evidence.model_validate(e) for e in fixture["bundle"]["sources"]]
    launch_input = LaunchInput(
        currency="BDT",
        cost_input=CostInput.model_validate(fixture["cost"]),
        supplier_quote=SupplierQuote.model_validate(fixture["bundle"]["quotes"][0]),
        order_quantity=100,
        sample_cost_local="500",
        setup_cost_local="1000",
        initial_ad_budget_local="2000",
        upfront_selling_costs_local="0",
        working_capital_reserve_local="3000",
        contingency_ratio="0.10",
        available_budget_local=answers.startup_budget_local,
        cash_evidence_ids=[sources[1].evidence_id],
        sources=sources,
    )
    paths.append(write(inputs / "launch.json", launch_input))
    launch = estimate_launch(launch_input, merchant)
    paths.extend(save_artifact(launch, "launch-budget", launch_markdown(launch), workspace, policy))
    return paths, {
        "mode": "journey",
        "synthetic": True,
        "live_requests": 0,
        "segments": len(profile.research.segments),
        "comparisons": len(comparison.results),
        "validation_assessment": summary.findings[0].assessment,
        "conservative_launch_cash": str(launch.scenarios[-1].required_cash),
        "budget_status": launch.scenarios[-1].budget_status,
    }
