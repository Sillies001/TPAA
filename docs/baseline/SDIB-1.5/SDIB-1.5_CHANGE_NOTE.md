# SDIB-1.5 Change Note

- Parent: SDIB-1.4
- Date: 2026-09-29
- Nature: post-M5 C1 task-level implementation refinement for M6 / P2; no P2 admission occurs in this revision.
- Entry protected main: `aae1e692774f7c10114d66fd79acb254c2aabfef`, Run #472 / `36556569965`, 14/14 PASS.
- Program policy: #149.
- M6 baseline tracking: #150.
- P2 C3 authority blocker: #151.
- M6 is refined to 17 Tasks across WS-CAPABILITY, WS-DATA, WS-TEST, WS-GUI and WS-GOVERNANCE, grouped into four coarse batches.
- Existing CB-1.4.0 / DB schema 1.6.0 / immutable P1 Release-replay semantics are retained; no shadow schema.
- P1 remains admitted and immutable; P2 remains candidate-only until protected-main M6 Exit GO; P3-P6 remain inactive.
- One-milestone-ahead rolling design is mandatory: M7/P3 detailed design proceeds during active M6 implementation, but P3 implementation/admission remains forbidden before M6 Exit GO.
- Missing exact P2 factor/reference/cohort, identifiability, uncertainty, DTO and Release/evidence semantics are not invented here; C3 #151 / M6-GOV-001 is fail-closed.
