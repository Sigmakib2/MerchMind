"""Synthetic fixtures only. Numbers below are not market, FX or tax advice."""

import hashlib
from datetime import timedelta

from merchmind.models import CostInput, Merchant, ResearchRequest, ScoringConfig
from merchmind.storage import evidence_record, now


def merchant() -> Merchant:
    return Merchant.model_validate(
        {
            "merchant_id": "cozy-vibe-demo",
            "name": "Cozy Vibe Demo (synthetic)",
            "market_country": "BD",
            "base_currency": "BDT",
            "source_countries": ["CN"],
            "allowed_marketplaces": ["example.com"],
            "preferred_categories": ["ambient-lighting", "desk-decor"],
            "excluded_categories": ["regulated-products"],
            "freight": {"rate": "1.00", "currency": "BDT"},
            "finance": {"merchant_vat_treatment": "expense"},
        }
    )


def data() -> dict:
    at = now()
    products = [
        {
            "product_id": "lamp-a",
            "name": "Demo desk lamp",
            "category": "ambient-lighting",
            "variant": "warm-usb",
            "mass_g": "180",
        },
        {
            "product_id": "lamp-b",
            "name": "Demo rechargeable lamp",
            "category": "ambient-lighting",
            "variant": "rgb-battery",
            "mass_g": "300",
        },
    ]
    orders = [
        {
            "order_id_hash": hashlib.sha256(f"synthetic-order-{i}".encode()).hexdigest(),
            "product_id": "lamp-a" if i < 4 else "lamp-b",
            "date": (at - timedelta(days=10 - i)).date().isoformat(),
            "quantity": 10,
            "unit_price": "1200",
            "currency": "BDT",
            "order_status": "fulfilled",
            "fulfilled_count": 10,
            "returned_count": 1 if i == 2 else 0,
        }
        for i in range(1, 5)
    ]
    returns = [
        {
            "return_id": "return-demo-1",
            "product_id": "lamp-a",
            "quantity": 1,
            "reason_code": "damaged",
            "date": at.date().isoformat(),
            "associated_cost": "100",
        }
    ]
    evidence = []
    for name, assertion in {
        "fx": "Synthetic FX assumption: 1 CNY = 17 BDT, for demonstration only.",
        "cost": "Synthetic supplier, freight, fulfillment and advertising assumptions; no live quote.",
        "tax": "Synthetic merchant-confirmed per-unit taxes for arithmetic demonstration; not official rates.",
        "fit": "Synthetic merchant assessment informed by demo lamp sales; not a real customer finding.",
        "market": "Synthetic local advertised comparable, not observed transactions or demand.",
        "supplier": "Synthetic supplier terms with a fictional completed merchant checklist.",
    }.items():
        record = evidence_record(
            {"demo": name, "synthetic": True},
            kind="merchant_record",
            reference=f"demo:{name}",
            assertion=assertion,
        )
        record.freshness_status = "current"
        evidence.append(record)
    ids = dict(
        zip(
            ("fx", "cost", "tax", "fit", "market", "supplier"),
            (e.evidence_id for e in evidence),
            strict=True,
        )
    )
    scenarios = []
    for name, price, selling, marketing in [
        ("optimistic", "10", "1250", "80"),
        ("base", "11", "1200", "100"),
        ("conservative", "12", "1100", "150"),
    ]:
        scenarios.append(
            {
                "name": name,
                "unit_price_source": price,
                "mass_g": "180",
                "packaging_mass_g": "20",
                "import_duties": "40",
                "import_vat": "20",
                "tax_inputs_confirmed": True,
                "tax_evidence_ids": [ids["tax"]],
                "brokerage": "10",
                "local_inbound": "15",
                "other_import_costs": "5",
                "selling_price_net": selling,
                "packaging": "20",
                "fulfillment": "60",
                "payment_fee": "15",
                "marketing_cost": marketing,
                "expected_return_loss": "30",
            }
        )
    cost = CostInput.model_validate(
        {
            "merchant_id": "cozy-vibe-demo",
            "product_variant_key": "lamp-a:warm-usb",
            "origin_country": "CN",
            "destination_country": "BD",
            "fx": {
                "source_currency": "CNY",
                "target_currency": "BDT",
                "rate": "17",
                "as_of": at.isoformat(),
                "evidence_id": ids["fx"],
            },
            "evidence_ids": [ids["cost"]],
            "scenarios": scenarios,
        }
    )
    request = ResearchRequest.model_validate(
        {
            "request_id": "req-demo-001",
            "safety_review": "approved",
            "safety_evidence_ids": [ids["supplier"]],
            "merchant_id": "cozy-vibe-demo",
            "product_url": "https://example.com/product/demo",
            "product_name": "Synthetic warm USB desk lamp",
            "product_variant_key": "lamp-a:warm-usb",
            "category": "ambient-lighting",
            "market_country": "BD",
        }
    )
    quote = {
        "supplier_id": "synthetic-supplier",
        "source": "Synthetic fixture",
        "listing_url": "https://example.com/product/demo",
        "product_variant_key": "lamp-a:warm-usb",
        "price_tiers": [
            {"min_qty": 10, "unit_price": "12", "currency": "CNY"},
            {"min_qty": 100, "unit_price": "10", "currency": "CNY"},
        ],
        "moq": 10,
        "mass_g": "180",
        "packaging_mass_g": "20",
        "incoterm": "EXW",
        "lead_time_days": 7,
        "quote_type": "confirmed",
        "quoted_at": at.isoformat(),
        "valid_until": (at + timedelta(days=14)).isoformat(),
        "evidence_ids": [ids["supplier"]],
        "verification_flags": [],
        "verification_checks": {
            "supplier_identity": True,
            "product_authenticity": True,
            "trade_terms": True,
            "sample_policy": True,
        },
    }
    comparable = {
        "retailer": "Synthetic local shop",
        "product_match_type": "exact",
        "product_variant_key": "lamp-a:warm-usb",
        "price": "1200",
        "currency": "BDT",
        "market": "BD",
        "captured_at": at.isoformat(),
        "source_url": "https://example.com/local/demo",
        "evidence_id": ids["market"],
    }
    signals = {
        "customer_fit": {
            "score": "80",
            "evidence_ids": [ids["fit"]],
            "rationale": "Synthetic merchant-reviewed fit for an existing category.",
        },
        "demand_evidence": {
            "score": "60",
            "evidence_ids": [ids["fit"]],
            "rationale": "Synthetic historical category outcome; no sales forecast.",
        },
        "supplier_reliability": {
            "score": "75",
            "evidence_ids": [ids["supplier"]],
            "rationale": "Synthetic completed supplier checklist.",
        },
        "operational_suitability": {
            "score": "90",
            "evidence_ids": [ids["cost"]],
            "rationale": "Synthetic mass within merchant constraint.",
        },
        "differentiation": {
            "score": "55",
            "evidence_ids": [ids["market"]],
            "rationale": "Synthetic merchant assessment; modest differentiation.",
        },
    }
    return {
        "merchant": merchant().model_dump(mode="json"),
        "scoring": ScoringConfig().model_dump(mode="json"),
        "products": products,
        "sales": orders,
        "returns": returns,
        "request": request.model_dump(mode="json"),
        "cost": cost.model_dump(mode="json"),
        "bundle": {
            "sources": [e.model_dump(mode="json") for e in evidence],
            "quotes": [quote],
            "comparables": [comparable],
            "signals": signals,
        },
    }
