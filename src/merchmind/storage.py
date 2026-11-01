"""Local artifacts, stable evidence identity and exclusive writes."""

import csv
import hashlib
import json
import os
import re
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel

from merchmind.models import Evidence, source_link


def now() -> datetime:
    return datetime.now(UTC)


def load(path: str | Path) -> Any:
    path = Path(path)
    text = read_input(path)
    try:
        return (
            yaml.safe_load(text) if path.suffix.lower() in {".yaml", ".yml"} else json.loads(text)
        )
    except yaml.YAMLError as exc:
        # Parser errors can contain source lines with credentials or private data.
        raise ValueError(
            "Invalid YAML syntax; check indentation, brackets and quoted values"
        ) from exc
    except RecursionError as exc:
        raise ValueError("Input nesting exceeds the supported depth") from exc


def read_input(path: str | Path) -> str:
    """Bound the actual read, including CSV/JSONL and files changed after stat()."""
    with Path(path).open("rb") as stream:
        content = stream.read(10_000_001)
    if len(content) > 10_000_000:
        raise ValueError("Input exceeds 10 MB limit")
    return content.decode("utf-8-sig")


def load_csv(path: Path) -> tuple[list[str], list[dict]]:
    import io

    try:
        reader = csv.DictReader(io.StringIO(read_input(path), newline=""), strict=True)
        fields = reader.fieldnames or []
        if len(fields) != len(set(fields)):
            raise ValueError("Duplicate CSV column names")
        rows = list(reader)
        if any(None in row or any(value is None for value in row.values()) for row in rows):
            raise ValueError("CSV rows must have the same number of fields as the header")
        return fields, rows
    except csv.Error as exc:
        raise ValueError("Invalid CSV syntax; check quoted cells and column lengths") from exc


def dump(value: Any) -> str:
    if isinstance(value, BaseModel):
        return value.model_dump_json(indent=2)
    return json.dumps(value, indent=2, ensure_ascii=False, default=str, allow_nan=False)


def write(path: str | Path, value: Any, *, text: bool = False) -> Path:
    """Refuse to silently replace prior evidence, inputs or reports."""
    path = Path(path)
    payload = value if text else dump(value)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("x", encoding="utf-8", newline="\n") as stream:
        stream.write(payload)
        stream.write("\n")
    return path


def private_path(workspace: Path, relative: str) -> Path:
    root = workspace.resolve()
    target = (root / relative).resolve()
    if not target.is_relative_to(root) or target == root:
        raise ValueError("Path must stay inside the merchant workspace")
    return target


def append_log(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as stream:
        stream.write(json.dumps(value, default=str, ensure_ascii=False) + "\n")
        stream.flush()
        os.fsync(stream.fileno())


def safe_uri(uri: str | None) -> str | None:
    return source_link(uri)


def redact(text: str) -> str:
    text = re.sub(r"[\w.+-]+@[\w.-]+\.[A-Za-z]{2,}", "[redacted email]", text)
    return re.sub(
        r"(?i)\b(api[_-]?key|token|secret|password|authorization)\s*[:=]\s*[^\s,;]+",
        r"\1=[redacted]",
        text,
    )


def evidence_record(
    record: Any,
    *,
    kind: str,
    reference: str,
    assertion: str,
    uri: str | None = None,
    verified: str = "merchant_provided",
    currency: str | None = None,
    unit: str | None = None,
) -> Evidence:
    digest = record_hash(record)
    identity = hashlib.sha256(f"{kind}:{reference}:{digest}".encode()).hexdigest()[:24]
    return Evidence(
        evidence_id=f"ev-{identity}",
        source_type=kind,
        source_uri=safe_uri(uri),
        source_record_ref=reference,
        retrieved_at=now(),
        assertion=redact(assertion),
        captured_value=None,
        currency=currency,
        unit=unit,
        verification_status=verified,
        freshness_status="unknown",
        hash=digest,
    )


def record_hash(record: Any) -> str:
    canonical = json.dumps(record, sort_keys=True, default=str, ensure_ascii=False)
    return hashlib.sha256(canonical.encode()).hexdigest()


def read_evidence(path: Path) -> list[Evidence]:
    if not path.exists():
        return []
    return [
        Evidence.model_validate_json(line) for line in read_input(path).splitlines() if line.strip()
    ]


def jsonl(records: list[BaseModel]) -> str:
    return "\n".join(record.model_dump_json() for record in records)
