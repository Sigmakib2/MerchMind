# MerchMind

MerchMind helps small online sellers turn a niche idea into customer hypotheses, product comparisons and a launch-cost estimate. Merchants with existing sales can also use their history to build customer profiles and evaluate new products.

It is built for **physical-product businesses**. You supply the niche, market, sourcing sites and restrictions. Reports show the evidence, assumptions, missing information and calculations behind each result.

**Status: developer alpha.** The local workflows and offline demos work. Live provider accounts, DeepSeek Harness integration, authorized sources and real-store outcomes still need qualification. See [implementation status](docs/status.md).

## Quick start

Install [Git](https://git-scm.com/downloads), [Python 3.12 or later](https://www.python.org/downloads/) and [uv](https://docs.astral.sh/uv/getting-started/installation/).

For a fresh checkout:

```sh
git clone https://github.com/Sigmakib2/MerchMind.git
cd MerchMind
uv sync --locked
uv run merchmind demo --mode journey --workspace workspaces/first-journey
```

If you already have the repository, run the last two commands from its root folder.

Setup downloads the locked dependencies into an isolated Python environment. After setup, this demo needs **no API keys, paid service, AI account or network access**. It uses fictional data and recorded provider responses.

The demo exercises all five stages. It deliberately includes an unknown product attribute, conflicting customer observations and a conservative launch scenario that exceeds the fictional budget.

### Open your results

The command prints `artifact_paths`: the exact locations of the generated files. Open the Markdown files for readable reports.

| File | What it explains |
| --- | --- |
| `starter-profile.md` | Four possible customer groups, their needs, uncertainties and sources |
| `comparison.md` | Product attributes that match, conflict with or lack evidence for each hypothesis |
| `validation-summary.md` | Customer observations supporting or contradicting the hypotheses |
| `launch-budget.md` | Upfront cash required across optimistic, base and conservative scenarios |

Matching JSON files preserve the structured results and inputs. The workspace's `demo-inputs/` folder contains complete example files for the individual commands.

Use a new workspace name when repeating a demo, such as `workspaces/second-journey`. Existing merchant inputs are never silently overwritten.

## The five-step merchant journey

| Step | What MerchMind does |
| --- | --- |
| **1. Guided setup** | Asks about your business, niche, market, budget, sourcing sites and product restrictions. |
| **2. Customer research** | Prepares research questions; optionally connects approved Brave search results with DeepSeek synthesis to develop three or four customer hypotheses. |
| **3. Product comparison** | Applies explicit rules to evidenced product attributes and shows matches, mismatches, unknowns and coverage for each group. |
| **4. Customer validation** | Records aggregate interviews, surveys, sample tests, sales and returns against the original hypotheses. |
| **5. Launch costs** | Estimates batch cash needs using supplier minimum quantities, applicable price tiers, import costs, samples, setup, ads, contingency and reserves. |

Customer groups remain **hypotheses**. Search results, listing counts or a high attribute-match score do not establish demand, willingness to pay or a psychological model of real people. Validation summaries preserve conflicting observations and do not automatically declare a group proven.

The [merchant journey guide](docs/merchant-journey.md) explains each command, input format and calculation assumption.

## Start your own business workspace

```sh
uv run merchmind onboard --workspace workspaces/my-store
```

Answer the guided questions. No sales history is required. Optional costs can be left blank and remain unknown.

For a repeatable or agent-driven setup, prepare an answer file using [the example format](examples/onboarding-answers.json):

```sh
uv run merchmind onboard --workspace workspaces/my-store --answers my-answers.json
```

Choose one setup method and a new workspace. Replace sample business details and approved hostnames before using real data. The resulting workspace includes your merchant settings, niche brief, source/scoring policies, budget input and readiness checks.

### Explore a niche without sales

```sh
uv run merchmind profile starter prepare --workspace workspaces/my-store --brief workspaces/my-store/niche-brief.json
uv run merchmind profile starter build --workspace workspaces/my-store --brief workspaces/my-store/niche-brief.json
```

`prepare` creates research questions and queries. `build` without researched inputs creates generic, low-confidence draft groups to investigate. It does not search the web or claim to know what customers want.

You can import a source-backed synthesis from a merchant or external agent using `build --research FILE`. See the [starter-mode guide](docs/starter-mode.md).

### Connect online research when ready

The optional connection uses **Brave Web Search** and **DeepSeek JSON synthesis**. It requires your provider accounts, current configured prices, approved research hosts and explicit sharing consent.

Copy [the connection template](config/research-connection.example.yaml) into your private workspace, set its model, hosts and prices, and export the configured key environment variables. Then run:

```sh
uv run merchmind profile starter research --workspace workspaces/my-store --brief workspaces/my-store/niche-brief.json --connection workspaces/my-store/research-connection.yaml --online --share-brief
```

This sends the niche brief, queries and public snippets to the providers. Customer files and merchant financial settings are not inserted into prompts. Keys are not saved in reports. Unknown provider prices block execution; estimated limits are separate from provider account billing caps.

Collected snippets remain unverified, and synthesized groups remain low-confidence hypotheses. Failed or malformed responses produce partial results with available sources and warnings.

See the [connection instructions](docs/merchant-journey.md#2-connected-research) for environment variables, limits and current verification status. Live provider accounts have not yet been qualified; automated tests use mocked responses.

## Already have sales history?

Import your catalog first, followed by sales and optional returns, then build an observed profile:

```sh
uv run merchmind import products --workspace workspaces/my-store --file my-products.csv
uv run merchmind import sales --workspace workspaces/my-store --file my-sales.csv
uv run merchmind import returns --workspace workspaces/my-store --file my-returns.csv
uv run merchmind profile build --workspace workspaces/my-store
```

The `my-*.csv` files are files you supply. See [sample files](examples/) and the [data dictionary](docs/data-dictionary.md) for required fields. Sales values must use the workspace currency; customer contact columns are rejected. Profiles distinguish gross sales observations from unavailable net-revenue or repeat-purchase metrics.

Review the [onboarding guide](docs/onboarding.md) before importing real records. Merchant IDs in research and cost files must match your workspace.

## Evaluate a specific product

The targeted-research workflow accepts a product name or URL, reviewed supplier/local-price evidence and three cost scenarios. Its JSON and Markdown reports recommend:

| Decision | Meaning |
| --- | --- |
| **Test** | Supplied evidence and economics pass the configured checks. Consider a controlled sample. |
| **Investigate** | Important information is missing, uncertain or below your requirements. |
| **Reject** | A hard rule failed, such as an excluded category, blocked safety review or unacceptable conservative margin. |

Money uses decimal arithmetic. Unknown costs stay unknown. Tax inputs require confirmation and evidence. Per-unit contribution, launch cash, recoverable VAT and held reserves are kept distinct.

The core economics and scoring work without an AI model. Six [project skills](.agents/skills/) support external agent orchestration; live DeepSeek Harness skill loading still needs verification.

## Other demos

These commands also run offline after dependency setup. Use a new workspace for each:

```sh
uv run merchmind demo --mode starter --workspace workspaces/starter-only
uv run merchmind demo --mode sales --workspace workspaces/sales-only
```

Starter-only mode produces unresearched draft groups. Sales-only mode uses a fictional catalog, orders and returns to produce a product decision report. All demo research, prices, taxes and supplier details are synthetic.

## Current limits

- Automatic supplier shortlists, verified marketplace-price extraction and dedicated Alibaba/1688 connectors are not implemented.
- Product comparisons require explicit criteria and reviewed attribute evidence. They do not simulate customers voting on a product.
- Customer observations are entered/imported by the merchant; collecting interviews and reconciling profiles with later sales are not automatic.
- Launch estimates depend on supplied costs and documented assumptions, including all ordered units being sellable.
- The toolkit does not order products, send supplier messages, make payments, modify accounts or bypass login/CAPTCHA restrictions.
- Services and digital products need different sourcing and economics workflows.
- Live-provider checks, hosted CI results, DSH qualification and the real-store pilot are separate from local test success.

Read the [source policy](docs/connector-policy.md) and [implementation status](docs/status.md) for details.

## Privacy and evidence

Workspaces, generated reports, local environments and secret files are ignored by Git. Default workflows keep data local. Connected research shares the niche brief and public snippets only after explicit consent. Validation records and merchant financial files are not inserted into provider prompts.

Keep personal information and credentials out of notes and imported records. Unsupported contact fields are rejected, but free-text notes still require review. The ignored `.env` file is not automatically loaded by the application.

Evidence and earlier reports are preserved. Customer-study corrections create new records rather than overwriting old ones, and ledger locks prevent simultaneous commands from bypassing duplicate checks. Content hashes detect accidental edits; they are not a signed, tamper-proof archive.

See [security reporting](SECURITY.md) and the [threat model](docs/threat-model.md).

## Common problems

| Problem | What to do |
| --- | --- |
| `uv` is not found | Install uv, reopen the terminal and check `uv --version`. |
| A workspace already exists | Choose a new folder. Existing inputs are preserved. |
| A result is `investigate`, `unknown` or `not_estimated` | Read the report's missing-evidence or missing-input list. |
| Connected research cannot start | Check keys, configured prices, approved hosts and both consent flags. |
| A provider returns a partial result | Review its sources and warnings; correct the connection or use a manual research import. |
| A financial value fails validation | Use quoted decimal strings, such as `"17.50"`, with explicit currency and units. |
| The validation ledger is busy | Retry after the other operation finishes; see the guide before removing a stale lock. |

Run `uv run merchmind --help` to see all commands. Add `--help` after a command for its arguments, for example `uv run merchmind launch estimate --help`.

## Development

The project uses a `src/` package layout, `pyproject.toml`, locked dependencies, Pydantic contracts, JSON Schema, pytest and Ruff. Install development tools and run:

```sh
uv sync --locked --extra dev
uv run pytest -q
uv run ruff check .
uv run ruff format --check .
uv run python scripts/check_skills.py
```

After changing models, regenerate schemas with `uv run python scripts/export_schemas.py`. CI is configured for Linux and Windows with Python 3.12 and 3.14, plus package-install demos. Local skill metadata checks do not establish live agent-runtime compatibility.

See [contributing](CONTRIBUTING.md), [architecture](docs/architecture.md), [the DSH adapter](adapters/dsh/README.md) and [evaluation](docs/evaluation.md). MerchMind uses the [Apache 2.0 license](LICENSE).
