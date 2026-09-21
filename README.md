# TPAA Software Repository

TPAA V8.0 / ED-2.0 implementation monorepo bootstrapped from **SDIB-1.0**.

## Current implementation state

- Milestone: **M0 Engineering Bootstrap**
- Completed task: **M0-CORE-001** — import and lock CB-1.4.0 baseline snapshot
- Capability claim: **none**. M0 does not admit P1 or any later Capability Phase.
- DB schema target inherited from the baseline: **1.6.0**

## Machine authority rule

Business schemas, DTO contracts, Stage definitions, Metric definitions, P/M/WS vocabularies, and related governed semantics are consumed from the frozen machine-readable Canonical snapshot under `baseline/CB-1.4.0/`. Markdown files are explanatory/implementation references and are not a second schema authority.

## Verify the frozen baseline

From the repository root, with a standard Python 3 interpreter:

```bash
python tools/baseline/verify_baseline.py
```

The command is intentionally standard-library-only at M0-CORE-001 so baseline verification does not depend on the dependency resolver/toolchain ADRs that are not yet closed.

To emit review evidence after a Git revision exists:

```bash
python tools/baseline/verify_baseline.py --evidence evidence/generated/M0-CORE-001-baseline-verify.json
```

A successful run verifies the pinned `BASELINE_LOCK.json` hash, all 21 controlled artifact byte sizes and SHA-256 digests, and rejects missing or unlisted Canonical JSON artifacts.

## Repository sequencing

Per SDIB-1.0, the next construction step after M0-CORE-001 is to establish the `pyproject + dependency lock + developer command` skeleton and close ADR-M0-001 through ADR-M0-003 before advancing into Canonical loading/code generation work.
