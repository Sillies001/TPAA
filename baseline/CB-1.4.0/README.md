# CB-1.4.0 Controlled Snapshot

This directory remains the repository Canonical trust root for CB-1.4.0. The original R3.3 controlled artifacts remain byte-identical; governed C3 extensions add explicit semantic/qualification authority without changing DB schema 1.6.0.

- Core baseline: `CB-1.4.0`
- Rebaseline: `R3.7_M6_P2_ATTRIBUTION_NORMALIZATION_AUTHORITY`
- DB schema target: `1.6.0`
- Approved candidate `BASELINE_LOCK.json` SHA-256: `64116b8b18ecbfdddab3ea045ed40504e28c3431ebe0082fe9c99f56a7ef8067`
- Controlled artifacts: `25`
- Lock lineage: immediate prior M5 C3 lock `e4f6c2bb97c169cc8db9eecfa09c67201510b5fad85e6e59fc2b96532b011db9`; earlier M4 C3 lock `8bc1834502561992e9aef64d73186c7854ef293e4ec57f658b4e9f72828e0cab`; M2 C3 lock `d6ebab2b5402cf81a0b5f73a2da4ed2aaa2d530bc7445c7f6132dcf7fa72224d`
- Existing C3 authority: `canonical/M2_QA_SNS_AUTHORITY.json` v1.0.0, SHA-256 `1f0755836e7ea40b3b69c83dae1b2b636ff80e37d8630c5ce158d5dfccffd5d3` (#106)
- Existing M4 C3 authority: `canonical/M4_LONGITUDINAL_DEBRIEF_AUTHORITY.json` v1.0.0, SHA-256 `c1c073bce8870feceb90bdb6c28172c4c726de6b15fc70208e169336baa59dfa` (#122)
- Existing M5 C3 authority: `canonical/M5_FORMAL_QUALIFICATION_AUTHORITY.json` v1.0.0, SHA-256 `e3dd1fafa9c65d6c9a85dfb7172d60adef3e9c17893e3b546b962275c42c01b1` (#136)
- Added M6 P2 C3 authority: `canonical/P2_ATTRIBUTION_NORMALIZATION_AUTHORITY.json` v1.0.0, SHA-256 `1bfc6c9eb8e2142249c327af5698bc6a8925f983fd8363b1d2bd835966eea5fa` (#151)

The M6 P2 authority freezes implementation-level factor/reference/cohort identity, attribution-spec/plugin binding, identifiability, uncertainty, leakage, DTO, Release and replay semantics on existing DB schema 1.6.0. P2 subtypes use existing ASSESSMENT_PROFILE / REFERENCE_SET artifact kinds plus exact logical-key prefix and artifact schema; no DB enum or shadow schema is added. It adds no attribution algorithm or threshold. Adoption of this authority does not admit P2; protected-main M6 Exit GO remains mandatory.
