"""Append-only first-party observations linked to exact, preserved hypotheses."""

import json
import os
from contextlib import contextmanager
from pathlib import Path

from merchmind.comparison import hypothesis_text
from merchmind.journey_models import (
    ValidationEvent,
    ValidationFinding,
    ValidationRecord,
    ValidationSummary,
)
from merchmind.models import Merchant, ResearchPolicy, StarterProfile
from merchmind.reports import escape
from merchmind.starter import check_brief
from merchmind.storage import load, now, private_path, record_hash, write

MAX_VALIDATION_RECORDS = 1000


@contextmanager
def _ledger_lock(workspace: Path):
    """Serialize duplicate checks, writes and summaries across CLI processes."""
    path = private_path(workspace, "validation/ledger.lock")
    path.parent.mkdir(parents=True, exist_ok=True)
    try:
        descriptor = os.open(path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
    except FileExistsError as exc:
        raise ValueError(
            "Validation ledger is busy. Retry after the other operation finishes. If it crashed, inspect validation/ledger.lock and remove it only after confirming no validation operation is running."
        ) from exc
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as stream:
            json.dump({"pid": os.getpid(), "started_at": now().isoformat()}, stream)
        yield
    finally:
        path.unlink(missing_ok=True)


def _key(event: ValidationEvent) -> tuple:
    return (
        event.profile_id,
        event.profile_version,
        event.segment_id,
        event.hypothesis_field,
        event.hypothesis_index,
        event.study_id,
    )


def read_records(workspace: Path, policy: ResearchPolicy) -> list[ValidationRecord]:
    root = private_path(workspace, "validation/events")
    paths = list(root.glob("*.json")) if root.exists() else []
    if (
        len(paths) > MAX_VALIDATION_RECORDS
        or sum(p.stat().st_size for p in paths) > policy.max_report_bytes
    ):
        raise ValueError(
            "Validation history exceeds the configured read budget; export/archive it before continuing"
        )
    records = []
    for path in sorted(paths):
        safe_path = private_path(workspace, f"validation/events/{path.name}")
        record = ValidationRecord.model_validate(load(safe_path))
        if record.event.event_id != path.stem or record.event_hash != record_hash(
            record.event.model_dump(mode="json")
        ):
            raise ValueError("Validation record identity or content hash does not match")
        records.append(record)
    return records


def _add_observation(
    event: ValidationEvent,
    profile: StarterProfile,
    merchant: Merchant,
    workspace: Path,
    policy: ResearchPolicy,
) -> Path:
    check_brief(profile.brief, merchant)
    if (event.profile_id, event.profile_version) != (profile.profile_id, profile.profile_version):
        raise ValueError("Validation event must reference this exact profile version")
    hypothesis_text(profile, event.segment_id, event.hypothesis_field, event.hypothesis_index)
    at = now()
    if event.recorded_at > at:
        raise ValueError("Future-dated validation records are not accepted")
    sources = {s.evidence_id: s for s in event.sources}
    if any(
        sources[key].verification_status not in {"verified", "merchant_provided"}
        or sources[key].retrieved_at > at
        for key in event.evidence_ids
    ):
        raise ValueError(
            "Validation requires reviewed first-party/verified evidence, not unverified search snippets"
        )
    if any(sources[key].source_type != "merchant_record" for key in event.evidence_ids):
        raise ValueError(
            "Direct customer observations require first-party merchant records, not listings or inferences"
        )
    records = read_records(workspace, policy)
    if len(records) >= MAX_VALIDATION_RECORDS:
        raise ValueError(
            "Validation record limit reached; archive the history before adding another event"
        )
    events = {r.event.event_id: r.event for r in records}
    if event.event_id in events:
        raise ValueError(
            "Validation event already exists; use a new event ID for an explicit correction"
        )
    superseded = {r.event.supersedes_event_id for r in records if r.event.supersedes_event_id}
    active = [r.event for r in records if r.event.event_id not in superseded]
    if event.supersedes_event_id:
        previous = events.get(event.supersedes_event_id)
        if previous is None or previous.event_id in superseded or _key(previous) != _key(event):
            raise ValueError(
                "Correction must replace an active observation of the same study and hypothesis"
            )
    elif any(_key(existing) == _key(event) for existing in active):
        raise ValueError(
            "This study already has an observation for this hypothesis; use supersedes_event_id to correct it"
        )
    record = ValidationRecord(
        event=event, event_hash=record_hash(event.model_dump(mode="json")), saved_at=at
    )
    size = len(record.model_dump_json(indent=2).encode()) + 1
    if (
        size > min(policy.max_report_bytes, 1_000_000)
        or size + sum(len(r.model_dump_json(indent=2).encode()) + 1 for r in records)
        > policy.max_report_bytes
    ):
        raise ValueError("Validation event or total history exceeds storage budget")
    return write(private_path(workspace, f"validation/events/{event.event_id}.json"), record)


def add_observation(
    event: ValidationEvent,
    profile: StarterProfile,
    merchant: Merchant,
    workspace: Path,
    policy: ResearchPolicy,
) -> Path:
    with _ledger_lock(workspace):
        return _add_observation(event, profile, merchant, workspace, policy)


def validation_plan(profile: StarterProfile, merchant: Merchant) -> dict:
    check_brief(profile.brief, merchant)
    return {
        "profile_id": profile.profile_id,
        "profile_version": profile.profile_version,
        "segments": [
            {
                "segment_id": s.segment_id,
                "name": s.name,
                "research_questions": s.validation_questions,
                "neutral_interview_prompts": [
                    "Describe the last time you faced this situation.",
                    "What did you use or buy instead?",
                    "What was difficult about that choice?",
                    "What would make a product unsuitable for you?",
                ],
                "sample_test_measures": [
                    "Actual usage and observed problems",
                    "Real purchase/return outcomes rather than stated intention alone",
                ],
            }
            for s in profile.research.segments
        ],
        "instructions": [
            "Record only consented aggregate observations; do not store names, emails or phone numbers.",
            "Choose the exact hypothesis field/index, method, study ID, outcome and supporting evidence.",
            "Do not reuse the same study as independent corroboration. Mixed findings must remain visible.",
        ],
    }


def _summarize_validation(
    profile: StarterProfile, merchant: Merchant, workspace: Path, policy: ResearchPolicy
) -> ValidationSummary:
    check_brief(profile.brief, merchant)
    records = [
        r
        for r in read_records(workspace, policy)
        if (r.event.profile_id, r.event.profile_version)
        == (profile.profile_id, profile.profile_version)
    ]
    superseded = {r.event.supersedes_event_id for r in records if r.event.supersedes_event_id}
    active = [r.event for r in records if r.event.event_id not in superseded]
    findings = []
    for segment in profile.research.segments:
        for field in (
            "use_context",
            "possible_goals",
            "possible_buying_triggers",
            "possible_objections",
        ):
            values = getattr(segment, field)
            values = [values] if isinstance(values, str) else values
            for index, text in enumerate(values):
                events = [
                    e
                    for e in active
                    if (e.segment_id, e.hypothesis_field, e.hypothesis_index)
                    == (segment.segment_id, field, index)
                ]
                support = sum(e.outcome == "supports" for e in events)
                contradict = sum(e.outcome == "contradicts" for e in events)
                inconclusive = sum(e.outcome == "inconclusive" for e in events)
                assessment = (
                    "mixed"
                    if support and contradict
                    else "some_support"
                    if support
                    else "contradicted"
                    if contradict
                    else "inconclusive"
                    if events
                    else "untested"
                )
                findings.append(
                    ValidationFinding(
                        segment_id=segment.segment_id,
                        hypothesis_field=field,
                        hypothesis_index=index,
                        hypothesis=text,
                        assessment=assessment,
                        supporting_studies=support,
                        contradicting_studies=contradict,
                        inconclusive_studies=inconclusive,
                        reported_sample_total=sum(e.sample_size for e in events),
                        event_ids=[e.event_id for e in events],
                        methods=sorted({e.method for e in events}),
                    )
                )
    return ValidationSummary(
        profile_id=profile.profile_id,
        profile_version=profile.profile_version,
        summarized_at=now(),
        findings=findings,
        records=records,
        limitations=[
            "These are recorded observations, not automatic proof of a segment, psychological model or future demand.",
            "Reported sample totals may overlap across studies and are not unique customer counts.",
            "Corrections supersede observations for the summary while preserving every original record. The starter profile itself is unchanged.",
            "No confidence upgrade or statistical significance claim is inferred from study counts.",
        ],
    )


def summarize_validation(
    profile: StarterProfile, merchant: Merchant, workspace: Path, policy: ResearchPolicy
) -> ValidationSummary:
    with _ledger_lock(workspace):
        return _summarize_validation(profile, merchant, workspace, policy)


def validation_markdown(report: ValidationSummary) -> str:
    lines = [
        "# Customer hypothesis validation",
        "",
        "Support and contradictions from recorded studies. Original hypotheses are preserved.",
        "",
        "| Segment | Hypothesis | Assessment | Support | Contradictions | Inconclusive |",
        "| --- | --- | --- | ---: | ---: | ---: |",
    ]
    for row in report.findings:
        lines.append(
            f"| {row.segment_id} | {escape(row.hypothesis)} | {row.assessment} | {row.supporting_studies} | {row.contradicting_studies} | {row.inconclusive_studies} |"
        )
    lines.extend(["", "## Limits", "", *(f"- {escape(v)}" for v in report.limitations)])
    return "\n".join(lines)
