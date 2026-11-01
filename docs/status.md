# Implementation status

The requirements document remains the product specification. This first implementation delivers a runnable foundation and targeted research toolkit; commercial validation and live agent-runtime qualification remain outstanding.

| Area | Status |
| --- | --- |
| Foundation | Python package, uv lockfile, typed contracts, generated schemas, examples, local CLI and CI configured |
| Merchant intelligence | CSV/JSON catalog, sales and returns imports; aggregate evidence-backed observations; versioned profiles |
| Customer hypotheses | Explicit finding contract exists; automated hypothesis generation, counterevidence synthesis and adoption workflow remain future work |
| Research | Targeted plan and evaluation, generic HTTPS receipt adapter, supplier CSV/JSON import, reviewed bundle intake, valid partial reports |
| Economics | Three decimal-safe scenarios, dated FX, actual/volumetric billable mass, freight minima, explicit duties and VAT treatment, contribution margin |
| Scoring | Six configurable criteria, coverage disclosure, computed economic rating, hard gates and explainable decisions |
| Reporting | JSON/Markdown/source manifest/run log, preserved input policies, calculation replay and append-only feedback |
| Agent skills | Six portable project skills and a local metadata validator; live DSH discovery and invocation still need qualification |
| Testing | Offline integration, independent cost fixtures, schema, imports, security and connector failure tests; see CI/local test output for measured results |
| Pilot | Synthetic benchmark only; private historical Cozy Vibe BD data, withheld outcomes and manual claim audits are still needed |
| Post-MVP | Search/discovery, scheduling, specialized marketplace APIs, automatic price extraction, MCP, dashboard, database and richer history comparisons are not implemented |

The MVP in the specification is not declared complete until a tested DSH release is recorded and a real retrospective pilot and live-source audit pass. The 95% source-validity, unsupported-claim and commercial-signal targets are not measured by synthetic tests.

To finish pilot qualification, supply a de-identified historical opportunity cohort with timestamps, merchant-reviewed source evidence available at each decision date, and held-out actual outcomes. Follow `docs/evaluation.md`. The implementation does not access private store connectors or upload business data automatically.
