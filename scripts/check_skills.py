"""Local skill structure check. This does not claim runtime discovery or loading."""

import json
from pathlib import Path

import yaml

EXPECTED = {
    "customer-intelligence",
    "product-research",
    "supplier-research",
    "competitor-research",
    "landed-cost",
    "opportunity-evaluation",
}


def check(root: Path) -> list[str]:
    paths = list(root.glob("*/SKILL.md"))
    names = set()
    for path in paths:
        parts = path.read_text(encoding="utf-8").split("---", 2)
        if len(parts) != 3 or parts[0].strip():
            raise ValueError(f"Invalid skill frontmatter: {path}")
        metadata = yaml.safe_load(parts[1])
        if metadata["name"] != path.parent.name or not metadata.get("description"):
            raise ValueError(f"Invalid skill name/description: {path}")
        if not parts[2].strip():
            raise ValueError(f"Empty skill body: {path}")
        names.add(metadata["name"])
    if names != EXPECTED:
        raise ValueError(f"Skill set differs: {names ^ EXPECTED}")
    return sorted(names)


def main():
    root = Path(__file__).resolve().parents[1] / ".agents/skills"
    print(
        json.dumps(
            {"status": "ok", "local_skill_metadata": check(root), "dsh_runtime_verified": False}
        )
    )


if __name__ == "__main__":
    main()
