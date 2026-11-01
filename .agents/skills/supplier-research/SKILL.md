---
name: supplier-research
description: Normalize supplier terms, MOQ tiers and verification evidence while preserving the difference between advertisements and confirmed quotes.
---

Use when comparing supplier offers for a specified canonical variant.

1. Capture supplier identity, source URL, exact variant, currency, MOQ, sorted price tiers, product and packaging mass, Incoterm, lead time, quote time and expiry. Keep missing facts unknown.
2. Use authorized exports or merchant-provided quotations. Run `merchmind import quotes --file FILE --workspace WORKSPACE` to normalize CSV/JSON terms. See `docs/data-dictionary.md` for CSV cells containing JSON arrays/maps.
3. Confirm the merchant's checklist: supplier identity, product authenticity, trade terms and sample policy. Record unresolved flags. A listing price is advertised; do not upgrade it to confirmed without merchant evidence.
4. Review freshness and the imported source receipt before setting a source to current. Imported evidence is merchant-provided, not independently verified. Preserve supporting records privately.
5. Merge the resulting quotes/sources into the research bundle. Only current, unexpired, matching confirmed quotes with all four checks and no unresolved flags clear the supplier gate.

No Alibaba or 1688 API integration is presumed available. Do not bypass authentication/CAPTCHA, use browser cookies, contact suppliers or negotiate autonomously. Missing access means unavailable and a manual fallback.
