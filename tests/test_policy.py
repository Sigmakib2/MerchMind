import pytest

from merchmind.models import ResearchPolicy
from merchmind.reports import save_report
from merchmind.research import prepare, run


def test_safety_review_pending_requires_investigation(fixture):
    fixture["request"].safety_review = "pending"
    report = run(
        fixture["request"],
        fixture["merchant"],
        fixture["policy"],
        cost=fixture["cost"],
        **fixture["bundle"],
    )
    assert report.evaluation.decision == "investigate"
    assert any("safety and legal review" in x for x in report.missing_evidence)


def test_safety_review_can_hard_reject_even_with_good_economics(fixture):
    fixture["request"].safety_review = "blocked"
    report = run(
        fixture["request"],
        fixture["merchant"],
        fixture["policy"],
        cost=fixture["cost"],
        **fixture["bundle"],
    )
    assert report.evaluation.decision == "reject"
    assert report.economics.scenarios[-1].contribution > 0


def test_request_cannot_exceed_workspace_source_limits(fixture):
    workspace_policy = ResearchPolicy(max_sources=2, max_duration_minutes=1)
    plan = prepare(fixture["request"], fixture["merchant"], workspace_policy)
    assert plan["limits"]["sources"] == 2
    assert plan["limits"]["duration_minutes"] == 1
    with pytest.raises(ValueError, match="budget exceeded"):
        run(
            fixture["request"],
            fixture["merchant"],
            fixture["policy"],
            research_policy=workspace_policy,
            **fixture["bundle"],
        )


def test_report_size_limit_applies_before_creating_output(fixture, tmp_path):
    report = run(
        fixture["request"],
        fixture["merchant"],
        fixture["policy"],
        cost=fixture["cost"],
        **fixture["bundle"],
    )
    report.research_policy.max_report_bytes = 1024
    with pytest.raises(ValueError, match="storage budget"):
        save_report(report, tmp_path / "reports")
    assert not (tmp_path / "reports").exists()
