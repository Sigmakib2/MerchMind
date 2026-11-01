---
name: customer-intelligence
description: Import merchant catalog, sales and returns and review aggregate customer evidence without inventing buyer traits.
---

Use when establishing merchant context or evaluating customer fit. Read the merchant's private configuration and approved input paths; never copy private data into this skill.

1. Run `merchmind validate --workspace WORKSPACE`.
2. Import products, then sales and optional returns with `merchmind import KIND --file FILE --workspace WORKSPACE`. Files must follow the schemas in `schemas/`; reject personal contact columns. Order identifiers must already be hashed.
3. Run `merchmind profile build --workspace WORKSPACE`. Inspect both profile artifacts and referenced source records.
4. Distinguish observations, merchant hypotheses and inferences. Current automated profiles contain aggregate observations only. Never infer sensitive traits or pretend to simulate individual buyers. Net revenue and repeat purchase are unknown when required data is absent.
5. Ask the merchant to review any proposed customer-fit rating or strategy adoption. A rating needs a rationale and current evidence IDs in the research bundle. Preserve contradictory evidence rather than quietly dropping it.

Commands return JSON with status, errors, warnings and artifact paths. Stop the dependent step on an error; correct data or report the unresolved issue. A profile is not proof of future demand.
