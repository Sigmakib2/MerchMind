"""Regenerate canonical JSON Schema Draft 2020-12 contracts from the models."""

import json
from pathlib import Path

from merchmind.models import (
    CostInput,
    CustomerProfile,
    Evidence,
    Feedback,
    Merchant,
    Product,
    Report,
    ResearchPolicy,
    ResearchRequest,
    ScoringConfig,
    SupplierQuote,
)

MODELS = {
    "merchant": Merchant,
    "product": Product,
    "evidence": Evidence,
    "supplier-quote": SupplierQuote,
    "research-request": ResearchRequest,
    "report": Report,
    "feedback": Feedback,
    "cost-input": CostInput,
    "customer-profile": CustomerProfile,
    "scoring": ScoringConfig,
    "research-policy": ResearchPolicy,
}


def schema_for(name, model):
    schema = model.model_json_schema(mode="serialization")
    schema["$schema"] = "https://json-schema.org/draft/2020-12/schema"
    schema["$id"] = f"https://merchmind.example/schemas/1.0/{name}.schema.json"
    return schema


def main():
    directory = Path(__file__).resolve().parents[1] / "schemas"
    directory.mkdir(exist_ok=True)
    for name, model in MODELS.items():
        (directory / f"{name}.schema.json").write_text(
            json.dumps(schema_for(name, model), indent=2) + "\n", encoding="utf-8"
        )


if __name__ == "__main__":
    main()
