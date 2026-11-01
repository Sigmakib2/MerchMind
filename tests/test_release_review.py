import json

import pytest

from merchmind.cli import main
from merchmind.intelligence import build_profile, import_records
from merchmind.models import CostInput
from merchmind.research import run
from merchmind.storage import load, load_csv, write


def test_malformed_yaml_returns_structured_error_without_echoing_content(tmp_path, capsys):
    workspace = tmp_path / "store"
    workspace.mkdir()
    (workspace / "merchant.yaml").write_text(
        'finance: ["private-value-do-not-echo"\n', encoding="utf-8"
    )
    assert main(["validate", "--workspace", str(workspace)]) == 2
    output = capsys.readouterr().out
    assert json.loads(output)["status"] == "error"
    assert "Invalid YAML syntax" in output
    assert "private-value-do-not-echo" not in output


def test_uppercase_yaml_extension_is_supported(tmp_path):
    path = tmp_path / "config.YAML"
    path.write_text("currency: BDT\n", encoding="utf-8")
    assert load(path) == {"currency": "BDT"}


def test_known_negative_conservative_margin_rejects_partial_research(fixture):
    raw = fixture["raw"]["cost"]
    raw["scenarios"][0]["tax_inputs_confirmed"] = False
    raw["scenarios"][2]["selling_price_net"] = "300"
    report = run(
        fixture["request"],
        fixture["merchant"],
        fixture["policy"],
        cost=CostInput.model_validate(raw),
        **fixture["bundle"],
    )
    assert report.economics.status == "not_estimated"
    assert report.evaluation.decision == "reject"
    assert "Conservative contribution margin is not positive" in report.evaluation.blockers


@pytest.mark.parametrize(
    "content",
    [
        "name,name\nlamp,other\n",
        "name,category\nlamp,decor,extra\n",
        "name,category\nlamp\n",
        'name,category\n"unterminated,decor\n',
    ],
)
def test_malformed_csv_is_rejected(tmp_path, content):
    path = tmp_path / "bad.csv"
    path.write_text(content, encoding="utf-8")
    with pytest.raises(ValueError, match="CSV"):
        load_csv(path)


def test_csv_import_has_same_size_limit_as_json(fixture, tmp_path):
    path = tmp_path / "oversized.csv"
    path.write_bytes(b"x" * 10_000_001)
    with pytest.raises(ValueError, match="10 MB"):
        import_records("products", path, tmp_path / "store", fixture["merchant"])
    assert not (tmp_path / "store").exists()


@pytest.mark.parametrize("damage", ["missing", "reordered", "modified_sales", "modified_catalog"])
def test_profile_does_not_silently_cite_mismatched_evidence(fixture, tmp_path, damage):
    workspace = tmp_path / "store"
    for kind in ("products", "sales"):
        source = write(tmp_path / f"{kind}.json", fixture["raw"][kind])
        import_records(kind, source, workspace, fixture["merchant"])
    evidence_path = workspace / "data/sales-evidence.jsonl"
    if damage == "missing":
        evidence_path.unlink()
    elif damage == "reordered":
        lines = evidence_path.read_text(encoding="utf-8").splitlines()
        evidence_path.write_text("\n".join(reversed(lines)), encoding="utf-8")
    else:
        data_path = workspace / (
            "data/sales.json" if damage == "modified_sales" else "data/products.json"
        )
        records = load(data_path)
        if damage == "modified_sales":
            records[0]["unit_price"] = "9999"
        else:
            records[0]["category"] = "different-category"
        data_path.write_text(json.dumps(records), encoding="utf-8")
    with pytest.raises(ValueError, match="evidence"):
        build_profile(workspace, fixture["merchant"])
