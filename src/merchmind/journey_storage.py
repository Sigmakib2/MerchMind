"""Exclusive versioned artifacts for the merchant journey."""

from pathlib import Path
from uuid import uuid4

from pydantic import BaseModel

from merchmind.models import ResearchPolicy
from merchmind.storage import private_path, write


def save_artifact(
    report: BaseModel, name: str, markdown: str, workspace: Path, policy: ResearchPolicy
) -> list[Path]:
    if (
        len(report.model_dump_json(indent=2).encode()) + len(markdown.encode()) + 2
        > policy.max_report_bytes
    ):
        raise ValueError("Artifact exceeds configured report storage budget")
    root = private_path(workspace, f"journey/{name}/{uuid4().hex[:16]}")
    return [write(root / f"{name}.json", report), write(root / f"{name}.md", markdown, text=True)]
