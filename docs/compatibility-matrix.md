# Compatibility matrix

| Component | Target | Verification |
| --- | --- | --- |
| Core engine | Python 3.12+ | Local tests pass on Windows/Python 3.12 and 3.14; CI configured for Windows/Linux, 3.12 and 3.14 |
| Offline workflow | No model or account | Local demo and replay exercised |
| DeepSeek Harness | Exact tested build pending | DSH executable not present in the development environment; local skill metadata check is available |
| Other agent runtimes | CLI and portable skills | No runtime-specific qualification claimed |
| Alibaba/1688 | Manual quote/CSV fallback | No marketplace-specific live connector |
| Generic HTTPS | Approved exact host, TLS, robots | Mocked contract/security tests; real authorized source audit pending |
| Agent handoff | Runtime-owned browsing and synthesis, no separate search/model API | Local submission/demo checks available; actual browsing/tool qualification pending for each runtime |

Do not label DSH compatible for a release until discovery, skill loading, local command invocation and report writing are all recorded against an exact runtime build. Follow `adapters/dsh/README.md`.
