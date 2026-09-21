# TPAA Software Repository

TPAA V8.0 / ED-2.0 implementation monorepo bootstrapped from **SDIB-1.0**.

## Current implementation state

- Milestone: **M0 Engineering Bootstrap**
- Completed tasks:
  - **M0-CORE-001** — import and lock CB-1.4.0 baseline snapshot
  - **M0-DEV-001** — unified developer command semantics
  - **M0-DEV-002** — one cross-platform project dependency lock
- Closed toolchain decisions:
  - **ADR-M0-001** — CPython 3.13.x runtime baseline
  - **ADR-M0-002** — uv + single `uv.lock`
  - **ADR-M0-003** — Ruff + mypy + pytest quality toolchain
- Capability claim: **none**. M0 does not admit P1 or any later Capability Phase.
- DB schema target inherited from the baseline: **1.6.0**

## Machine authority rule

Business schemas, DTO contracts, Stage definitions, Metric definitions, P/M/WS vocabularies, and related governed semantics are consumed from the frozen machine-readable Canonical snapshot under `baseline/CB-1.4.0/`. Markdown files are explanatory/implementation references and are not a second schema authority.

## Toolchain baseline

TPAA currently requires **CPython 3.13.x**. The project dependency resolver is **uv** and `uv.lock` is the only project dependency lock. Separate Windows/Linux Python lockfiles are forbidden.

The current project lock deliberately contains no third-party runtime package yet: the completed bootstrap and baseline verifier are standard-library-only. Runtime libraries enter `pyproject.toml` and `uv.lock` only when an admitted implementation task actually uses them.

For airborne-data processing and metric calculation, **Polars is the default DataFrame/query engine**. Pandas is not a default dependency. See `docs/developer/DATAFRAME_POLICY.md`.

## Unified developer commands

```bash
python tools/dev/tpaa_dev.py list
python tools/dev/tpaa_dev.py bootstrap --check-only
python tools/dev/tpaa_dev.py verify-baseline
python tools/dev/tpaa_dev.py test-contract
python tools/dev/tpaa_dev.py doctor
```

The command dispatcher deliberately reserves future command names such as `generate`, `run-api`, `run-gui`, `package`, `manifest`, and `cold-start`, but those commands fail closed with `NOT_IMPLEMENTED` until their controlling SDIB work items exist.

## Verify the frozen baseline

```bash
python tools/baseline/verify_baseline.py
```

A successful run verifies the pinned `BASELINE_LOCK.json` hash, all 21 controlled artifact byte sizes and SHA-256 digests, and rejects missing or unlisted Canonical JSON artifacts.

## Verify the M0 toolchain decisions

```bash
python tools/dev/verify_toolchain.py \
  --evidence evidence/generated/M0-DEV-001-002_ADR-M0-001-003.json
```

This checks the Python minor, resolver/lock authority, frozen static-tool pins, developer command discovery, Polars-first policy and ADR closure evidence.

## Repository sequencing

The SDIB-1.0 startup sequence through step 4 is now complete. The next implementation item is **M0-CORE-002 — Canonical artifact loader**, followed by **M0-CORE-003 — code generator framework**.
