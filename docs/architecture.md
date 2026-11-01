# Architecture

The domain engine is Python, local-first, and independent of DeepSeek Harness or any model provider. Agent skills coordinate the CLI; they do not implement arithmetic or grant permissions.

```text
Merchant config + catalog + order lines + returns
                      |
             Typed validation
                      |
       Aggregate observations and evidence
                      |
Product request -> research plan -> source/quote/comparable intake
                      |
            Evidence reference checks
                      |
        Decimal economics + weighted scoring
                      |
          JSON + Markdown + source manifest
                      |
           Append-only merchant feedback
```

`models.py` defines versioned input/output contracts. `storage.py` owns exclusive artifact writes, hashes, redaction helpers and workspace path boundaries. `intelligence.py` imports schema-approved records and builds versioned observations. `sourcing.py` implements generic HTTPS retrieval and manual supplier imports. `economics.py` and `scoring.py` are the deterministic engine. `research.py` coordinates evidence, checks decision gates and preserves snapshots. `reports.py` renders the decision. `cli.py` provides structured command envelopes with exit code 0 on success and 2 on validation or operational errors. Parser usage errors also use exit code 2.

Merchant YAML may also be JSON; JSON is a YAML subset. Unknown fields fail explicitly to catch misspelled financial configuration. No code is loaded from merchant inputs or web pages. Evidence timestamps are UTC. Evidence IDs derive from normalized content and record identity. Prior imports and reports are never silently overwritten. Subsequent import snapshots currently require a new workspace; reports and profiles have unique output directories within a workspace.

At evaluation, source references must exist. Scoring evidence must be current and either merchant-provided or verified. A claim's verification and freshness labels are declarations from its input provider; the toolkit cannot independently establish their truth. The public web connector always emits unverified evidence. A merchant-reviewed bundle is therefore a trust boundary, not an automated certification system.

The default six score weights are 30% customer fit, 25% contribution economics, 15% demand evidence, 15% supplier reliability, 10% operational suitability and 5% differentiation. Unknown components are unscored. Coverage is the sum of scored weights. Above the configured threshold, scoring renormalizes by that coverage; below it, the final score is null. Conservative margin is divided by the merchant target and capped to 0–100 for the economics component.

Excluded categories, excess mass and a non-positive conservative margin (when required) reject the product. Incomplete economics, ambiguous variants, inadequate evidence coverage, missing reviewed customer fit, missing confirmed supplier terms, or missing current exact local comparables block a test recommendation. A below-target conservative margin also requires investigation. Passing these gates and the configured score threshold returns test, meaning review a controlled sample.

Reports include merchant, request, economics, scoring and source-policy snapshots for replay. Replay uses the recorded run date, so aging evidence does not rewrite historical decisions. A new research run applies today's evidence and FX age. Replay verifies reproducibility, not a cryptographic guarantee against someone replacing a report and all its inputs.
