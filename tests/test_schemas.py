import importlib.util
import json
from pathlib import Path

import pytest
from jsonschema import Draft202012Validator, FormatChecker

from merchmind.models import Report
from merchmind.research import run

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("export_schemas", ROOT / "scripts/export_schemas.py")
EXPORTER = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(EXPORTER)


@pytest.mark.parametrize("name,model", EXPORTER.MODELS.items())
def test_published_schemas_match_models(name, model):
    schema = json.loads((ROOT / f"schemas/{name}.schema.json").read_text(encoding="utf-8"))
    Draft202012Validator.check_schema(schema)
    assert schema == EXPORTER.schema_for(name, model)


def test_report_conforms_to_independent_schema_validator(fixture):
    report = run(
        fixture["request"],
        fixture["merchant"],
        fixture["policy"],
        cost=fixture["cost"],
        **fixture["bundle"],
    )
    schema = EXPORTER.schema_for("report", Report)
    validator = Draft202012Validator(schema, format_checker=FormatChecker())
    serialized = json.loads(report.model_dump_json())
    validator.validate(serialized)
    serialized["economics"]["scenarios"][0]["landed"] = 1.2
    assert list(validator.iter_errors(serialized))
