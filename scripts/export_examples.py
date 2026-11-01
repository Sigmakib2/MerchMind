"""Refresh synthetic example snapshots. Runtime demo dates are generated at execution."""

import csv
import json
from pathlib import Path

from merchmind.demo import data
from merchmind.models import CostInput, Merchant, ResearchRequest, ScoringConfig
from merchmind.research import load_research_bundle, run


def main():
    root = Path(__file__).resolve().parents[1]
    examples = root / "examples"
    examples.mkdir(exist_ok=True)
    fixture = data()
    for name, records in fixture.items():
        (examples / f"demo-{name}.json").write_text(
            json.dumps(records, indent=2) + "\n", encoding="utf-8"
        )
    for name in ("products", "sales", "returns"):
        records = fixture[name]
        with (examples / f"demo-{name}.csv").open("w", encoding="utf-8", newline="") as stream:
            writer = csv.DictWriter(stream, fieldnames=list(records[0]))
            writer.writeheader()
            writer.writerows(records)
    config = root / "config"
    config.mkdir(exist_ok=True)
    for name, key in (("business", "merchant"), ("scoring", "scoring")):
        (config / f"{name}.example.yaml").write_text(
            json.dumps(fixture[key], indent=2) + "\n", encoding="utf-8"
        )
    report = run(
        ResearchRequest.model_validate(fixture["request"]),
        Merchant.model_validate(fixture["merchant"]),
        ScoringConfig(),
        cost=CostInput.model_validate(fixture["cost"]),
        **load_research_bundle(examples / "demo-bundle.json"),
    )
    (examples / "expected-report.json").write_text(
        report.model_dump_json(indent=2) + "\n", encoding="utf-8"
    )


if __name__ == "__main__":
    main()
