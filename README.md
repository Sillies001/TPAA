# TPAA Software Repository

TPAA V8.0 / ED-2.0 implementation monorepo governed by the frozen Canonical business baseline and the adopted SDIB implementation baseline. Machine-readable Canonical artifacts remain the business authority; implementation documents and code may consume that authority but do not redefine it.

## Current implementation state

- Overall design input: **TPAA V8.0 / ED-2.0 Rebaseline R3.3**.
- Machine business authority: **CB-1.4.0** under `baseline/CB-1.4.0/`.
- Adopted implementation baseline: **SDIB-1.4**. See `docs/reviews/SDIB-1.4_ADOPTION_REVIEW.md`.
- Database schema authority remains exactly **1.6.0**; no shadow schema is admitted.
- M5 contains exactly **23 tasks** and remains **P1-only**; P2-P6 are inactive.
- M5 formal qualification authority is `M5_FORMAL_QUALIFICATION_AUTHORITY` v1.0.0, SHA-256 `e3dd1fafa9c65d6c9a85dfb7172d60adef3e9c17893e3b546b962275c42c01b1`. See `docs/reviews/M5_C3_FORMAL_QUALIFICATION_AUTHORITY_REVIEW.md`.
- Protected-main M5 Exit is **GO** at `68767397c028f7aa6ad3a22a49302710481951c6`; Cross-platform CI Run #470 / `36549239360` passed all 14 required jobs.
- Formal qualification at that protected-main revision is **P1_M5_QUALIFIED**. The four mandatory certification profiles, package/performance/security gates, recovery/rollback evidence, cold reconstruction, and exact-release signoff contract are all part of the M5 qualification boundary.
- No M6 scope and no P2-P6 capability is implied by the M5 qualification state.

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

M0-M5 implementation sequencing has completed through the protected-main M5 Exit GO revision above. Any subsequent implementation work must come from an explicitly adopted authority/baseline or tracked corrective scope; do not infer a new milestone, activate P2-P6, change DB schema 1.6.0, or redefine frozen Canonical/M5 qualification semantics from this README.

