---
name: landed-cost
description: Calculate reproducible landed costs and contribution across three scenarios using the local decimal engine and explicit tax evidence.
---

Use for sourcing economics. Read `schemas/cost-input.schema.json` and `docs/data-dictionary.md`.

1. Supply exactly optimistic/base/conservative scenarios with quoted decimal strings. Use grams, base-currency per-unit charges and a dated sourced FX conversion from source to base currency.
2. Include actual product mass, shipping packaging mass and optional volumetric mass. Normalize kilograms to grams before input. Allocate fixed batch charges per sellable unit explicitly.
3. Require merchant-confirmed import duties and VAT with evidence IDs. Set merchant VAT treatment explicitly. A freight assumption such as 1 BDT/gram does not include customs. Unknown costs are null, never implicit zero.
4. Include selling price net of collected tax, packaging, fulfillment, payment fee, marketing cost and expected return loss. Do not confuse return rates with monetary loss allowances.
5. Run `merchmind cost estimate --input COST --workspace WORKSPACE --format json`. Use its figures verbatim as calculations; do not replace them with LLM arithmetic. If not_estimated, return the missing inputs and partial breakdown.
6. Preserve the full input snapshot and evidence in the final research report. The conservative margin drives economic scoring and merchant hard gates.

Tax classification/rates are merchant-reviewed inputs, not an automated customs database. Recoverable VAT is excluded from expense but still affects working capital. A scenario is an assumption, not a guaranteed outcome.
