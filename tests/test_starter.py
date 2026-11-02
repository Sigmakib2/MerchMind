import json
from datetime import timedelta
from pathlib import Path

import pytest
from jsonschema import Draft202012Validator
from pydantic import ValidationError

from merchmind.cli import main
from merchmind.models import NicheBrief, ResearchPolicy, StarterProfile, StarterResearch
from merchmind.starter import build_starter_profile, discovery_plan, research_plan, seed_segments
from merchmind.storage import load, now, write


@pytest.fixture
def brief(fixture):
    return NicheBrief(
        brief_id="fitness-test",
        merchant_id=fixture["merchant"].merchant_id,
        niche="lightweight home fitness accessories",
        description="Explore small home workout accessories without heavy machinery.",
        market_country="BD",
        sourcing_hosts=["example.com"],
        product_constraints=["Exclude heavy machines"],
    )


def test_new_merchant_can_build_four_drafts_without_history(brief, fixture):
    profile = build_starter_profile(brief, fixture["merchant"], ResearchPolicy())
    assert profile.sales_history_used is False
    assert profile.status == "hypotheses_unvalidated"
    assert len(profile.research.segments) == 4
    assert all(
        s.confidence == "low" and s.status == "unvalidated" for s in profile.research.segments
    )
    assert all(not s.evidence_ids for s in profile.research.segments)
    assert profile.missing_evidence


def test_three_segments_are_supported(brief, fixture):
    brief.segment_count = 3
    profile = build_starter_profile(brief, fixture["merchant"], ResearchPolicy())
    assert len(profile.research.segments) == 3


@pytest.mark.parametrize("count", [0, 1, 2, 5, 20])
def test_arbitrary_segment_counts_are_rejected(brief, count):
    raw = brief.model_dump(mode="json")
    raw["segment_count"] = count
    with pytest.raises(ValidationError):
        NicheBrief.model_validate(raw)


def test_market_and_merchant_must_match(brief, fixture):
    brief.market_country = "US"
    with pytest.raises(ValueError, match="does not match"):
        research_plan(brief, fixture["merchant"], ResearchPolicy())


def test_sourcing_plan_cannot_add_unapproved_hosts(brief, fixture):
    brief.sourcing_hosts = ["alibaba.com"]
    with pytest.raises(ValueError, match="already be approved"):
        research_plan(brief, fixture["merchant"], ResearchPolicy())


def test_product_search_plan_keeps_constraints_and_does_not_fetch(brief, fixture):
    profile = build_starter_profile(brief, fixture["merchant"], ResearchPolicy())
    plan = discovery_plan(profile, fixture["merchant"])
    assert plan["network_requests_performed"] == 0
    assert plan["purchasing"] is False
    assert plan["constraints"]["max_product_mass_g"] == "400"
    assert plan["constraints"]["product_constraints"] == ["Exclude heavy machines"]
    assert all(
        q["host"] == "example.com" and q["query"].startswith("site:example.com ")
        for s in plan["segments"]
        for q in s["sourcing_queries"]
    )


def test_research_plan_explains_external_research_and_local_context(brief, fixture):
    plan = research_plan(brief, fixture["merchant"], ResearchPolicy())
    assert "Bangladesh" in plan["research_queries"][0]
    assert "performs no search" in plan["instructions"][0]
    assert plan["sales_history_required"] is False


def research_input(brief, fixture):
    sources = [e.model_copy(deep=True) for e in fixture["bundle"]["sources"][:2]]
    sources[0].source_uri = "https://first.example.org/research"
    sources[1].source_uri = "https://second.example.org/research"
    segments = seed_segments(brief)
    for segment in segments:
        segment.kind = "research_inference"
        segment.confidence = "medium"
        segment.evidence_ids = [e.evidence_id for e in sources]
    return StarterResearch(brief_id=brief.brief_id, sources=sources, segments=segments)


def test_research_keeps_provenance_and_never_becomes_observed_customer_truth(brief, fixture):
    profile = build_starter_profile(
        brief, fixture["merchant"], ResearchPolicy(), research_input(brief, fixture)
    )
    assert all(
        s.kind == "research_inference" and s.confidence == "medium" and s.status == "unvalidated"
        for s in profile.research.segments
    )
    assert len(profile.research.sources) == 2
    assert "No first-party sales" in profile.missing_evidence[0]
    assert StarterProfile.model_validate_json(profile.model_dump_json()) == profile


@pytest.mark.parametrize(
    "problem", ["same_domain", "stale", "unverified", "future", "contradicted"]
)
def test_weak_or_contradicted_support_cannot_receive_medium_confidence(brief, fixture, problem):
    research = research_input(brief, fixture)
    if problem == "same_domain":
        research.sources[1].source_uri = "https://first.example.org/copied"
    elif problem == "stale":
        research.sources[0].freshness_status = "stale"
    elif problem == "unverified":
        research.sources[0].verification_status = "unverified"
    elif problem == "future":
        research.sources[0].retrieved_at = now() + timedelta(days=1)
    else:
        extra = fixture["bundle"]["sources"][2].model_copy(deep=True)
        research.sources.append(extra)
        for segment in research.segments:
            segment.counterevidence_ids = [extra.evidence_id]
    profile = build_starter_profile(brief, fixture["merchant"], ResearchPolicy(), research)
    assert all(s.confidence == "low" for s in profile.research.segments)
    assert research.segments[0].confidence == "medium"  # Build does not mutate input.


def test_research_cannot_cite_missing_evidence(brief):
    segments = seed_segments(brief)
    segments[0].evidence_ids = ["ev-missing"]
    with pytest.raises(ValidationError, match="Unknown starter evidence"):
        StarterResearch(brief_id=brief.brief_id, segments=segments)


def test_duplicate_personas_with_different_ids_are_rejected(brief):
    segments = seed_segments(brief)
    segments[1].use_context = segments[0].use_context
    with pytest.raises(ValidationError, match="distinct use contexts"):
        StarterResearch(brief_id=brief.brief_id, segments=segments)


def test_high_confidence_and_validated_customer_claims_are_rejected(brief):
    raw = seed_segments(brief)[0].model_dump(mode="json")
    from merchmind.models import SegmentHypothesis

    for field, value in (("confidence", "high"), ("status", "validated"), ("kind", "observation")):
        with pytest.raises(ValidationError):
            SegmentHypothesis.model_validate({**raw, field: value})


def test_starter_cli_end_to_end_without_sales_files(tmp_path, capsys):
    workspace = tmp_path / "new-store"
    assert main(["demo", "--mode", "starter", "--workspace", str(workspace)]) == 0
    output = json.loads(capsys.readouterr().out)
    assert output["result"]["segments"] == 4
    assert output["result"]["sales_history_used"] is False
    assert not (workspace / "data").exists()
    profile_path = next(
        Path(p) for p in output["artifact_paths"] if p.endswith("starter-profile.json")
    )
    assert (
        main(
            [
                "profile",
                "starter",
                "discover",
                "--workspace",
                str(workspace),
                "--profile",
                str(profile_path),
            ]
        )
        == 0
    )
    plan = json.loads(capsys.readouterr().out)
    assert len(plan["result"]["segments"]) == 4
    assert plan["result"]["network_requests_performed"] == 0
    profile = load(profile_path)
    assert all(s["status"] == "unvalidated" for s in profile["research"]["segments"])


def test_profile_matches_published_json_schema(brief, fixture):
    profile = build_starter_profile(brief, fixture["merchant"], ResearchPolicy())
    root = Path(__file__).resolve().parents[1]
    schema = load(root / "schemas/starter-profile.schema.json")
    Draft202012Validator(schema).validate(json.loads(profile.model_dump_json()))


def test_prepare_and_build_cli_accept_researched_input_without_sales(
    brief, fixture, tmp_path, capsys
):
    workspace = tmp_path / "store"
    assert main(["init", "--workspace", str(workspace)]) == 0
    capsys.readouterr()
    brief_path = write(tmp_path / "brief.json", brief)
    research_path = write(tmp_path / "research.json", research_input(brief, fixture))
    assert (
        main(
            [
                "profile",
                "starter",
                "prepare",
                "--workspace",
                str(workspace),
                "--brief",
                str(brief_path),
            ]
        )
        == 0
    )
    assert json.loads(capsys.readouterr().out)["result"]["requested_segments"] == 4
    assert (
        main(
            [
                "profile",
                "starter",
                "build",
                "--workspace",
                str(workspace),
                "--brief",
                str(brief_path),
                "--research",
                str(research_path),
            ]
        )
        == 0
    )
    output = json.loads(capsys.readouterr().out)
    assert output["result"]["sales_history_used"] is False
    path = next(Path(p) for p in output["artifact_paths"] if p.endswith("starter-profile.json"))
    assert len(load(path)["research"]["sources"]) == 2
    assert not (workspace / "data").exists()
