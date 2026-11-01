"""Every command emits a structured envelope; domain errors return exit code 2."""

import argparse
import json
import sys
import uuid
from pathlib import Path

from pydantic import ValidationError

from merchmind import __version__
from merchmind.demo import data
from merchmind.demo import merchant as demo_merchant
from merchmind.economics import estimate
from merchmind.intelligence import build_profile, import_records
from merchmind.models import (
    CostInput,
    Feedback,
    Merchant,
    Report,
    ResearchPolicy,
    ResearchRequest,
    ScoringConfig,
)
from merchmind.reports import markdown, save_report
from merchmind.research import load_research_bundle, prepare, run
from merchmind.sourcing import import_quotes
from merchmind.storage import append_log, load, private_path, redact, write


def parser() -> argparse.ArgumentParser:
    root = argparse.ArgumentParser(
        prog="merchmind", description="Evidence-backed merchant product research"
    )
    root.add_argument("--version", action="version", version=__version__)
    commands = root.add_subparsers(dest="command", required=True)
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
                    "Import a product catalog and sales history",
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
    if args.command == "init":
        paths = initialize(args.workspace)
        warnings = ["Synthetic demo defaults. Review merchant.yaml before real research."]
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
            paths = persist_profile(args.workspace, merchant)
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
    except (ValueError, OSError, KeyError, TypeError) as exc:
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
