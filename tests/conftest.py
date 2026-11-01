from pathlib import Path

import pytest

from merchmind.demo import data
from merchmind.models import CostInput, Merchant, ResearchRequest, ScoringConfig
from merchmind.research import load_research_bundle
from merchmind.storage import write


@pytest.fixture
def fixture(tmp_path: Path) -> dict:
    raw = data()
    bundle_path = write(tmp_path / "bundle.json", raw["bundle"])
    return {
        "merchant": Merchant.model_validate(raw["merchant"]),
        "request": ResearchRequest.model_validate(raw["request"]),
        "cost": CostInput.model_validate(raw["cost"]),
        "policy": ScoringConfig.model_validate(raw["scoring"]),
        "bundle": load_research_bundle(bundle_path),
        "raw": raw,
    }
