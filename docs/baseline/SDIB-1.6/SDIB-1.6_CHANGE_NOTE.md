# SDIB-1.6 Change Note

- Parent: SDIB-1.5
- Date: 2026-09-30
- Nature: post-M6 C1 task-level implementation refinement for M7 / P3; no P3 admission occurs in this revision.
- Entry protected main: `892e4a64a321be9c7252b66207a7d1d90a6ce98d`, Run #494 / `36697493917`, 14/14 PASS.
- Entry M6 Exit: GO / `P2_M6_QUALIFIED`.
- Program policy: #149.
- M7 baseline tracking: #168.
- P3 C3 authority blocker: #169.
- M8/P4-P5 design runway: #170.
- M7 is refined to 18 Tasks in four coarse batches.
- Canonical required M7 workstreams remain WS-CAPABILITY, WS-LONGITUDINAL, WS-TEST, WS-GUI and WS-GOVERNANCE; WS-DATA and WS-API are supporting workstreams.
- Existing CB-1.4.0 / DB schema 1.6.0 / immutable P1 and P2 Release-replay semantics are retained; no shadow schema.
- P1 and P2 remain admitted and immutable; P3 remains candidate-only until protected-main M7 Exit GO; P4-P6 remain inactive.
- Exact P3 model/plugin/profile, validation/applicability thresholds, claim tiers, managed-object binding and DTO semantics are not invented here; C3 #169 / M7-GOV-001 is fail-closed.
- One-milestone-ahead rolling design continues through #170; M8 implementation/admission remains forbidden before M7 Exit GO.
