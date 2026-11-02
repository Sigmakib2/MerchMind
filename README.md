# MerchMind

MerchMind helps small online sellers answer two questions:

- Does this product fit my business and customers?
- How much money could be left after buying, importing and selling it?

It combines your sales history, supplier quotes, local prices and cost assumptions into a report. Each report shows its sources, calculations and missing information, then recommends **test**, **investigate** or **reject**.

**Current stage: developer alpha.** The local command-line toolkit and offline demo work. Real-store evaluation and live DeepSeek Harness integration still need verification. See [what is built and what remains](docs/status.md).

## Run your first demo

### 1. Check the requirements

Install:

- [Python](https://www.python.org/downloads/) 3.12 or later.
- [uv](https://docs.astral.sh/uv/getting-started/installation/), which installs and manages the project's Python dependencies.

Open a terminal in the MerchMind folder. The following commands should print the installed versions:

```sh
python --version
uv --version
```

On Windows, `py --version` can be used to check Python if `python` is unavailable. Internet access is needed to download dependencies during setup.

### 2. Install and run

```sh
uv sync --locked
uv run merchmind demo --workspace workspaces/demo
```

The first command creates an isolated Python environment and installs the versions recorded in `uv.lock`. The second runs the complete demo using fictional store data. The demo needs no AI account, API key, paid service or internet connection once setup is complete.

### 3. Open the report

The command prints a result containing `artifact_paths`: the locations of the files it created. Open the file ending in **report.md** for the readable report. Find it under:

```text
workspaces/demo/reports/<run-id>/report.md
```

The demo also creates a customer profile and supporting files:

| File | Purpose |
| --- | --- |
| `customer-profile.md` | Summarizes outcomes in the sample sales history |
| `report.md` | Explains the product decision and cost scenarios |
| `report.json` | Keeps the structured results and calculation inputs |
| `sources.jsonl` | Records the evidence behind the report |
| `run-log.jsonl` | Records the saved run |

The sample decision is **test**, with a score of **81/100**. Its conservative scenario has a landed cost of **494 BDT** and **331 BDT** left after the included product and selling costs. This is contribution, before expenses outside the calculation, such as fixed business overhead. All demo prices, exchange rates, taxes and supplier details are fictional.

To run the demo again, choose another folder, such as `workspaces/demo-2`. MerchMind refuses to replace an existing workspace.

## Understand the decision

| Decision | What it means |
| --- | --- |
| **Test** | The supplied evidence and economics pass the configured checks. Consider a small, controlled sample. |
| **Investigate** | Important information is missing, uncertain or below your requirements. Read the report's missing-evidence list. |
| **Reject** | A hard rule failed, such as an excluded category, blocked safety review or unacceptable conservative margin. |

A high score does not guarantee sales. Missing costs stay unknown; they are never silently counted as zero.

## Starting without existing customers?

For guided setup, optional connected research, product comparison, customer feedback and launch costs, see the [merchant journey guide](docs/merchant-journey.md). Try all five stages offline:

```sh
uv run merchmind demo --mode journey --workspace workspaces/my-journey-demo
```

For your own business, run `uv run merchmind onboard --workspace workspaces/my-store` and answer the questions. No sales history is required.

Use **starter mode** to explore a niche before you have sales history:

```sh
uv run merchmind demo --mode starter --workspace workspaces/fitness-starter
```

It creates three or four possible customer profiles, questions to research, and product-search directions for approved sourcing sites. The demo uses lightweight home fitness as an example. These are unvalidated hypotheses: the offline demo does not search the web or claim to know what real buyers want.

You can describe your own niche and add a source-backed synthesis from a merchant or external research agent. Read the [starter-mode guide](docs/starter-mode.md) for the full workflow and current limits.

## Use your own business data

Start with a separate workspace:

```sh
uv run merchmind init --workspace workspaces/my-store
```

Then follow these steps:

1. **Set up your business.** Edit `merchant.yaml` inside that workspace. Set your market, currency, shipping assumptions, product restrictions and target margin. The initial values are demo defaults.
2. **Import your history.** Use the files in `examples/` as format guides for your catalog, sales and returns. Import the catalog first, then sales and optional returns.
3. **Build the customer profile.** Review the sales observations before using them to assess a new product.
4. **Prepare your product research.** Supply its name or URL, exact variation when known, reviewed evidence, supplier quotes and local price comparisons.
5. **Estimate costs and read the report.** Supply optimistic, base and conservative scenarios, including dated exchange rates and confirmed tax inputs. Check the missing-evidence list before acting.

The [onboarding guide](docs/onboarding.md) explains the fields and evidence review. The [data dictionary](docs/data-dictionary.md) explains file formats, units and supplier imports. Your request and cost files must use the same merchant ID as your workspace.

To try an incomplete research request with the demo workspace:

```sh
uv run merchmind research run --workspace workspaces/demo --request examples/partial-request.json
```

This returns **investigate** and lists the information still needed. It does not invent the missing research.

Run `uv run merchmind --help` to see the available commands. Add `--help` after a command, for example `uv run merchmind research run --help`, for its options.

## What this version can do

- Import CSV or JSON catalogs, sales, returns and supplier quotes.
- Build customer profiles from aggregate sales observations.
- Explore a new niche without sales history through distinct starter hypotheses and guided sourcing plans.
- Set up a business through guided questions and optionally connect Brave search with DeepSeek synthesis.
- Compare evidenced product attributes with customer hypotheses and track real validation observations.
- Estimate total launch cash using minimum quantities, applicable price tiers and upfront costs.
- Calculate shipping, landed cost and contribution across three scenarios.
- Score opportunities with visible evidence coverage and decision rules.
- Save reports, preserve their inputs and check that calculations can be reproduced.
- Provide six research skills for an external agent runtime, including DeepSeek Harness (DSH).

Research runs offline by default. An explicit `--online` option enables limited, read-only retrieval from approved websites. The generic page adapter records an unverified title and receipt hash. Optional connected research uses approved search results and model synthesis with configured accounts, budgets and `--share-brief` consent. Reviewed imports supply prices and supplier facts; automatic verified marketplace-price extraction is not implemented. See the [source policy](docs/connector-policy.md) and [merchant journey guide](docs/merchant-journey.md).

MerchMind does not place orders, send supplier messages, make payments or bypass login and CAPTCHA restrictions. Alibaba and 1688 do not yet have dedicated connectors. Live DSH skill loading and a real-store pilot remain release checks; local skill checks do not establish runtime compatibility.

## Keep business data private

Workspaces, generated reports and environment files are ignored by Git. Default workflows keep data local. Optional connected research sends the niche brief and public snippets only after explicit sharing consent; merchant financial files and validation records are not inserted into provider prompts. Imports reject unsupported fields such as customer email or phone columns. Remove personal information and credentials from your own notes and source records before importing them.

See the [security policy](SECURITY.md) for reporting vulnerabilities and the [threat model](docs/threat-model.md) for current controls and limits.

## Common problems

| Problem | What to do |
| --- | --- |
| `uv` is not found | Install uv, reopen the terminal and check `uv --version`. |
| The workspace already exists | Use a new folder name. Existing inputs are preserved. |
| The decision is `investigate` | Read the missing-evidence list in `report.md`. An incomplete report can be a valid result. |
| A cost is `not_estimated` | Supply the missing inputs, current exchange rate or confirmed tax evidence. |
| A financial value fails validation | Use quoted decimal strings, such as `"17.50"`, with the required currency and units. |
| A website cannot be accessed | Use an authorized CSV/JSON export or a manually reviewed quote. |

## Development and project conventions

The project uses a `src/` package layout, `pyproject.toml` for package configuration, a `uv.lock` dependency lockfile, Pydantic input validation, JSON Schema contracts, pytest tests and Ruff formatting/linting. Financial calculations use Python's decimal arithmetic and run independently of any AI model.

Install the development tools and run the checks:

```sh
uv sync --locked --extra dev
uv run pytest -q
uv run ruff check .
uv run ruff format --check .
uv run python scripts/check_skills.py
```

When changing data models, regenerate the schemas with `uv run python scripts/export_schemas.py`. GitHub Actions is configured to run the checks on Linux and Windows with Python 3.12 and 3.14; local checks alone do not establish that hosted CI has passed.

Read the [contribution guide](CONTRIBUTING.md), [architecture](docs/architecture.md), [DSH adapter instructions](adapters/dsh/README.md) and [implementation status](docs/status.md) for more detail. The project uses the [Apache 2.0 license](LICENSE).
