# Implementation baseline index

The active software-development implementation baseline candidate is **SDIB-1.4**; protected-main adoption is pending exact-head CI and merge-SHA requalification.

Candidate entry evidence:
- parent implementation baseline: SDIB-1.3
- M4 Exit protected-main SHA: `de42de880e25102b9dfb5b06ffff18a37ca1fdc1`
- M4 Exit Run #435 / `36430788368`: PASS, 14/14 jobs / GO
- Core baseline: CB-1.4.0
- DB schema: 1.6.0
- baseline directory: `docs/baseline/SDIB-1.4/`
- candidate main document SHA-256: `00ab4ac1ef9c3fa3c0a85bd0466dcc2f6174cc7e921af5759bd5c42d22aaa5e6`
- candidate M5 task baseline SHA-256: `89eb4b69cb5af94476983b957584807fb62eb48ffa435a1fc79f00c8b9a348cc`

SDIB-1.4 refines M5 `P1 Product Qualification & Release` into 23 Tasks / four coarse batches and binds exact four mandatory certification profiles from `PLATFORM_COMPATIBILITY_REGISTRY.json`.

C3 #136 is the hard fail-closed authority blocker for exact formal qualification parameters. Dependent M5 performance/security/package/recovery/release-acceptance work cannot claim qualification until that machine authority is adopted on protected main.

Historical baselines remain for auditability. See `docs/reviews/SDIB-1.4_ADOPTION_REVIEW.md`.
