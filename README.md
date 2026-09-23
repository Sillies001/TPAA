# TPAA Software Repository

TPAA V8.0 / ED-2.0 implementation monorepo governed by **SDIB-1.0.1**. The already-published M0 engineering baseline remains a historical SDIB-1.0 acceptance result; SDIB-1.0.1 is a C1 implementation-organization patch and does not change CB-1.4.0 / R3.3 Canonical business authority.

## Current implementation state

- Overall design input: **TPAA V8.0 / ED-2.0 Rebaseline R3.3**.
- Machine business authority: **CB-1.4.0** with the frozen R3.3 Canonical snapshot under `baseline/CB-1.4.0/`.
- Implementation baseline: **SDIB-1.0.1**.
- Historical M0 Exit: **GO**, accepted merged-main revision `ee54e8500381e62a53e1f2352d485ed11892c9d6`.
- Published engineering tag: `M0_IMPLEMENTATION_BASELINE`, verified to peel exactly to the accepted M0 revision above.
- SDIB-1.0.1 adoption audit: the patch adds `M0-DEV-000 Formal Repository Bootstrap` and raises the normative M0 backlog to **48 work packages**.
- Current delta status: strict **48/48 completion is not yet claimed** because the current GitHub `main` is not protected and the repository root does not yet contain `.editorconfig`, both required by `M0-DEV-000`.
- Consequently, under SDIB-1.0.1 §19.1 the current transition state is **M1_NOT_ADMITTED** until the new M0 delta is closed (or a formal M0 Review grants an allowed non-blocking exception) and the M1 Entry Gate is re-reviewed.
- Capability claim: **none beyond the historical M0 engineering substrate**. P1/M1 capability has not started or been admitted.

See `docs/reviews/SDIB-1.0.1_ADOPTION_REVIEW.md` for the adoption/delta review.

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
python tools/dev/tpaa_dev.py verify-canonical
python tools/dev/tpaa_dev.py generate
python tools/dev/tpaa_dev.py generate --check
python tools/dev/tpaa_dev.py verify-generated
python tools/dev/tpaa_dev.py regenerate-diff
python tools/dev/tpaa_dev.py verify-architecture
python tools/dev/tpaa_dev.py test-contract
python tools/dev/tpaa_dev.py doctor
```

The command dispatcher implements `generate` for M0-CORE-003, `verify-generated` / `regenerate-diff` for M0-CORE-004, and `verify-architecture` for M0-CORE-005. Future command names such as `run-api`, `run-gui`, `package`, `manifest`, and `cold-start` remain reserved and fail closed with `NOT_IMPLEMENTED` until their controlling SDIB work items exist.

## Verify the frozen baseline

```bash
python tools/baseline/verify_baseline.py
```

A successful run verifies the pinned `BASELINE_LOCK.json` hash, all 21 controlled artifact byte sizes and SHA-256 digests, and rejects missing or unlisted Canonical JSON artifacts.


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

This checks the Python minor, resolver/lock authority, frozen static-tool pins, developer command discovery, Polars-first policy and ADR closure evidence.

## Repository sequencing

SDIB-1.0.1 §17.1/§17.2 are now the normative M0 construction order, and §19.1–§19.4 are the normative M1 transition/startup order. Do not begin M1 work until the SDIB-1.0.1 M0 delta review is closed and all §19.1 M1 Entry Gate conditions are evidenced PASS.

