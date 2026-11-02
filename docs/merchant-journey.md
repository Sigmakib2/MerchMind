# From a niche idea to a product test and launch estimate

The merchant journey has five steps: guided business setup, agent-led research, product comparison, customer validation and total launch cash planning. Purchasing, payments, messages and account changes remain outside the toolkit.

## Try all five stages offline

```sh
uv run merchmind demo --mode journey --workspace workspaces/my-journey-demo
```

Open the returned Markdown files for customer profiles, product comparison, validation summary and launch budget. `demo-inputs/` contains the exact input formats used by the commands below.

This demo creates a fictional desk-accessory business, validates a synthetic agent source capture and research submission, builds four hypotheses, compares a fictional product, records support and contradiction, and estimates a 100-unit launch. No browser, network request or separate model API call is used. Research, interviews, product details, prices and taxes are synthetic. Its conservative required cash is 63,390 BDT against a fictional 62,000 BDT budget; these are arithmetic fixtures, not actual Bangladesh costs.

## 1 Guided setup

```sh
uv run merchmind onboard --workspace workspaces/my-store
```

Answer the questions about your business, niche, market, currency, sourcing sites, restrictions, target margin and optional startup budget. Prompts appear in the terminal; the final result remains structured JSON. Blank optional amounts stay unknown. No fictional sales are created.

For repeatable or agent-driven setup, use an answer file:

```sh
uv run merchmind onboard --workspace workspaces/my-store --answers examples/onboarding-answers.json
```

Choose one approach and a new workspace. Setup refuses to overwrite existing files. Replace the sample details before real research. Outputs include merchant settings, niche brief, scoring/source policies, an onboarding snapshot and readiness checks. Unknown shipping blocks complete unit-cost totals rather than becoming free shipping. VAT treatment remains unknown unless supplied explicitly in the answer file or later merchant configuration.

## 2 Agent-led research

The current agent uses its own authorized browsing/source tools and reasoning. MerchMind calls no separate search/model API and needs no provider account, API key or price configuration.

```sh
uv run merchmind agent prepare --workspace workspaces/my-store --brief workspaces/my-store/niche-brief.json --public-web
```

The agent reads the generated task, captures sources, writes an AgentSubmission, and runs `merchmind agent complete` with the workspace, task and submission paths. For restricted research, use explicit `--research-hosts HOST ...` instead. The `profile starter research` alias also prepares a task.

Complete accepted submissions produce source receipts and low-confidence starter hypotheses. Missing browsing or incomplete access produces explicit unavailable/partial results, without fabricated replacement groups. The Python CLI validates task/source/reference data and computes costs; it does not launch an agent or supply a browser. Runtime permissions, data handling and billing remain that runtime's responsibility.

See the [agent workflow guide](agent-workflow.md) for the full submission contract, source/time budgets, capture hashes, runtime limits and migration from the removed provider adapters.

## 3 Product-to-profile comparison

```sh
uv run merchmind compare --workspace workspaces/my-store --profile PATH_TO_STARTER_PROFILE_JSON --input comparison.json
```

Use `schemas/comparison-input.schema.json` or the journey demo's generated `demo-inputs/comparison.json`. Supply candidate variants, evidenced product attributes, and explicit criteria pointing to an exact profile version and hypothesis field/index.

For example, a merchant may hypothesize that a space-related need calls for `foldable == true`. The rule and its weight remain visible assumptions. Equality, text containment and numeric comparisons are supported. State units consistently in attribute/criterion descriptions; monetary economics belong in the cost engine.

Reports separate matches, mismatches and unknowns and show weighted evidence coverage and each rule's sources. Unverified/missing attributes receive no match points. Merchant mass/category restrictions override good matches. Free-text restrictions still need human review. Attribute-match scores are conditional on hypotheses, not purchase probabilities, willingness to pay or substitutes for supplier/safety/economic checks.

## 4 Customer validation

```sh
uv run merchmind validation plan --workspace workspaces/my-store --profile PATH_TO_STARTER_PROFILE_JSON
uv run merchmind validation add --workspace workspaces/my-store --profile PATH_TO_STARTER_PROFILE_JSON --input observation.json
uv run merchmind validation summary --workspace workspaces/my-store --profile PATH_TO_STARTER_PROFILE_JSON
```

Plans provide research questions, neutral interview prompts and sample-test measures. They do not contact anyone. Observation inputs record an exact hypothesis/version, study ID, method, dates, sample size, merchant review, supporting first-party evidence and a supports/contradicts/inconclusive outcome. Methods include interviews, surveys, sample tests, sales and returns. Use the validation-event schema and generated demo files as guides. Store consented aggregate observations, not customer identities or contact details.

Events are saved exclusively with content hashes. The same study cannot be counted twice for one hypothesis. Correct an observation using a new event ID and `supersedes_event_id`. The original remains unchanged, while summaries count the active replacement. Editing content without its matching hash is detected; this is not a signed tamper-proof archive.

Ledger updates and summaries use an exclusive workspace lock so simultaneous commands cannot bypass duplicate-study checks or read a half-written record. A busy ledger returns a retryable error. After a process crash, inspect `validation/ledger.lock` and remove a stale lock only after confirming no validation operation is running. History is limited to 1,000 records and the configured byte budget; the next event is rejected before exceeding either limit.

Summaries retain support, contradictions, inconclusive findings and untested hypotheses. Counts do not automatically raise confidence or establish statistical validation. Samples may overlap between studies. Original profiles remain unchanged. This ledger is not an accounting system or an automatic importer of study outcomes.

## 5 Total launch cash

```sh
uv run merchmind launch estimate --workspace workspaces/my-store --input launch.json
```

Use `schemas/launch-input.schema.json` or generated `demo-inputs/launch.json`. Inputs include three cost scenarios, a matching supplier quote, order quantity, sources, samples, setup, initial advertising, prepaid selling costs, working-capital reserve, contingency and available budget. Monetary inputs use the merchant base currency and quoted decimals. Explicit null means unknown; known free charges are zero.

MOQ and applicable quantity tiers are enforced. Scenarios below the confirmed tier price are flagged. Unsupported, expired or unconfirmed supplier terms block complete estimates. Missing startup amounts stay unknown. Required cash can be estimated even when available budget is unknown.

Each scenario includes batch import cash, full-order packaging, samples, setup, initial ads, prepaid selling costs, contingency and reserve. All import VAT is cash paid up front, even if later recoverable; no immediate refund is assumed. Initial advertising is counted once, rather than again as per-sale marketing multiplied by inventory. Per-sale marketing still affects contribution separately.

Contingency applies to upfront costs before the reserve. Reserve is held cash, not an expense. Launch setup costs are not silently allocated into unit contribution. All ordered units are assumed sellable; defects/unsellable inventory must be accounted for explicitly in supplied costs/reserve. Estimates show required cash, remaining budget, assumptions and missing inputs. They are not purchase authorization or guarantees of sufficient capital.
