# Start from a niche without customer history

Starter mode helps a new merchant explore a niche before they have customers or sales. It stores three or four possible customer groups, their different use situations, buying questions, objections and product-search ideas. These are **unvalidated hypotheses**, not simulated people or a proven model of customer psychology.

## Try the offline example

```sh
uv run merchmind demo --mode starter --workspace workspaces/fitness-starter
```

Open the returned `starter-profile.md` path. The demo explores lightweight home fitness accessories in Bangladesh using four generic draft contexts: a first purchase, limited space, portability and an upgrade. It uses no sales history and performs no web search. It deliberately does not claim that those groups exist, how large they are, what they will pay, or what they will buy. The generic seeds are prompts to replace or refine through research.

The output directory contains:

- `starter-profile.json`: the niche brief, segment hypotheses, source references, confidence and missing evidence.
- `starter-profile.md`: the readable profile report.
- `product-discovery-plan.json`: per-segment search terms, approved sourcing-site queries, merchant limits and validation questions.

Existing `demo` and `profile build` commands continue to use sales-history mode. Starter mode is a separate path; no catalog or order files are required.

## Describe your niche

Start with `merchmind init`, review your merchant settings, and copy `examples/niche-brief.json` into your private workspace. Change the brief's merchant ID and market to match `merchant.yaml`.

Describe the niche in everyday language: for example, small home-workout accessories, excluding heavy machines. Include intended use situations, product limits, research languages and the sourcing hosts you approve. Set `segment_count` to 3 or 4. Sourcing hosts must already appear in the merchant's exact-host allowlist; naming a site does not establish permission to automate it.

Prepare a research plan:

```sh
uv run merchmind profile starter prepare --workspace workspaces/my-store --brief workspaces/my-store/niche-brief.json
```

The response supplies research queries and questions about local use contexts, complaints, alternatives and counterevidence. It does not run a search. A merchant/external agent can collect evidence, or use the agent-led browsing workflow in the [merchant journey guide](merchant-journey.md). The domain engine remains provider-independent. There is no psychological model or Alibaba connector.

You can also create low-confidence draft seeds while research is unavailable:

```sh
uv run merchmind profile starter build --workspace workspaces/my-store --brief workspaces/my-store/niche-brief.json
```

This produces generic questions based on the supplied niche. Treat the output as a starting worksheet, not completed customer research.

## Add researched hypotheses

An external agent or merchant can supply a `StarterResearch` JSON file containing `brief_id`, `segments` and `sources`. Its complete contract is in `schemas/starter-research.schema.json`. The `research` object in a generated starter profile is also a usable shape template; make edits in a new input file and preserve the original report.

Each segment records:

- A distinct name and use context.
- Possible goals, purchase triggers and objections.
- Product-search terms and questions that could disprove the hypothesis.
- `kind`: `merchant_hypothesis` or `research_inference`.
- Supporting and contradicting evidence IDs, plus low or medium confidence.

Research inferences must cite existing evidence. Sources use the existing evidence contract, including URLs, timestamps, source-record references, content hashes, verification status and freshness. Source labels are provider declarations, not an automatic certification that the claims are true. Review whether each source actually supports the proposed group. Product listings establish availability or advertised price, not demand or customer psychology.

Build the researched profile:

```sh
uv run merchmind profile starter build --workspace workspaces/my-store --brief workspaces/my-store/niche-brief.json --research workspaces/my-store/niche-research.json
```

The tool checks identities, source references, count limits and duplicate contexts. Confidence is capped at medium. Unresearched assumptions, unverified/stale support, a single source domain or contradictory evidence keep confidence low. Two independently identified current sources are a necessary condition for retaining a supplied medium rating, not proof of demand. The tool never upgrades a low rating itself. Every group stays unvalidated until real customer testing provides a basis for a later workflow.

## Use the profiles to explore products

The saved discovery plan provides sourcing queries for each group. You can recreate that plan using:

```sh
uv run merchmind profile starter discover --workspace workspaces/my-store --profile PATH_TO_STARTER_PROFILE_JSON
```

Use the plan with authorized search tools or manual source exports. Compare potential products against the niche restrictions, maximum mass and excluded categories. Free-text constraints guide research and still need human review; they are not automatically understood by the cost engine. Enter a concrete candidate URL or name into the existing targeted-research workflow to check its exact variant, supplier terms, local prices, safety and economics.

The comparison command now matches evidenced product attributes against explicit profile criteria, and a validation ledger records later observations. These do not automatically turn hypotheses into observed opportunity scores. Supplier listings are not automatically browsed and shortlisted. Candidate evaluation still needs reviewed evidence; scheduled autonomous discovery remains outside this feature.

## Learn from real outcomes

Validate the hypotheses through interviews, product samples and small tests. Record what supported or contradicted each idea. Once orders exist, use the sales-history workflow for observed outcomes and preserve the earlier starter profile as a dated hypothesis record. Automatic reconciliation between starter groups and later sales is not implemented.

Do not infer someone's income, health condition, personality or preferences from location, gender or other sensitive traits. Use explicitly supplied needs, product requirements and aggregate evidence. Keep individual names, contact details and unnecessary personal information out of research files.
