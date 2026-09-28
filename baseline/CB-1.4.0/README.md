# CB-1.4.0 Controlled Snapshot

This directory remains the repository Canonical trust root for CB-1.4.0. The original R3.3 controlled artifacts remain byte-identical; governed C3 extensions add explicit semantic/qualification authority without changing DB schema 1.6.0.

- Core baseline: `CB-1.4.0`
- Rebaseline: `R3.6_M5_FORMAL_QUALIFICATION_AUTHORITY`
- DB schema target: `1.6.0`
- Approved candidate `BASELINE_LOCK.json` SHA-256: `e4f6c2bb97c169cc8db9eecfa09c67201510b5fad85e6e59fc2b96532b011db9`
- Controlled artifacts: `24`
- Lock lineage: immediate prior M4 C3 lock `8bc1834502561992e9aef64d73186c7854ef293e4ec57f658b4e9f72828e0cab`; earlier M2 C3 lock `d6ebab2b5402cf81a0b5f73a2da4ed2aaa2d530bc7445c7f6132dcf7fa72224d`
- Existing C3 authority: `canonical/M2_QA_SNS_AUTHORITY.json` v1.0.0, SHA-256 `1f0755836e7ea40b3b69c83dae1b2b636ff80e37d8630c5ce158d5dfccffd5d3` (#106)
- Existing M4 C3 authority: `canonical/M4_LONGITUDINAL_DEBRIEF_AUTHORITY.json` v1.0.0, SHA-256 `c1c073bce8870feceb90bdb6c28172c4c726de6b15fc70208e169336baa59dfa` (#122)
- Added M5 C3 authority: `canonical/M5_FORMAL_QUALIFICATION_AUTHORITY.json` v1.0.0, SHA-256 `e3dd1fafa9c65d6c9a85dfb7172d60adef3e9c17893e3b546b962275c42c01b1` (#136)

The M5 authority freezes formal P1 qualification hardware/workload/performance/resource/security/package/upgrade/rollback/backup/restore/release-acceptance semantics for the exact four mandatory certification profiles. It preserves existing P1 business semantics, Core tables, DB schema 1.6.0 and immutable Release/replay behavior. It is a new C3 decision, not a recovered R3.5 source fact, and becomes active only after protected-main adoption of this lock.
