# Security policy

This is an early local toolkit. Run only reviewed source code and sanitize merchant imports. Never commit customer records, account credentials or private workspace contents. Examples must be synthetic.

For a vulnerability, use the repository host's private vulnerability reporting feature if enabled, or contact the maintainer privately through an established channel. No dedicated security mailbox is configured. Do not open a public issue containing secrets, private records or an exploit against a real merchant account. A redacted issue asking for a private contact is acceptable if no private channel is available.

Include affected version, a minimal synthetic reproduction, expected/observed behavior and potential impact. Credential leakage, private-network access, arbitrary execution and unauthorized external actions receive priority. See `docs/threat-model.md` for controls and remaining trust boundaries. No response-time SLA or supported-version guarantee is established for this prerelease.
