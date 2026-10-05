# TPAA Software Repository

TPAA V8.0 / ED-2.0 implementation monorepo governed by the frozen Canonical business baseline and the adopted SDIB implementation baseline. Machine-readable Canonical artifacts remain the business authority; implementation documents and code may consume that authority but do not redefine it.

## Current implementation state

- Overall design input: **TPAA V8.0 / ED-2.0 Rebaseline R3.3**.
- Machine business authority remains **CB-1.4.0** under `baseline/CB-1.4.0/`.
- Product integration/qualification authority is **PIQB-1.0**; B0-B6 are formally protected-main qualified and PIQB-1.0 is complete.
- Product version is **1.0.0**.
- Current physical database schema authority is **1.9.0**, adopted through ACP-216 -> ACP-219 -> ACP-221; historical M0-M9/M5 evidence that records 1.6.0 remains immutable historical evidence rather than current authority.
- P1-P6 capability qualification from M5-M9 is retained. PIQB does not create M10 or P7.
- B6 / PIQB Exit protected-main qualification is **PIQB_1_0_QUALIFIED** at `8f2581f2c990531eaecb49f9dc5826885e0c18a4`; Run #634 / `37265802397` passed all 14 required jobs.
- `TPAA_PIQB_EXIT_REVIEW_V1` returned **PASS / GO**, `failed_acceptance=[]`, and formally qualified Windows/Linux Desktop+Service release profiles with P1-P6 unified product scope.
- Exact-head Hosted CI remains the only merge/formal-release authority.

## Machine authority rule

Business schemas, DTO contracts, Stage definitions, Metric definitions, P/M/WS vocabularies, and related governed semantics are consumed from the frozen machine-readable Canonical snapshot under `baseline/CB-1.4.0/`. Markdown files are explanatory or implementation references and are not a second schema authority.

## Toolchain baseline

TPAA requires **CPython 3.13.x**. The project dependency resolver is **uv**, and `uv.lock` is the project dependency lock; separate Windows/Linux Python lockfiles are forbidden.

The current runtime dependency set includes the governed FastAPI, Psycopg, and PySide6 packages declared in `pyproject.toml`. For airborne-data processing and metric calculation, **Polars is the preferred DataFrame/query engine** when an admitted implementation task requires that class of dependency; Pandas is not the default dependency. See `docs/developer/DATAFRAME_POLICY.md`.

## Unified developer commands

The developer dispatcher is the authoritative command index:

```bash
python tools/dev/tpaa_dev.py list
```

Common baseline and development checks include:

```bash
python tools/dev/tpaa_dev.py bootstrap --check-only
python tools/dev/tpaa_dev.py verify-baseline
python tools/dev/tpaa_dev.py verify-canonical
python tools/dev/tpaa_dev.py generate
python tools/dev/tpaa_dev.py generate --check
python tools/dev/tpaa_dev.py verify-generated
python tools/dev/tpaa_dev.py regenerate-diff
python tools/dev/tpaa_dev.py verify-architecture
python tools/dev/tpaa_dev.py test-contract
python tools/dev/tpaa_dev.py doctor
```

The dispatcher has expanded with admitted M1-M5 verification and qualification commands. Use `python tools/dev/tpaa_dev.py list` rather than relying on an older reserved-command list.

## Verify the frozen baseline

```bash
python tools/baseline/verify_baseline.py
```

A successful run verifies the pinned `BASELINE_LOCK.json`, all controlled artifact byte sizes and SHA-256 digests, and rejects missing or unlisted Canonical JSON artifacts.

## Verify the Canonical artifact loader

```bash
python tools/dev/tpaa_dev.py verify-canonical
```

The loader accepts only `BASELINE_LOCK`-controlled artifacts, verifies exact bytes/hash before trusting JSON, checks declared Core/DB-schema compatibility, and supports explicit consumer version/schema expectations. Artifacts that do not declare an independent authority version remain explicitly unversioned rather than receiving an implementation-invented version. See `docs/developer/CANONICAL_LOADER.md`.

## Verify the M0 toolchain decisions

```bash
python tools/dev/verify_toolchain.py \
  --evidence evidence/generated/M0-DEV-001-002_ADR-M0-001-003.json
```

This checks the Python minor, resolver/lock authority, frozen static-tool pins, developer command discovery, Polars-first policy, and ADR closure evidence.

## Repository sequencing

M0-M9 and P1-P6 capability implementation are complete inputs to PIQB-1.0. PIQB B0-B6 are formally qualified, and PIQB-1.0 reached protected-main final-product qualification at Run #634. The qualified product preserves the frozen Canonical semantics, current DB 1.9.0 authority, exact-release history, fail-closed security/recovery rules, and the existing 14 required Hosted CI checks. PIQB completion does not imply M10 or P7.

