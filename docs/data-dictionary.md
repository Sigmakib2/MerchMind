# Data dictionary

Canonical JSON Schemas live in `schemas/`, are generated from `src/merchmind/models.py`, and declare JSON Schema Draft 2020-12. Pydantic enforces cross-field rules, units, ISO code membership, evidence references and time ordering in addition to the structural schemas. All top-level versioned entities accept schema version `1.0` only. Breaking migrations must be explicit.

| Entity | Key fields | Meaning |
| --- | --- | --- |
| Merchant | merchant_id, market_country, base_currency, freight, finance, constraints, permissions | Editable business context; source hostnames match exactly |
| Product | product_id, name, category, variant, mass_g | Canonical catalog identity; mass is grams |
| Order line | order_id_hash, product_id, date, quantity, unit_price, currency, fulfilled_count, returned_count | One aggregated order/product row; returned <= fulfilled <= ordered |
| Return | return_id, product_id, quantity, reason_code, date, associated_cost | Separate reason/cost record; cost is in merchant base currency |
| Evidence | evidence_id, source_type, source_record_ref, assertion, hash, retrieved_at, verification_status, freshness_status | Claim provenance; inference records must cite support and be labeled inferred |
| Supplier quote | supplier_id, product_variant_key, price_tiers, moq, quoted_at, valid_until, quote_type, verification_checks | Advertised and merchant-confirmed terms remain distinct |
| Comparable | product_variant_key, product_match_type, price, currency, market, captured_at, evidence_id, price_type | Local advertised price or separately evidenced transaction value |
| Cost input | merchant_id, product_variant_key, origin_country, destination_country, fx, evidence_ids, scenarios | Exactly optimistic, base and conservative scenarios |
| Signal | score, rationale, evidence_ids | Merchant-reviewed 0–100 rating; computed economics cannot be supplied |
| Report | product_identity, economics, evaluation, missing_evidence, sources, snapshots | Immutable decision record with replay inputs |
| Feedback | run_id, status, recorded_at, notes | Append-only merchant outcome event |
| Niche brief | brief_id, merchant_id, niche, description, market_country, product_constraints, sourcing_hosts, segment_count | New-business input; requests three or four possible customer groups |
| Starter research | brief_id, segments, sources | Hypotheses with goals, objections, product-search terms, confidence, support and counterevidence |
| Starter profile | profile_id, profile_version, brief, research, missing_evidence | Separate unvalidated profile artifact; no sales imports required |
| Onboarding answers | merchant_id, niche, country/currency, constraints, optional shipping/budget | Guided intake; unknown shipping is null |
| Agent task | task_id, approved brief, merchant/policy snapshots, source scope, expiry, integrity hash | Provider-free handoff to the current agent runtime |
| Agent submission/receipt | captures, runtime/tool activity, hypotheses, unresolved questions, task snapshot, source hashes | Agent-reported provenance; captures remain unverified and incomplete work stays explicit |
| Comparison input/report | exact profile version, product facts, explicit criteria, rule results and coverage | Hypothetical attribute fit, separate from opportunity scoring |
| Validation event/record/summary | study ID, exact hypothesis, method, outcome, dates, source records, correction links | Append-only first-party support and contradiction; no automatic statistical validation |
| Launch input/report | unit scenarios, quote, order size, startup cash items, sources, scenario totals | Upfront cash includes all import VAT and a separately declared reserve |

Money, weights and ratios use quoted decimal strings. Runtime validation also limits numeric strings to 1,024 characters, coefficients to 1,000 digits, and the absolute exponent and adjusted exponent to 1,000; pathological values fail before arithmetic. Display precision expands for large supported amounts. No NaN, infinity or binary floating-point input is accepted for commercial values. All scenario expenses except fixed sourcing charges must be explicitly supplied, including zero or null. Unknown totals are null with `not_estimated`. Full-precision calculations use a 38-digit decimal context; only Markdown display is rounded to two places using half-up rounding. Currency-specific settlement rounding is not implemented and display rounding must not be used as a payment instruction.

Currency and country lists are bundled validation lists; they are not a live registry feed. All supported rates and units are explicit. Cost scenarios accept canonical `mass_g`/`packaging_mass_g` or an explicit `mass`/`packaging_mass` object such as `{"value": "0.18", "unit": "kg"}`. The engine normalizes to grams and preserves the supplied unit object in the input snapshot. Conflicting representations fail validation. Financial records never infer missing taxes from a freight quote. `customs_included: true` is rejected because the current engine expects customs separately.

Research requests include a merchant `safety_review` of pending, approved or blocked and supporting `safety_evidence_ids`. Pending or unsupported review blocks a test decision; a blocked review rejects the product. This records a merchant decision, not an independent regulatory certification.

Supplier CSV imports support the same fields as JSON. `price_tiers`, `verification_flags`, `verification_checks` and optional `evidence_ids` are JSON-encoded CSV cells. The importer creates a new merchant-provided evidence record; supplied evidence IDs are replaced. Quote tiers must be sorted, unique, use one currency and begin at MOQ. A completed checklist declares `supplier_identity`, `product_authenticity`, `trade_terms` and `sample_policy` true. Any verification flag blocks using the quote to clear the supplier gate.

Dates are ISO 8601; timestamps require timezone information. Source links accept HTTPS and omit query strings and fragments when normalized. They are references only: importing a link does not fetch it or add its host to the network allowlist. Source snapshots should contain no credentials or unnecessary personal data.
