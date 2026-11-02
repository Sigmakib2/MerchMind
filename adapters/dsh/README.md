# DeepSeek Harness adapter

MerchMind exposes six portable skills in `.agents/skills/` and a runtime-independent JSON CLI. It imports no DSH libraries and needs no model for its offline demo or economics engine.

Live research is agent-led: the runtime's existing browsing and reasoning tools collect sources and synthesize an `AgentSubmission`. The local `agent prepare/complete` commands handle the task contract, receipts and profile outputs without a separate search/model API. Read `docs/agent-workflow.md`. Preparing a task does not start DSH or grant new tool permissions.

Upstream's [skill subsystem documentation](https://github.com/deepseek-ai/deepseek-harness/blob/master/docs/subsystems/skills.md) lists project `.agents/skills/` as a local discovery root beneath the nearest Git repository. That document was inspected on 2026-11-01. Actual discovery depends on the installed DSH build and composition.

## Local contract smoke

```sh
uv run python scripts/check_skills.py
uv run merchmind demo --workspace workspaces/dsh-contract-demo
```

This checks skill frontmatter and exercises the local commands only. It must not be reported as a DSH runtime smoke test.

## Runtime qualification procedure

Install and pin a DSH build through the [upstream instructions](https://github.com/deepseek-ai/deepseek-harness). Start the runtime with this repository as the working directory and inspect its skill catalog. Verify that all six names are present and load `product-research`.

Ask the orchestrator to review a synthetic demo request, invoke the local CLI through its shell tool, validate the saved report, and return its artifact paths. Use only the synthetic workspace and no live credentials. Confirm the report is written beneath the expected workspace and that no network, purchase, supplier message or upload occurs. Use separate workspaces for repeated demos because initialization refuses overwrites.

Record the exact DSH version/commit, OS, Python version, discovery/load results, command invocation, report path and transcript in `docs/compatibility-matrix.md`. Repeat after changing the runtime. Root `AGENTS.md` is a repository convention; runtime enforcement must be verified rather than assumed.

An external orchestrator must enforce its own model token/spend limits and untrusted-content isolation. MerchMind's `--online` flag and source allowlist govern only its built-in network adapter. They do not restrict arbitrary tools granted directly to the orchestrator.
