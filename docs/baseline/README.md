# Implementation baseline index

The current software-development implementation baseline for this repository is
**SDIB-1.1**.

- Current baseline directory: `docs/baseline/SDIB-1.1/`
- Main document SHA-256:
  `ba6cfd3765c53fec7ea322b2ec964ee78f09392d1e6a1e32d9754584b71132fe`
- M2 task baseline SHA-256:
  `733b4180ad6941ca1361e1a5857c802e698ad69351b07cf9c591c80045a63d4b`
- Parent implementation baseline: SDIB-1.0.1
- Source design package: TPAA V8.0 / ED-2.0 Rebaseline R3.3
- C3 authority extension: #106 / R3.4_M2_QA_SNS_AUTHORITY
- Core baseline: CB-1.4.0
- R3.3 source ZIP SHA-256:
  `8030b988a8740fb9fc9003866b449618abc9b7048c77930b6cc22cb85fe926b9`
- BASELINE_LOCK SHA-256:
  `d6ebab2b5402cf81a0b5f73a2da4ed2aaa2d530bc7445c7f6132dcf7fa72224d`

SDIB-1.1 is the post-M1 C1 implementation-contract refinement that freezes M2
`P1 Basic Flight Complete` into a 27-Task, four-batch implementation backlog while
preserving the original CB-1.4.0 imported authorities while allowing governed C3 extensions. The #106 extension adds only `M2_QA_SNS_AUTHORITY.json`; it does not change the 116
P1 metrics, 661 input bindings, Stage/DTO/Core schema authority, DB schema 1.6.0, or
the Catalog-owned M2 delivery set `P1_FOUNDATION_32`.

Historical baselines remain in this directory for auditability; they are not deleted or
silently rewritten when a later implementation baseline is adopted.

See `docs/reviews/SDIB-1.1_ADOPTION_REVIEW.md` for the M1 Exit authority boundary,
M2 refinement rationale, and exact adoption conditions.
