"""Aggregate merchant observations without inventing buyer characteristics."""

import hashlib
from decimal import Decimal
from pathlib import Path

from merchmind.models import CustomerProfile, Finding, Merchant, OrderLine, Product, Return
from merchmind.storage import (
    dump,
    evidence_record,
    jsonl,
    load,
    load_csv,
    now,
    private_path,
    record_hash,
    write,
)

IMPORT_MODELS = {"products": Product, "sales": OrderLine, "returns": Return}


def import_records(kind: str, path: Path, workspace: Path, merchant: Merchant) -> list[Path]:
    model = IMPORT_MODELS[kind]
    if path.suffix.lower() == ".csv":
        fields, raw = load_csv(path)
        unexpected = set(fields) - set(model.model_fields)
        if unexpected:
            raise ValueError(f"Unsupported columns (PII is not imported): {sorted(unexpected)}")
        for row in raw:
            for field in ("quantity", "fulfilled_count", "returned_count"):
                if field in row:
                    row[field] = int(row[field])
            for field in ("mass_g", "associated_cost"):
                if field in row and row[field] == "":
                    row[field] = None
    else:
        raw = load(path)
    if not isinstance(raw, list) or not raw:
        raise ValueError("Import requires a nonempty list of records")
    records = [model.model_validate(row) for row in raw]
    keys = {
        "products": lambda r: r.product_id,
        "sales": lambda r: (r.order_id_hash, r.product_id),
        "returns": lambda r: r.return_id,
    }
    identities = [keys[kind](record) for record in records]
    if len(identities) != len(set(identities)):
        raise ValueError(
            "Duplicate records; aggregate order lines by order and product before import"
        )
    if kind != "products":
        products_path = private_path(workspace, "data/products.json")
        if not products_path.exists():
            raise ValueError("Import the product catalog first")
        product_ids = {p["product_id"] for p in load(products_path)}
        if {r.product_id for r in records} - product_ids:
            raise ValueError("Imported records reference unknown products")
    if kind == "sales" and any(r.currency != merchant.base_currency for r in records):
        raise ValueError("Normalize sales to the merchant base currency before import")
    # No raw CSV or PII is copied. Only schema-approved records are retained.
    evidence = [
        evidence_record(
            r.model_dump(mode="json"),
            kind="merchant_record",
            reference=f"{kind}:{i}",
            assertion=f"Merchant supplied {kind} record {i}",
            currency=merchant.base_currency if kind == "sales" else None,
        )
        for i, r in enumerate(records, start=1)
    ]
    targets = [
        private_path(workspace, f"data/{kind}.json"),
        private_path(workspace, f"data/{kind}-evidence.jsonl"),
    ]
    if any(p.exists() for p in targets):
        raise ValueError("Import already exists. Use a new workspace for a revised data snapshot")
    write(targets[0], [r.model_dump(mode="json") for r in records])
    write(targets[1], jsonl(evidence), text=True)
    return targets


def build_profile(workspace: Path, merchant: Merchant) -> CustomerProfile:
    from merchmind.storage import read_evidence

    products = [
        Product.model_validate(r) for r in load(private_path(workspace, "data/products.json"))
    ]
    orders = [OrderLine.model_validate(r) for r in load(private_path(workspace, "data/sales.json"))]
    sources = read_evidence(private_path(workspace, "data/sales-evidence.jsonl"))
    catalog_sources = read_evidence(private_path(workspace, "data/products-evidence.jsonl"))
    if not orders:
        raise ValueError("Sales history is empty")
    for kind, records, receipts in (
        ("sales", orders, sources),
        ("products", products, catalog_sources),
    ):
        if len(records) != len(receipts):
            raise ValueError(
                f"{kind} evidence is missing or has a different record count; restore the original import snapshot"
            )
        for i, (record, receipt) in enumerate(zip(records, receipts, strict=True), start=1):
            if receipt.source_record_ref != f"{kind}:{i}" or receipt.hash != record_hash(
                record.model_dump(mode="json")
            ):
                raise ValueError(
                    f"{kind} evidence does not match the imported data; restore the original import snapshot"
                )
    if any(o.currency != merchant.base_currency for o in orders):
        raise ValueError("Sales currency no longer matches merchant configuration")
    if {o.product_id for o in orders} - {p.product_id for p in products}:
        raise ValueError("Sales reference products missing from the imported catalog")
    at = now()
    metrics, findings = [], []
    start, end = min(o.date for o in orders), max(o.date for o in orders)
    for product, catalog_evidence in zip(products, catalog_sources, strict=True):
        rows = [(i, o) for i, o in enumerate(orders) if o.product_id == product.product_id]
        fulfilled = sum(o.fulfilled_count for _, o in rows)
        returned = sum(o.returned_count for _, o in rows)
        gross = sum((o.unit_price * o.fulfilled_count for _, o in rows), Decimal("0"))
        ids = [sources[i].evidence_id for i, _ in rows]
        metrics.append(
            {
                "product_id": product.product_id,
                "category": product.category,
                "period_start": start.isoformat(),
                "period_end": end.isoformat(),
                "fulfilled_units": fulfilled,
                "returned_units": returned,
                "gross_fulfilled_value_before_refunds": str(gross),
                "currency": merchant.base_currency,
                "return_rate": str(Decimal(returned) / fulfilled) if fulfilled else None,
                "return_rate_denominator": "fulfilled units in imported order-line window",
                "net_revenue": None,
                "repeat_purchase_rate": None,
                "evidence_ids": [catalog_evidence.evidence_id, *ids],
            }
        )
        if ids:
            findings.append(
                Finding(
                    finding_id=f"cf-{product.product_id}",
                    segment_id=product.category,
                    statement=f"{product.name}: {fulfilled} fulfilled units and {returned} returned units in the imported window. This describes outcomes, not buyer motivations.",
                    kind="observation",
                    confidence="medium" if fulfilled >= 20 else "low",
                    evidence_ids=[catalog_evidence.evidence_id, *ids],
                    last_reviewed_at=at,
                )
            )
    version = hashlib.sha256(dump(metrics).encode()).hexdigest()[:16]
    return CustomerProfile(
        merchant_id=merchant.merchant_id,
        built_at=at,
        profile_version=version,
        metrics=metrics,
        findings=findings,
        evidence_ids=[e.evidence_id for e in [*catalog_sources, *sources]],
        limitations=[
            "No customer identifier is retained; repeat purchase cannot be measured.",
            "Refund amounts are unavailable; gross fulfilled value is not net revenue.",
            "Return reasons and associated costs are separate from order-line return counts and are not added again.",
            "No demographic, sensitive-trait, demand or preference inference is made. Merchant review is required before adopting a strategy.",
        ],
    )
