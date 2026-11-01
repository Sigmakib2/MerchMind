from decimal import Decimal

from merchmind.models import CRITERIA, Economics, Evaluation, Merchant, ScoringConfig, Signal


def evaluate(
    signals: dict[str, Signal],
    economics: Economics,
    merchant: Merchant,
    policy: ScoringConfig,
    *,
    blockers: list[str] | None = None,
    hard_rejections: list[str] | None = None,
) -> Evaluation:
    if set(signals) - set(CRITERIA):
        raise ValueError("Unknown scoring criterion")
    components = {key: signals.get(key) for key in CRITERIA}
    # Economic scoring is always computed; external ratings cannot override arithmetic.
    components["contribution_economics"] = None
    conservative = next((s for s in economics.scenarios if s.name == "conservative"), None)
    hard = list(hard_rejections or [])
    pending = list(blockers or [])
    # A known hard failure remains decisive even if another scenario is incomplete.
    if (
        conservative is not None
        and conservative.contribution_margin is not None
        and merchant.constraints.require_positive_conservative_margin
        and conservative.contribution_margin <= 0
    ):
        hard.append("Conservative contribution margin is not positive")
    if economics.status != "complete" or conservative is None:
        pending.append("Complete verified cost scenarios are required")
    elif conservative.contribution_margin is not None:
        margin = conservative.contribution_margin
        target = merchant.constraints.minimum_contribution_margin
        score = (
            min(Decimal("100"), max(Decimal("0"), margin / target * 100))
            if target
            else (Decimal("100") if margin > 0 else Decimal("0"))
        )
        components["contribution_economics"] = Signal(
            score=score,
            evidence_ids=economics.evidence_ids,
            rationale="Conservative contribution margin divided by merchant target, capped at 100.",
        )
        if margin < target:
            pending.append("Conservative contribution margin is below merchant target")
    coverage = sum(
        (getattr(policy.weights, k) for k, v in components.items() if v is not None), Decimal("0")
    )
    score = None
    if coverage >= policy.minimum_coverage and coverage > 0:
        score = (
            sum(
                (
                    getattr(policy.weights, k) * v.score
                    for k, v in components.items()
                    if v is not None
                ),
                Decimal("0"),
            )
            / coverage
        )
    else:
        pending.append("Insufficient evidence coverage for ranking")
    decision = "reject" if hard else "investigate"
    if not hard and not pending and score is not None and score >= policy.test_threshold:
        decision = "test"
    elif score is not None and score < policy.test_threshold:
        pending.append("Score below sample-test threshold")
    return Evaluation(
        score=score,
        coverage=coverage,
        decision=decision,
        scoring_version=policy.scoring_version,
        components=components,
        blockers=hard + pending,
        policy=policy,
        rationale="Hard constraints take priority; missing signals disclose coverage and are excluded from the weighted denominator. Test means consider a controlled sample, not guaranteed sales.",
    )
