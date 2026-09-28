# SDIB-1.4 Change Note

- Parent: SDIB-1.3
- Date: 2026-09-28
- Nature: post-M4 task-level implementation refinement for M5; no Canonical/business semantic change in this C1 revision.
- Entry evidence: M4 protected-main Exit GO at `de42de880e25102b9dfb5b06ffff18a37ca1fdc1`, Run #435 / Actions run `36430788368`.
- M5 is refined to 23 Tasks across WS-PLATFORM, WS-PERFORMANCE, WS-SECURITY, WS-DEVOPS, WS-TEST and WS-GOVERNANCE, grouped into four batches under #120.
- Mandatory certification inventory is exact four profiles from PLATFORM_COMPATIBILITY_REGISTRY.
- Existing DB schema 1.6.0 and immutable Release/replay semantics are retained; no shadow schema.
- M5 remains P1-only; P2-P6 are not admitted.
- Missing exact formal qualification parameters are not invented here; C3 #136 / M5-GOV-001 is a hard dependency.
- M5 Exit requires exact 23/23 evidence, four-profile qualification, governed target-workload performance/resource and security acceptance, package lifecycle, upgrade/rollback, backup/restore, same-candidate logical equivalence, cold-start and protected-main GO.
