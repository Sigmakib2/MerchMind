import csv
import json
from pathlib import Path

import pytest

from merchmind.cli import main
from merchmind.intelligence import build_profile, import_records
from merchmind.models import Report
from merchmind.sourcing import import_quotes
from merchmind.storage import load, write


def command(capsys, *args):
    code = main(list(map(str, args)))
    output = json.loads(capsys.readouterr().out)
    return code, output


def test_offline_demo_and_replay(tmp_path, capsys):
    workspace = tmp_path / "store"
    code, output = command(capsys, "demo", "--workspace", workspace)
    assert code == 0, output
    assert output["result"] == {
        "decision": "test",
        "score": "81",
        "coverage": "1.00",
        "synthetic": True,
    }
    report_path = next(Path(p) for p in output["artifact_paths"] if p.endswith("report.json"))
    report = Report.model_validate(load(report_path))
    assert report.economics.scenarios[-1].contribution == 331
    code, output = command(capsys, "research", "validate", "--report", report_path)
    assert code == 0, output
    rendered = tmp_path / "rendered.md"
    code, output = command(capsys, "report", "render", "--input", report_path, "--output", rendered)
    assert code == 0
    assert "331.00" in rendered.read_text(encoding="utf-8")
    assert "Synthetic" in rendered.read_text(encoding="utf-8")


def test_modified_report_arithmetic_fails_replay(tmp_path, capsys):
    _, output = command(capsys, "demo", "--workspace", tmp_path / "store")
    report_path = next(Path(p) for p in output["artifact_paths"] if p.endswith("report.json"))
    report = load(report_path)
    report["economics"]["scenarios"][0]["landed"] = "1"
    tampered = write(tmp_path / "tampered.json", report)
    code, output = command(capsys, "research", "validate", "--report", tampered)
    assert code == 2
    assert "do not reproduce" in output["errors"][0]


def test_existing_workspace_not_overwritten(tmp_path, capsys):
    workspace = tmp_path / "store"
    assert command(capsys, "init", "--workspace", workspace)[0] == 0
    original = (workspace / "merchant.yaml").read_bytes()
    assert command(capsys, "init", "--workspace", workspace)[0] == 2
    assert (workspace / "merchant.yaml").read_bytes() == original


def test_unknown_config_keys_fail_informatively(tmp_path, capsys):
    workspace = tmp_path / "store"
    command(capsys, "init", "--workspace", workspace)
    config = load(workspace / "merchant.yaml")
    config["unexpected"] = True
    (workspace / "merchant.yaml").write_text(json.dumps(config), encoding="utf-8")
    code, output = command(capsys, "validate", "--workspace", workspace)
    assert code == 2
    assert output["errors"][0]["field"] == "unexpected"


def test_profile_metrics_have_explicit_denominators(fixture, tmp_path):
    merchant = fixture["merchant"]
    for kind in ("products", "sales", "returns"):
        path = write(tmp_path / f"{kind}.json", fixture["raw"][kind])
        import_records(kind, path, tmp_path / "store", merchant)
    profile = build_profile(tmp_path / "store", merchant)
    metric = profile.metrics[0]
    assert metric["fulfilled_units"] == 30
    assert metric["returned_units"] == 1
    assert metric["gross_fulfilled_value_before_refunds"] == "36000"
    assert metric["net_revenue"] is None
    assert metric["repeat_purchase_rate"] is None
    assert metric["return_rate_denominator"]
    assert profile.findings[0].adopted is False


def test_duplicate_orders_rejected_before_writing(fixture, tmp_path):
    products = write(tmp_path / "products.json", fixture["raw"]["products"])
    workspace = tmp_path / "store"
    import_records("products", products, workspace, fixture["merchant"])
    orders = fixture["raw"]["sales"]
    orders.append(orders[0])
    sales = write(tmp_path / "sales.json", orders)
    with pytest.raises(ValueError, match="Duplicate"):
        import_records("sales", sales, workspace, fixture["merchant"])
    assert not (workspace / "data/sales.json").exists()


def test_pii_column_rejected_before_persistence(fixture, tmp_path):
    path = tmp_path / "products.csv"
    path.write_text(
        "product_id,name,category,variant,mass_g,email\np1,Lamp,decor,warm,100,a@example.com\n",
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="PII"):
        import_records("products", path, tmp_path / "store", fixture["merchant"])
    assert not (tmp_path / "store").exists()


def test_supplier_csv_import_preserves_moq_and_price_tiers(fixture, tmp_path):
    quote = fixture["raw"]["bundle"]["quotes"][0]
    path = tmp_path / "quotes.csv"
    with path.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(quote))
        writer.writeheader()
        writer.writerow(
            {k: json.dumps(v) if isinstance(v, (list, dict)) else v for k, v in quote.items()}
        )
    quotes, evidence = import_quotes(path)
    assert quotes[0].moq == 10
    assert quotes[0].price_tiers[1].min_qty == 100
    assert quotes[0].evidence_ids == [evidence[0].evidence_id]
    assert evidence[0].verification_status == "merchant_provided"


def test_incomplete_run_generates_report_via_cli(tmp_path, capsys):
    workspace = tmp_path / "store"
    command(capsys, "init", "--workspace", workspace)
    request = write(
        tmp_path / "request.json",
        {
            "request_id": "req-partial",
            "merchant_id": "cozy-vibe-demo",
            "product_name": "Unknown lamp",
            "market_country": "BD",
        },
    )
    code, output = command(
        capsys, "research", "run", "--request", request, "--workspace", workspace
    )
    assert code == 0, output
    assert output["result"]["decision"] == "investigate"
    assert output["result"]["missing_evidence"]


def test_cli_errors_do_not_echo_secret_input_values(tmp_path, capsys):
    workspace = tmp_path / "store"
    command(capsys, "init", "--workspace", workspace)
    config = load(workspace / "merchant.yaml")
    config["finance"]["max_fx_age_days"] = "secret-value-12345"
    (workspace / "merchant.yaml").write_text(json.dumps(config), encoding="utf-8")
    code, output = command(capsys, "validate", "--workspace", workspace)
    assert code == 2
    assert "secret-value-12345" not in json.dumps(output)
