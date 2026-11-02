# Threat model

| Threat | Implemented control | Remaining boundary |
| --- | --- | --- |
| Web prompt injection | No webpage instructions or commands execute; page titles stay unverified | An external agent must still treat all imported content as untrusted |
| SSRF and DNS rebinding | Exact host allowlist, public-IP validation, address-pinned TLS, no redirects or proxies | Network policies and resolver availability depend on deployment |
| Credential leakage | No credential-required connector, URL queries removed/refused, common secret redaction, no input echo in validation errors | Redaction is not a complete DLP system; merchants must sanitize imports |
| PII import | Strict field allowlist and already-hashed order IDs | Merchant notes, product names and manually supplied assertions still require review |
| Misleading product variants | Explicit variant identity; exact comparable and matching supplier gates | Identity is merchant-reviewed, not independently authenticated |
| Incorrect money or omitted tax | Decimal strings, explicit units, dated FX, null unknowns, confirmed tax evidence | The toolkit cannot verify customs classifications or official amounts |
| Falsely labeled evidence | Provenance, freshness labels, evidence references and hashes | Merchant-provided labels and hashes are not external verification |
| Path traversal and overwrite | Resolved workspace boundaries and exclusive output writes | A trusted local user can intentionally edit workspace files |
| Edited results | Historical replay checks arithmetic and scoring snapshots | No signed, tamper-proof evidence archive is provided |
| Resource exhaustion | Input size, request count, response size, report size and duration limits | Total history storage and external agent token spend require operator limits |

The toolkit never initiates checkout, payments, supplier messages or account modifications. Default workflows are local and use synthetic fixtures without credentials. Optional connected research transmits only the niche brief and public snippets to fixed provider APIs after explicit `--online --share-brief` consent. Provider keys come from environment variables and are excluded from saved request records. Search/model responses remain untrusted, citations are validated, and no model tools execute. Account-level spending limits remain an external boundary. Validation observations and merchant financial files are not inserted into provider prompts.
