from datetime import timedelta

import pytest

from merchmind.journey_models import ValidationEvent
from merchmind.models import NicheBrief, ResearchPolicy
from merchmind.starter import build_starter_profile
from merchmind.storage import now
from merchmind.validation import add_observation, summarize_validation, validation_plan


def profile_for(fixture):
    return build_starter_profile(
        NicheBrief(
            brief_id="feedback-demo",
            merchant_id="cozy-vibe-demo",
            niche="desk accessories",
            description="Explore compact useful accessories for home desk setups.",
            market_country="BD",
        ),
        fixture["merchant"],
        ResearchPolicy(),
    )


def event_for(
    fixture, profile, event_id="observation-1", study_id="study-1", outcome="supports", **updates
):
    source = fixture["bundle"]["sources"][0]
    return ValidationEvent(
        event_id=event_id,
        study_id=study_id,
        profile_id=profile.profile_id,
        profile_version=profile.profile_version,
        segment_id="first-purchase",
        hypothesis_field="use_context",
        method="interview",
        outcome=outcome,
        occurred_at=now() - timedelta(days=1),
        recorded_at=now(),
        reviewed_by_merchant=True,
        sample_size=3,
        notes="Synthetic aggregate interview observation; no individual identities retained.",
        evidence_ids=[source.evidence_id],
        sources=[source],
        **updates,
    )


def test_support_and_contradiction_both_remain_visible(fixture, tmp_path):
    profile = profile_for(fixture)
    policy = ResearchPolicy()
    add_observation(event_for(fixture, profile), profile, fixture["merchant"], tmp_path, policy)
    add_observation(
        event_for(fixture, profile, "observation-2", "study-2", "contradicts"),
        profile,
        fixture["merchant"],
        tmp_path,
        policy,
    )
    summary = summarize_validation(profile, fixture["merchant"], tmp_path, policy)
    first = summary.findings[0]
    assert (
        first.assessment == "mixed" and first.supporting_studies == first.contradicting_studies == 1
    )
    assert first.reported_sample_total == 6
    assert profile.status == "hypotheses_unvalidated"
    assert all(f.assessment == "untested" for f in summary.findings[1:])


def test_same_study_cannot_be_counted_twice(fixture, tmp_path):
    profile = profile_for(fixture)
    policy = ResearchPolicy()
    add_observation(event_for(fixture, profile), profile, fixture["merchant"], tmp_path, policy)
    with pytest.raises(ValueError, match="already has an observation"):
        add_observation(
            event_for(fixture, profile, "duplicate-study"),
            profile,
            fixture["merchant"],
            tmp_path,
            policy,
        )


def test_explicit_correction_preserves_original_and_changes_summary(fixture, tmp_path):
    profile = profile_for(fixture)
    policy = ResearchPolicy()
    original = add_observation(
        event_for(fixture, profile), profile, fixture["merchant"], tmp_path, policy
    )
    contents = original.read_bytes()
    add_observation(
        event_for(
            fixture,
            profile,
            "corrected-1",
            outcome="contradicts",
            supersedes_event_id="observation-1",
        ),
        profile,
        fixture["merchant"],
        tmp_path,
        policy,
    )
    summary = summarize_validation(profile, fixture["merchant"], tmp_path, policy)
    assert summary.findings[0].assessment == "contradicted"
    assert summary.findings[0].supporting_studies == 0
    assert len(summary.records) == 2 and original.read_bytes() == contents


def test_unverified_search_snippet_cannot_become_real_customer_feedback(fixture, tmp_path):
    profile = profile_for(fixture)
    event = event_for(fixture, profile)
    event.sources[0] = event.sources[0].model_copy(deep=True)
    event.sources[0].source_type = "web_search_result"
    with pytest.raises(ValueError, match="first-party merchant records"):
        add_observation(event, profile, fixture["merchant"], tmp_path, ResearchPolicy())


def test_wrong_profile_version_is_rejected(fixture, tmp_path):
    profile = profile_for(fixture)
    event = event_for(fixture, profile)
    event.profile_version = "old"
    with pytest.raises(ValueError, match="exact profile"):
        add_observation(event, profile, fixture["merchant"], tmp_path, ResearchPolicy())


def test_validation_plan_has_questions_and_no_outbound_actions(fixture):
    profile = profile_for(fixture)
    plan = validation_plan(profile, fixture["merchant"])
    assert len(plan["segments"]) == 4
    assert all(s["neutral_interview_prompts"] for s in plan["segments"])


def test_changed_observation_without_updated_hash_is_rejected(fixture, tmp_path):
    import json

    from merchmind.storage import load

    profile = profile_for(fixture)
    path = add_observation(
        event_for(fixture, profile), profile, fixture["merchant"], tmp_path, ResearchPolicy()
    )
    record = load(path)
    record["event"]["outcome"] = "contradicts"
    path.write_text(json.dumps(record), encoding="utf-8")
    with pytest.raises(ValueError, match="content hash"):
        summarize_validation(profile, fixture["merchant"], tmp_path, ResearchPolicy())


def test_concurrent_writes_cannot_count_the_same_study_twice(fixture, tmp_path, monkeypatch):
    from concurrent.futures import ThreadPoolExecutor
    from threading import Event

    import merchmind.validation as ledger

    profile = profile_for(fixture)
    entered, release = Event(), Event()
    original = ledger._add_observation

    def paused(*args, **kwargs):
        entered.set()
        if not release.wait(5):
            raise RuntimeError("Test writer was not released")
        return original(*args, **kwargs)

    monkeypatch.setattr(ledger, "_add_observation", paused)
    with ThreadPoolExecutor(max_workers=1) as workers:
        first = workers.submit(
            add_observation,
            event_for(fixture, profile),
            profile,
            fixture["merchant"],
            tmp_path,
            ResearchPolicy(),
        )
        try:
            assert entered.wait(5)
            with pytest.raises(ValueError, match="ledger is busy"):
                add_observation(
                    event_for(fixture, profile, "second-event"),
                    profile,
                    fixture["merchant"],
                    tmp_path,
                    ResearchPolicy(),
                )
        finally:
            release.set()
        assert first.result().exists()
    summary = summarize_validation(profile, fixture["merchant"], tmp_path, ResearchPolicy())
    assert summary.findings[0].supporting_studies == 1
    assert not (tmp_path / "validation/ledger.lock").exists()


def test_record_limit_is_enforced_before_writing_unreadable_history(fixture, tmp_path, monkeypatch):
    import merchmind.validation as ledger

    monkeypatch.setattr(ledger, "MAX_VALIDATION_RECORDS", 1)
    profile = profile_for(fixture)
    add_observation(
        event_for(fixture, profile), profile, fixture["merchant"], tmp_path, ResearchPolicy()
    )
    with pytest.raises(ValueError, match="record limit reached"):
        add_observation(
            event_for(fixture, profile, "second-event", "second-study"),
            profile,
            fixture["merchant"],
            tmp_path,
            ResearchPolicy(),
        )
    assert (
        len(summarize_validation(profile, fixture["merchant"], tmp_path, ResearchPolicy()).records)
        == 1
    )
    assert not (tmp_path / "validation/ledger.lock").exists()


def test_observation_cannot_save_dangling_supporting_evidence(fixture):
    from pydantic import ValidationError

    profile = profile_for(fixture)
    raw = event_for(fixture, profile).model_dump(mode="json")
    raw["sources"][0]["supporting_evidence_ids"] = ["missing-source"]
    with pytest.raises(ValidationError, match="evidence is duplicated or missing"):
        ValidationEvent.model_validate(raw)
