# CB-1.4.0 Controlled Snapshot

This directory remains the repository Canonical trust root for CB-1.4.0. The original R3.3 controlled artifacts remain byte-identical; governed C3 extensions add explicit semantic/qualification authority without changing DB schema 1.6.0.

- Core baseline: `CB-1.4.0`
- Rebaseline: `R3.8_M6_P2_DTO_EXECUTION_PROFILE`
- DB schema target: `1.6.0`
- Approved candidate `BASELINE_LOCK.json` SHA-256: `f95167aca59dc993ced607e55f21f01080c4e24cc0759bf97482d49654ea182b`
- Controlled artifacts: `26`
- Lock lineage: immediate prior protected-main M6 P2 authority lock `7eafadbb1d47297688595a8a0c48d4836dad13e040f76340ce2c0fa38a5547fa`; prior Batch 1 lock `be54a16d2f33aca73f0686ffe09414045611fa4ad4c452e0e57ca96e460736d8`; M5 C3 lock `e4f6c2bb97c169cc8db9eecfa09c67201510b5fad85e6e59fc2b96532b011db9`; M4 C3 lock `8bc1834502561992e9aef64d73186c7854ef293e4ec57f658b4e9f72828e0cab`; M2 C3 lock `d6ebab2b5402cf81a0b5f73a2da4ed2aaa2d530bc7445c7f6132dcf7fa72224d`
- M2 C3 authority: `canonical/M2_QA_SNS_AUTHORITY.json` v1.0.0, SHA-256 `1f0755836e7ea40b3b69c83dae1b2b636ff80e37d8630c5ce158d5dfccffd5d3` (#106)
- M4 C3 authority: `canonical/M4_LONGITUDINAL_DEBRIEF_AUTHORITY.json` v1.0.0, SHA-256 `c1c073bce8870feceb90bdb6c28172c4c726de6b15fc70208e169336baa59dfa` (#122)
- M5 C3 authority: `canonical/M5_FORMAL_QUALIFICATION_AUTHORITY.json` v1.0.0, SHA-256 `e3dd1fafa9c65d6c9a85dfb7172d60adef3e9c17893e3b546b962275c42c01b1` (#136)
- M6 P2 authority: `canonical/P2_ATTRIBUTION_NORMALIZATION_AUTHORITY.json` v1.0.0, SHA-256 `1bfc6c9eb8e2142249c327af5698bc6a8925f983fd8363b1d2bd835966eea5fa` (#151)
- M6 P2 execution profile: `canonical/P2_LINEAR_REFERENCE_ADJUSTMENT_PROFILE.json` v1.0.0, SHA-256 `202e255bd09349407e0e7cc4d77d8b848df99d84dc00e50e46871eb4f82f0d68` (#161)
- Cross-layer DTO registry SHA-256: `9d94f75031afcbfe2391bed1245c3f8d95f124a6549a8f116aa1efb879ae45b4`

The #161 C3 closes the central P2 DTO projection and freezes one exact deterministic reference-adjustment execution profile. It preserves DB schema 1.6.0, uses existing P2 product tables/context-artifact carriers, introduces no shadow schema, and does not admit P2. Protected-main M6 Exit GO remains mandatory before external P2 claims.
