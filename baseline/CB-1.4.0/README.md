# CB-1.4.0 Controlled Snapshot

This directory remains the repository Canonical trust root for CB-1.4.0. The original R3.3 controlled artifacts are byte-identical to the imported snapshot; C3 Baseline Change #106 adds one explicit M2 QA/SNS semantic-authority artifact and re-approves the lock.

- Core baseline: `CB-1.4.0`
- Rebaseline: `R3.4_M2_QA_SNS_AUTHORITY`
- DB schema target: `1.6.0`
- Approved `BASELINE_LOCK.json` SHA-256: `d6ebab2b5402cf81a0b5f73a2da4ed2aaa2d530bc7445c7f6132dcf7fa72224d`
- Controlled artifacts: `22`
- Added C3 authority: `canonical/M2_QA_SNS_AUTHORITY.json` version `1.0.0`, SHA-256 `1f0755836e7ea40b3b69c83dae1b2b636ff80e37d8630c5ce158d5dfccffd5d3`
- Decision record: GitHub issue #106

The new authority values are delegated C3 decisions, not recovered R3.3 source facts. All pre-existing 21 Canonical artifact bytes remain unchanged. Any later semantic change requires another governed Baseline Change and a new approved lock.
