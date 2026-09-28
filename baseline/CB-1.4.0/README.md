# CB-1.4.0 Controlled Snapshot

This directory remains the repository Canonical trust root for CB-1.4.0. The original R3.3 controlled artifacts remain byte-identical; governed C3 extensions add explicit semantic authority without changing DB schema 1.6.0.

- Core baseline: `CB-1.4.0`
- Rebaseline: `R3.5_M4_LONGITUDINAL_DEBRIEF_AUTHORITY`
- DB schema target: `1.6.0`
- Approved candidate `BASELINE_LOCK.json` SHA-256: `8bc1834502561992e9aef64d73186c7854ef293e4ec57f658b4e9f72828e0cab`
- Controlled artifacts: `23`
- Historical lock lineage preserves M2 C3 adopted lock: `d6ebab2b5402cf81a0b5f73a2da4ed2aaa2d530bc7445c7f6132dcf7fa72224d`
- Existing C3 authority: `canonical/M2_QA_SNS_AUTHORITY.json` v1.0.0, SHA-256 `1f0755836e7ea40b3b69c83dae1b2b636ff80e37d8630c5ce158d5dfccffd5d3` (#106)
- Added M4 C3 authority: `canonical/M4_LONGITUDINAL_DEBRIEF_AUTHORITY.json` v1.0.0, SHA-256 `c1c073bce8870feceb90bdb6c28172c4c726de6b15fc70208e169336baa59dfa` (#122)

The M4 authority freezes exact P1 longitudinal sample/trend/comparison-key/replay and longitudinal/debrief DTO semantics while preserving the existing Core tables and DB schema 1.6.0. It is a new C3 decision, not a recovered R3.3/R3.4 source fact. Downstream implementation may consume it only after protected-main adoption of this lock.
