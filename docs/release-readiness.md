# GitHub readiness review

Review date: 2026-11-01. Recommendation: share this repository as a **developer alpha**. The offline toolkit is working; the full product specification is not yet commercially validated.

## Problems corrected during review

- Malformed YAML now returns a structured error without echoing private source lines.
- A known non-positive conservative margin triggers its configured rejection rule even when another scenario has missing inputs.
- CSV imports now enforce the same 10 MB input limit as JSON and reject duplicate headers, broken quoting and mismatched row lengths.
- Customer profiles check catalog and sales evidence hashes and record order before citing them. Missing, reordered or altered import snapshots fail explicitly.
- Source archives now include documentation, schemas, example data, skills, scripts and test fixtures. CI also builds and installs the wheel in a separate environment before running its demo.
- The README labels the project as a developer alpha and explains current limits.

## Verification performed

| Check | Result |
| --- | --- |
| Windows, Python 3.12.16 | 113 tests passed, 1 skipped |
| Windows, Python 3.14.6 | 113 tests passed, 1 skipped |
| Skipped test | Filesystem symlink creation is unavailable in this environment |
| Ruff lint and formatting | Passed |
| Project skill metadata | Six skills validated locally |
| Installable package | Built and installed in a fresh environment; isolated offline demo succeeded |
| Git exclusions | Merchant workspaces, environment files, local environments and build/test outputs are ignored |
| Credential-pattern scan | No common private-key, AWS access-key, GitHub-token or OpenAI-key patterns found in Git-visible files, including XML inside the requirements document |

The credential scan is a pattern check, not proof that every possible secret format has been excluded. No GitHub-hosted CI result is claimed: the configured workflows still need to run after pushing.

## Before a stable release

The maintainer should require passing hosted CI, qualify skill discovery and invocation against an exact DeepSeek Harness build, audit an authorized live source, and complete the historical merchant pilot without revealing future outcomes to the evaluator. Marketplace-specific connectors and autonomous discovery remain outside this implementation.

GitHub is suitable for sharing this alpha, collecting issues and running CI. A push should not be presented as a production-ready launch or a claim of improved merchant profitability.
