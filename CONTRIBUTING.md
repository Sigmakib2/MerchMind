# Contributing

Install with `uv sync --locked --extra dev`. Run `uv run pytest -q`, `uv run ruff check .` and `uv run ruff format --check .` before submitting changes. Regenerate schemas with `uv run python scripts/export_schemas.py` when models change. Example snapshot regeneration is intentional and uses `scripts/export_examples.py`; do not refresh timestamps just to hide stale evidence.

Use small typed modules, decimal commercial values, explicit unknowns and immutable evidence. Include meaningful failure fixtures for new connectors or financial behavior. Never include real customer records, credentials, private supplier links or non-redistributable page captures in public tests or issues. Explain source authorization and rate limits for connector proposals.

The core must remain independent of any agent runtime. Document DSH compatibility only after verifying the actual runtime version, skill discovery, invocation and saved report. Keep scheduled discovery behind the pilot gate. See `SECURITY.md` for vulnerability reporting.
