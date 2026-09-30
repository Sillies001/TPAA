# CB-1.4.0 Controlled Snapshot

This directory remains the repository Canonical trust root for CB-1.4.0. The original R3.3 controlled artifacts remain byte-identical; governed C3 extensions add explicit semantic/qualification authority without changing DB schema 1.6.0.

- Core baseline: `CB-1.4.0`
- Rebaseline: `R3.9_M7_P3_AUTHORITY_PROFILE`
- DB schema target: `1.6.0`
- Approved candidate `BASELINE_LOCK.json` SHA-256: `0d2f11dc5ee41038a1ef63b8b4157730bd1cd313c7a98faaa286132397b8de47`
- Controlled artifacts: `28`
- Lock lineage: immediate prior protected-main M6 P2 DTO/profile lock `f95167aca59dc993ced607e55f21f01080c4e24cc0759bf97482d49654ea182b`; prior M6 P2 authority lock `7eafadbb1d47297688595a8a0c48d4836dad13e040f76340ce2c0fa38a5547fa`; M5 C3 lock `e4f6c2bb97c169cc8db9eecfa09c67201510b5fad85e6e59fc2b96532b011db9`; M4 C3 lock `8bc1834502561992e9aef64d73186c7854ef293e4ec57f658b4e9f72828e0cab`; M2 C3 lock `d6ebab2b5402cf81a0b5f73a2da4ed2aaa2d530bc7445c7f6132dcf7fa72224d`
- M2 C3 authority: `canonical/M2_QA_SNS_AUTHORITY.json` v1.0.0, SHA-256 `1f0755836e7ea40b3b69c83dae1b2b636ff80e37d8630c5ce158d5dfccffd5d3` (#106)
- M4 C3 authority: `canonical/M4_LONGITUDINAL_DEBRIEF_AUTHORITY.json` v1.0.0, SHA-256 `c1c073bce8870feceb90bdb6c28172c4c726de6b15fc70208e169336baa59dfa` (#122)
- M5 C3 authority: `canonical/M5_FORMAL_QUALIFICATION_AUTHORITY.json` v1.0.0, SHA-256 `e3dd1fafa9c65d6c9a85dfb7172d60adef3e9c17893e3b546b962275c42c01b1` (#136)
- M6 P2 authority: `canonical/P2_ATTRIBUTION_NORMALIZATION_AUTHORITY.json` v1.0.0, SHA-256 `1bfc6c9eb8e2142249c327af5698bc6a8925f983fd8363b1d2bd835966eea5fa` (#151)
- M6 P2 execution profile: `canonical/P2_LINEAR_REFERENCE_ADJUSTMENT_PROFILE.json` v1.0.0, SHA-256 `202e255bd09349407e0e7cc4d77d8b848df99d84dc00e50e46871eb4f82f0d68` (#161)
- M7 P3 authority: `canonical/P3_CAPABILITY_TWIN_AUTHORITY.json` v1.0.0, SHA-256 `76726fc533cde7b0a183a1575cb50276e166081cc37ebe4857ed3324ab913e3b` (#169)
- M7 P3 execution profile: `canonical/P3_REFERENCE_CONDITION_OLS_MAD_LONGITUDINAL_PROFILE.json` v1.0.0, SHA-256 `d66aa780d1c2e31ec664d173a0cdbc355f98c9ff3f751a6949e84f74cdf93876` (#169)
- Cross-layer DTO registry SHA-256: `644370d40e42960144102e6f404b6ee31af9753686b67bb27e47690515898c41`

The #169 M7 C3 candidate extends the same trust root with explicit P3 capability/twin authority, an exact deterministic reference-condition longitudinal execution profile, and eight cross-layer P3 DTOs. It preserves DB schema 1.6.0, retains P1/P2 immutability, introduces no shadow schema, and does not admit P3. Protected-main M7 Exit GO remains mandatory before external P3 claims.
