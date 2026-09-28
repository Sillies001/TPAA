# SDIB-1.4 Adoption / M5 Refinement Review

## Review identity
- **Change class:** C1 — post-M4 backlog refinement.
- **Candidate baseline:** SDIB-1.4; parent SDIB-1.3.
- **Tracking issue:** #135; program policy #120; formal qualification authority closure #136.
- **Core baseline / DB schema:** CB-1.4.0 / 1.6.0.
- **Document SHA-256:** `00ab4ac1ef9c3fa3c0a85bd0466dcc2f6174cc7e921af5759bd5c42d22aaa5e6`.
- **M5 manifest SHA-256:** `89eb4b69cb5af94476983b957584807fb62eb48ffa435a1fc79f00c8b9a348cc`.

## Entry evidence
M4 protected-main SHA `de42de880e25102b9dfb5b06ffff18a37ca1fdc1`, Run #435 / `36430788368` is PASS (14/14 jobs) and `TPAA_M4_EXIT_REVIEW_V1 decision=GO`, `protected_main_exact=true`, 21/21 M4 tasks, `failed_acceptance=[]`.

## Candidate refinement
SDIB-1.4 freezes 23 M5 Tasks: GOVERNANCE 3, PLATFORM 5, PERFORMANCE 2, SECURITY 2, DEVOPS 4, TEST 7; exactly four coarse batches. M5 remains P1-only and binds exact four mandatory certification profiles from PLATFORM_COMPATIBILITY_REGISTRY.

## C3 boundary
SDIB-1.4 intentionally does not invent target hardware/workload identities, performance/resource thresholds, security/vulnerability acceptance, package/install rules, upgrade/rollback, backup/restore or formal release acceptance/signoff. C3 #136 is fail-closed until dedicated machine authority is adopted on protected main.

## Protected-main adoption
ADOPTED by PR #137.
- exact candidate head: `a8a9a342a0b1a347e575169234553ec97d8078e9`
- exact-head Run #436 / `36433513907`: PASS, 14/14 jobs
- actual protected-main merge SHA: `de5dfb528156428eee93ce4d022350382cbf4127`
- protected-main Run #437 / `36435473663`: PASS, 14/14 jobs

**Decision: ADOPTED.** M5 implementation remains fail-closed where task dependencies require C3 #136 until its protected-main adoption.
