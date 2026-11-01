---
name: opportunity-evaluation
description: Review evidence-backed score components, hard gates and decision coverage, then validate the recorded product recommendation.
---

Use after customer, supplier, local-market and cost evidence has been gathered.

1. Review the configured six weights and coverage threshold. Every supplied rating needs a rationale and current verified or merchant-provided evidence IDs. Do not supply contribution_economics: it is computed by the engine.
2. Leave unknown ratings unscored. Disclose the weighted evidence coverage and its effect on ranking. Do not invent neutral or perfect scores.
3. Run `merchmind research run --request REQUEST --workspace WORKSPACE --cost COST --bundle BUNDLE`. Hard constraints, incomplete costs, variant ambiguity, missing customer review and supplier/local-price gates take priority over a high score.
4. Run `merchmind research validate --report REPORT` and inspect report.md plus the source manifest. Explain test/investigate/reject and the actionable missing-evidence list. Test means consider a controlled sample, not guaranteed sales or authorization to purchase.
5. Record merchant outcomes with `merchmind feedback add --workspace WORKSPACE --input FEEDBACK`. Keep original evidence and prior reports unchanged.

Do not initiate a supplier message, order, payment, upload, listing publication or account modification. Autonomous discovery remains outside this release.
