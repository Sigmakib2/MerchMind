"""Regenerate canonical JSON Schema Draft 2020-12 contracts from the models."""

import json
from pathlib import Path

from merchmind.agent_models import AgentResearchReceipt, AgentResearchTask, AgentSubmission
from merchmind.journey_models import (
    ComparisonInput,
    ComparisonReport,
    LaunchInput,
    LaunchReport,
    OnboardingAnswers,
    ValidationEvent,
    ValidationRecord,
    ValidationSummary,
)
from merchmind.models import (
    CostInput,
    CustomerProfile,
    Evidence,
    Feedback,
    Merchant,
    NicheBrief,
    Product,
    Report,
    ResearchPolicy,
    ResearchRequest,
    ScoringConfig,
    StarterProfile,
    StarterResearch,
    SupplierQuote,
)

MODELS = {
    "agent-task": AgentResearchTask,
    "agent-submission": AgentSubmission,
    "agent-receipt": AgentResearchReceipt,
    "validation-event": ValidationEvent,
    "validation-record": ValidationRecord,
    "validation-summary": ValidationSummary,
    "launch-input": LaunchInput,
    "launch-report": LaunchReport,
    "onboarding-answers": OnboardingAnswers,
    "comparison-input": ComparisonInput,
    "comparison-report": ComparisonReport,
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
    "niche-brief": NicheBrief,
    "starter-research": StarterResearch,
    "starter-profile": StarterProfile,
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
