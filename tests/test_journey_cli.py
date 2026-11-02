import json
from decimal import Decimal
from pathlib import Path

from merchmind.cli import main
from merchmind.storage import load


def test_all_five_stages_run_offline_and_create_reviewable_artifacts(tmp_path, capsys):
    workspace = tmp_path / "journey"
    assert main(["demo", "--mode", "journey", "--workspace", str(workspace)]) == 0
    output = json.loads(capsys.readouterr().out)
    assert output["result"]["live_requests"] == 0
    assert output["result"]["segments"] == 4
    assert output["result"]["comparisons"] == 4
    assert output["result"]["validation_assessment"] == "mixed"
    assert output["result"]["budget_status"] == "over_budget"
    assert Decimal(output["result"]["conservative_launch_cash"]) == 63390
    assert all(Path(p).exists() for p in output["artifact_paths"])
    assert not (workspace / "data").exists()
    assert (
        main(
            [
                "compare",
                "--workspace",
                str(workspace),
                "--profile",
                next(p for p in output["artifact_paths"] if p.endswith("starter-profile.json")),
                "--input",
                str(workspace / "demo-inputs/comparison.json"),
            ]
        )
        == 0
    )
    capsys.readouterr()
    assert (
        main(
            [
                "launch",
                "estimate",
                "--workspace",
                str(workspace),
                "--input",
                str(workspace / "demo-inputs/launch.json"),
            ]
        )
        == 0
    )
    assert json.loads(capsys.readouterr().out)["result"]["order_quantity"] == 100
    profile = next(p for p in output["artifact_paths"] if p.endswith("starter-profile.json"))
    assert main(["validation", "summary", "--workspace", str(workspace), "--profile", profile]) == 0
    assert json.loads(capsys.readouterr().out)["result"]["recorded_events"] == 2


def test_journey_demo_refuses_to_overwrite_existing_workspace(tmp_path, capsys):
    workspace = tmp_path / "journey"
    assert main(["demo", "--mode", "journey", "--workspace", str(workspace)]) == 0
    capsys.readouterr()
    config = load(workspace / "merchant.yaml")
    assert main(["demo", "--mode", "journey", "--workspace", str(workspace)]) == 2
    capsys.readouterr()
    assert load(workspace / "merchant.yaml") == config
