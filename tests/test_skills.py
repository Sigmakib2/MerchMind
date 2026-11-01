import importlib.util
from pathlib import Path


def test_portable_skill_catalog():
    root = Path(__file__).resolve().parents[1]
    spec = importlib.util.spec_from_file_location("check_skills", root / "scripts/check_skills.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    assert len(module.check(root / ".agents/skills")) == 6
