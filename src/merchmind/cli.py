"""Every command emits a structured envelope; domain errors return exit code 2."""

import argparse
import json
import sys
import uuid
from pathlib import Path

from pydantic import ValidationError

from merchmind import __version__
from merchmind.agent import complete_agent_task, prepare_agent_task, save_agent_task
from merchmind.agent_models import AgentResearchTask, AgentSubmission
from merchmind.comparison import compare_products, comparison_markdown
from merchmind.demo import data
from merchmind.demo import merchant as demo_merchant
from merchmind.economics import estimate
from merchmind.intelligence import build_profile, import_records
from merchmind.journey_demo import run_journey_demo
from merchmind.journey_models import (
    ComparisonInput,
    LaunchInput,
    OnboardingAnswers,
    ValidationEvent,
)
from merchmind.journey_storage import save_artifact
from merchmind.launch import estimate_launch, launch_markdown
from merchmind.models import (
    CostInput,
    Feedback,
    Merchant,
    NicheBrief,
    Report,
    ResearchPolicy,
    ResearchRequest,
    ScoringConfig,
    StarterProfile,
    StarterResearch,
)
from merchmind.onboarding import onboard, prompt_answers
from merchmind.reports import markdown, save_report
from merchmind.research import load_research_bundle, prepare, run
from merchmind.sourcing import import_quotes
from merchmind.starter import (
    build_starter_profile,
    discovery_plan,
    research_plan,
    save_starter_profile,
)
from merchmind.storage import append_log, load, private_path, redact, write
from merchmind.validation import (
    add_observation,
    summarize_validation,
    validation_markdown,
    validation_plan,
)


def parser() -> argparse.ArgumentParser:
    root = argparse.ArgumentParser(
        prog="merchmind", description="Evidence-backed merchant product research"
    )
    root.add_argument("--version", action="version", version=__version__)
    commands = root.add_subparsers(dest="command", required=True)
    agent = commands.add_parser(
        "agent", help="Hand research to the current agent; no search/model API keys required"
    ).add_subparsers(dest="action", required=True)
    prepare_agent = agent.add_parser("prepare")
    prepare_agent.add_argument("--workspace", type=Path, required=True)
    prepare_agent.add_argument("--brief", type=Path, required=True)
    prepare_agent.add_argument(
        "--research-hosts",
        nargs="+",
        help="Explicitly approved research hosts; defaults to merchant allowlist",
    )
    prepare_agent.add_argument(
        "--public-web",
        action="store_true",
        help="Explicitly permit read-only public-web research through runtime tools",
    )
    complete_agent = agent.add_parser("complete")
    complete_agent.add_argument("--workspace", type=Path, required=True)
    complete_agent.add_argument("--task", type=Path, required=True)
    complete_agent.add_argument("--submission", type=Path, required=True)
    launch = (
        commands.add_parser("launch", help="Estimate total startup cash")
        .add_subparsers(dest="action", required=True)
        .add_parser("estimate")
    )
    launch.add_argument("--workspace", type=Path, required=True)
    launch.add_argument("--input", type=Path, required=True)
    validation = commands.add_parser(
        "validation", help="Plan and record real customer observations"
    ).add_subparsers(dest="action", required=True)
    for name in ("plan", "add", "summary"):
        action = validation.add_parser(name)
        action.add_argument("--workspace", type=Path, required=True)
        action.add_argument("--profile", type=Path, required=True)
        if name == "add":
            action.add_argument("--input", type=Path, required=True)
    compare = commands.add_parser(
        "compare", help="Compare product attributes with customer hypotheses"
    )
    compare.add_argument("--workspace", type=Path, required=True)
    compare.add_argument("--profile", type=Path, required=True)
    compare.add_argument("--input", type=Path, required=True)
    onboarding = commands.add_parser(
        "onboard", help="Answer simple questions to configure a new business"
    )
    onboarding.add_argument("--workspace", type=Path, required=True)
    onboarding.add_argument(
        "--answers",
        type=Path,
        help="Optional OnboardingAnswers JSON instead of interactive questions",
    )
    init = commands.add_parser("init", help="Initialize a private demo-configured workspace")
    init.add_argument("--workspace", type=Path, required=True)
    init.add_argument("--template", choices=["demo"], default="demo")
    validate = commands.add_parser("validate")
    validate.add_argument("--workspace", type=Path, required=True)
    imports = commands.add_parser("import")
    imports.add_argument("kind", choices=["products", "sales", "returns", "quotes"])
    imports.add_argument("--file", type=Path, required=True)
    imports.add_argument("--workspace", type=Path, required=True)
    profile = commands.add_parser("profile").add_subparsers(dest="action", required=True)
    profile_build = profile.add_parser("build")
    profile_build.add_argument("--workspace", type=Path, required=True)
    starter = profile.add_parser("starter", help="Start from a niche without sales history")
    starter_actions = starter.add_subparsers(dest="starter_action", required=True)
    for name in ("prepare", "build", "discover", "research"):
        action = starter_actions.add_parser(name)
        action.add_argument("--workspace", type=Path, required=True)
        if name == "discover":
            action.add_argument("--profile", type=Path, required=True)
        else:
            action.add_argument("--brief", type=Path, required=True)
        if name == "build":
            action.add_argument(
                "--research",
                type=Path,
                help="Reviewed StarterResearch JSON; omitted input produces unresearched draft seeds",
            )
        if name == "research":
            action.add_argument("--research-hosts", nargs="+")
            action.add_argument("--public-web", action="store_true")
    cost = (
        commands.add_parser("cost")
        .add_subparsers(dest="action", required=True)
        .add_parser("estimate")
    )
    cost.add_argument("--input", type=Path, required=True)
    cost.add_argument("--workspace", type=Path, required=True)
    cost.add_argument("--format", choices=["json"], default="json")
    research = commands.add_parser("research").add_subparsers(dest="action", required=True)
    for name in ["prepare", "run"]:
        action = research.add_parser(name)
        action.add_argument("--request", type=Path, required=True)
        action.add_argument("--workspace", type=Path, required=True)
        if name == "run":
            action.add_argument("--cost", type=Path)
            action.add_argument("--bundle", type=Path)
            action.add_argument(
                "--online",
                action="store_true",
                help="Explicitly enable allowlisted read-only HTTPS",
            )
    research_validate = research.add_parser("validate")
    research_validate.add_argument("--report", type=Path, required=True)
    render = (
        commands.add_parser("report")
        .add_subparsers(dest="action", required=True)
        .add_parser("render")
    )
    render.add_argument("--input", type=Path, required=True)
    render.add_argument("--output", type=Path, required=True)
    demo = commands.add_parser("demo", help="Complete offline synthetic workflow")
    demo.add_argument("--workspace", type=Path, required=True)
    demo.add_argument("--mode", choices=["sales", "starter", "journey"], default="sales")
    feedback = (
        commands.add_parser("feedback")
        .add_subparsers(dest="action", required=True)
        .add_parser("add")
    )
    feedback.add_argument("--workspace", type=Path, required=True)
    feedback.add_argument("--input", type=Path, required=True)
    return root


def initialize(workspace: Path) -> list[Path]:
    if workspace.exists() and any(workspace.iterdir()):
        raise ValueError("Workspace is not empty; existing merchant files will not be overwritten")
    workspace.mkdir(parents=True, exist_ok=True)
    paths = [
        write(private_path(workspace, "merchant.yaml"), demo_merchant()),
        write(private_path(workspace, "scoring.yaml"), ScoringConfig()),
        write(private_path(workspace, "sources.yaml"), ResearchPolicy()),
        write(private_path(workspace, ".gitignore"), "*", text=True),
    ]
    paths.append(
        write(
            private_path(workspace, "readiness.json"),
            {
                "status": "demo_only",
                "missing": [
                    "Replace synthetic business assumptions",
                    "Build starter hypotheses from a niche brief, or import a catalog and sales history",
                    "Supply current verified FX and tax amounts",
                ],
            },
        )
    )
    return paths


def get_merchant(workspace: Path) -> Merchant:
    return Merchant.model_validate(load(private_path(workspace, "merchant.yaml")))


def get_policy(workspace: Path) -> ScoringConfig:
    return ScoringConfig.model_validate(load(private_path(workspace, "scoring.yaml")))


def get_research_policy(workspace: Path) -> ResearchPolicy:
    return ResearchPolicy.model_validate(load(private_path(workspace, "sources.yaml")))


def persist_profile(workspace: Path, merchant: Merchant) -> list[Path]:
    profile = build_profile(workspace, merchant)
    root = private_path(workspace, f"profiles/{profile.profile_version}-{uuid.uuid4().hex[:8]}")
    text = "# Merchant customer observations\n\n" + "\n\n".join(
        f.statement for f in profile.findings
    )
    text += "\n\n## Limits\n\n" + "\n".join(f"- {limit}" for limit in profile.limitations)
    return [
        write(root / "customer-profile.json", profile),
        write(root / "customer-profile.md", text, text=True),
    ]


def execute(args: argparse.Namespace) -> dict:
    paths: list[Path] = []
    result = None
    warnings = []
    run_id = None
    if args.command == "onboard":
        answers = (
            OnboardingAnswers.model_validate(load(args.answers))
            if args.answers
            else prompt_answers()
        )
        paths, warnings = onboard(answers, args.workspace)
        result = {
            "merchant_id": answers.merchant_id,
            "next_command": "agent prepare",
            "configuration_source": "merchant_answers",
        }
    elif args.command == "init":
        paths = initialize(args.workspace)
        warnings = ["Synthetic demo defaults. Review merchant.yaml before real research."]
    elif args.command == "demo" and args.mode == "journey":
        paths, result = run_journey_demo(args.workspace)
        warnings = [
            "Entire five-stage journey is synthetic. Agent research uses a local submission fixture; no browsing or API requests are performed."
        ]
    elif args.command == "demo" and args.mode == "starter":
        paths = initialize(args.workspace)
        brief = NicheBrief(
            brief_id="home-fitness-demo",
            merchant_id="cozy-vibe-demo",
            niche="lightweight home fitness accessories",
            description="Explore compact accessories for people considering exercise at home or on the go. Exclude heavy machinery and medical claims.",
            market_country="BD",
            audience_context=["People considering home workouts"],
            product_constraints=["No heavy machines", "No medical treatment claims"],
            sourcing_hosts=["example.com"],
            research_languages=["English", "Bangla"],
        )
        paths.append(write(private_path(args.workspace, "demo-inputs/niche-brief.json"), brief))
        merchant = get_merchant(args.workspace)
        policy = get_research_policy(args.workspace)
        profile = build_starter_profile(brief, merchant, policy)
        paths.extend(save_starter_profile(profile, merchant, args.workspace, policy))
        result = {
            "mode": "starter",
            "segments": len(profile.research.segments),
            "status": profile.status,
            "sales_history_used": False,
            "synthetic": True,
        }
        warnings = [
            "Unresearched hypothetical customer groups, not Bangladesh market findings. No web search or product sourcing was performed."
        ]
    elif args.command == "demo":
        paths = initialize(args.workspace)
        fixture = data()
        fixture_root = private_path(args.workspace, "demo-inputs")
        for name in ("products", "sales", "returns", "request", "cost", "bundle"):
            paths.append(write(fixture_root / f"{name}.json", fixture[name]))
        merchant = get_merchant(args.workspace)
        for kind in ("products", "sales", "returns"):
            paths.extend(
                import_records(kind, fixture_root / f"{kind}.json", args.workspace, merchant)
            )
        paths.extend(persist_profile(args.workspace, merchant))
        report = run(
            ResearchRequest.model_validate(fixture["request"]),
            merchant,
            get_policy(args.workspace),
            cost=CostInput.model_validate(fixture["cost"]),
            **load_research_bundle(fixture_root / "bundle.json"),
        )
        paths.extend(save_report(report, private_path(args.workspace, "reports")))
        result = {
            "decision": report.evaluation.decision,
            "score": str(report.evaluation.score),
            "coverage": str(report.evaluation.coverage),
            "synthetic": True,
        }
        run_id = report.run_id
        warnings = ["Entire demo is synthetic; no live market, FX, tax or supplier claims."]
    elif args.command == "research" and args.action == "validate":
        report = Report.model_validate(load(args.report))
        # Replay the decision from recorded inputs to detect edited arithmetic or scores.
        replay = run(
            report.request_snapshot,
            report.merchant_snapshot,
            report.evaluation.policy,
            cost=report.economics.input_snapshot,
            sources=report.sources,
            quotes=report.supplier_options,
            comparables=report.local_comparables,
            signals={
                k: v
                for k, v in report.evaluation.components.items()
                if v and k != "contribution_economics"
            },
            at=report.run_at,
            research_policy=report.research_policy,
        )
        if report.economics.model_dump() != replay.economics.model_dump():
            raise ValueError("Recorded economics do not reproduce at the original run time")
        if report.evaluation.model_dump() != replay.evaluation.model_dump():
            raise ValueError("Recorded evaluation does not reproduce at the original run time")
        result = {"valid": True, "run_id": report.run_id}
        run_id = report.run_id
    elif args.command == "report":
        report = Report.model_validate(load(args.input))
        paths = [write(args.output, markdown(report), text=True)]
        run_id = report.run_id
    else:
        merchant = get_merchant(args.workspace)
        policy = get_policy(args.workspace)
        research_policy = get_research_policy(args.workspace)
        if args.command == "validate":
            result = {
                "merchant": merchant.model_dump(mode="json"),
                "scoring": policy.model_dump(mode="json"),
                "research_policy": research_policy.model_dump(mode="json"),
                "configuration_valid": True,
            }
        elif args.command == "agent":
            if args.action == "prepare":
                task = prepare_agent_task(
                    NicheBrief.model_validate(load(args.brief)),
                    merchant,
                    research_policy,
                    research_hosts=args.research_hosts,
                    public_web=args.public_web,
                )
                paths = save_agent_task(task, args.workspace)
                result = {
                    "status": "awaiting_agent",
                    "task_id": task.task_id,
                    "api_keys_required": False,
                }
                warnings = [
                    "Task created locally. Actual research requires the current agent's authorized browsing tools."
                ]
            else:
                task = AgentResearchTask.model_validate(load(args.task))
                receipt, paths = complete_agent_task(
                    task,
                    AgentSubmission.model_validate(load(args.submission)),
                    args.workspace,
                    merchant,
                    research_policy,
                )
                result = {
                    "status": receipt.status,
                    "source_count": len(receipt.sources),
                    "local_network_requests": 0,
                }
                warnings = receipt.warnings
                run_id = receipt.task_id
        elif args.command == "launch":
            launch_report = estimate_launch(LaunchInput.model_validate(load(args.input)), merchant)
            paths = save_artifact(
                launch_report,
                "launch-budget",
                launch_markdown(launch_report),
                args.workspace,
                research_policy,
            )
            result = {
                "order_quantity": launch_report.order_quantity,
                "scenarios": [
                    {
                        "name": s.name,
                        "required_cash": str(s.required_cash)
                        if s.required_cash is not None
                        else None,
                        "budget_status": s.budget_status,
                    }
                    for s in launch_report.scenarios
                ],
            }
        elif args.command == "validation":
            profile = StarterProfile.model_validate(load(args.profile))
            if args.action == "plan":
                result = validation_plan(profile, merchant)
            elif args.action == "add":
                event = ValidationEvent.model_validate(load(args.input))
                paths = [add_observation(event, profile, merchant, args.workspace, research_policy)]
                result = {"event_id": event.event_id, "original_profile_changed": False}
            else:
                summary = summarize_validation(profile, merchant, args.workspace, research_policy)
                paths = save_artifact(
                    summary,
                    "validation-summary",
                    validation_markdown(summary),
                    args.workspace,
                    research_policy,
                )
                result = {
                    "hypotheses": len(summary.findings),
                    "recorded_events": len(summary.records),
                }
        elif args.command == "compare":
            comparison = compare_products(
                ComparisonInput.model_validate(load(args.input)),
                StarterProfile.model_validate(load(args.profile)),
                merchant,
            )
            paths = save_artifact(
                comparison,
                "comparison",
                comparison_markdown(comparison),
                args.workspace,
                research_policy,
            )
            result = {"comparisons": len(comparison.results), "basis": "unvalidated_hypotheses"}
        elif args.command == "import":
            if args.kind == "quotes":
                quotes, sources = import_quotes(args.file)
                paths = [
                    write(
                        private_path(args.workspace, f"quotes/import-{uuid.uuid4().hex[:12]}.json"),
                        {
                            "quotes": [q.model_dump(mode="json") for q in quotes],
                            "sources": [s.model_dump(mode="json") for s in sources],
                        },
                    )
                ]
            else:
                paths = import_records(args.kind, args.file, args.workspace, merchant)
        elif args.command == "profile":
            if args.action == "build":
                paths = persist_profile(args.workspace, merchant)
            elif args.starter_action == "discover":
                profile = StarterProfile.model_validate(load(args.profile))
                result = discovery_plan(profile, merchant)
            else:
                brief = NicheBrief.model_validate(load(args.brief))
                if args.starter_action == "prepare":
                    result = research_plan(brief, merchant, research_policy)
                elif args.starter_action == "research":
                    task = prepare_agent_task(
                        brief,
                        merchant,
                        research_policy,
                        research_hosts=args.research_hosts,
                        public_web=args.public_web,
                    )
                    paths = save_agent_task(task, args.workspace)
                    result = {
                        "status": "awaiting_agent",
                        "task_id": task.task_id,
                        "next_command": "agent complete",
                        "api_keys_required": False,
                    }
                    warnings = [
                        "Use an agent with browsing/source tools to perform this task. The CLI does not launch an agent or perform web research."
                    ]
                else:
                    research = (
                        StarterResearch.model_validate(load(args.research))
                        if args.research
                        else None
                    )
                    profile = build_starter_profile(brief, merchant, research_policy, research)
                    paths = save_starter_profile(profile, merchant, args.workspace, research_policy)
                    result = {
                        "mode": "starter",
                        "segments": len(profile.research.segments),
                        "status": profile.status,
                        "sales_history_used": False,
                    }
                    warnings = profile.missing_evidence
        elif args.command == "cost":
            cost_input = CostInput.model_validate(load(args.input))
            result = estimate(cost_input, merchant).model_dump(mode="json")
        elif args.command == "research":
            request = ResearchRequest.model_validate(load(args.request))
            if args.action == "prepare":
                result = prepare(request, merchant, research_policy)
            else:
                report = run(
                    request,
                    merchant,
                    policy,
                    cost=CostInput.model_validate(load(args.cost)) if args.cost else None,
                    **load_research_bundle(args.bundle),
                    online=args.online,
                    research_policy=research_policy,
                )
                paths = save_report(report, private_path(args.workspace, "reports"))
                run_id = report.run_id
                result = {
                    "decision": report.evaluation.decision,
                    "missing_evidence": report.missing_evidence,
                }
        elif args.command == "feedback":
            feedback = Feedback.model_validate(load(args.input))
            if not private_path(args.workspace, f"reports/{feedback.run_id}/report.json").exists():
                raise ValueError("Feedback must reference an existing report in this workspace")
            log = private_path(args.workspace, "feedback/events.jsonl")
            append_log(log, feedback.model_dump(mode="json"))
            paths = [log]
    return {
        "status": "ok",
        "errors": [],
        "warnings": warnings,
        "artifact_paths": [str(p.resolve()) for p in paths],
        "run_id": run_id,
        "result": result,
    }


def main(argv: list[str] | None = None) -> int:
    args = parser().parse_args(argv)
    try:
        result = execute(args)
    except ValidationError as exc:
        result = {
            "status": "error",
            "errors": [
                {"field": ".".join(map(str, item["loc"])), "message": item["msg"]}
                for item in exc.errors(include_input=False)
            ],
            "warnings": [],
            "artifact_paths": [],
            "run_id": None,
        }
    except (ValueError, OSError, KeyError, TypeError, EOFError) as exc:
        result = {
            "status": "error",
            "errors": [redact(str(exc))],
            "warnings": [],
            "artifact_paths": [],
            "run_id": None,
        }
    print(json.dumps(result, ensure_ascii=False, default=str))
    return 0 if result["status"] == "ok" else 2


if __name__ == "__main__":
    sys.exit(main())
