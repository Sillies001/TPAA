# Canonical Artifact Loader Contract — M0-CORE-002

## Purpose

`src/tpaa_canonical/loader.py` is the single implementation entry point for consuming the frozen Canonical snapshot during M0. It does not redefine TPAA business schemas. Canonical JSON remains the machine authority; `BASELINE_LOCK.json` remains the byte/hash authority for the approved snapshot.

## Trust boundary

The loader fails closed unless all of the following hold:

1. `BASELINE_LOCK.json` matches the repository-pinned SHA-256 for CB-1.4.0.
2. The lock identifies the expected Core baseline and exactly 21 controlled artifacts.
3. Only lock-listed JSON artifacts are addressable.
4. The selected artifact byte count and SHA-256 match the lock before its JSON payload is trusted.
5. The payload is a JSON object and declared envelope fields have valid string types.
6. A declared `core_baseline` matches CB-1.4.0.
7. A declared `db_schema_version` matches the baseline lock DB schema target.
8. Any consumer-requested artifact version, schema version, or top-level structural requirement matches exactly.

## Version model

The current Canonical set does not use one universal artifact-version field. The loader recognizes authority-declared `version`, `catalog_version`, and `matrix_version`. Artifacts with no independent artifact version remain explicitly `UNVERSIONED_BY_AUTHORITY`; the implementation does not invent one from a filename, date, or hash.

A consumer that only supports a specific version uses `ArtifactExpectation`. This keeps implementation compatibility separate from Canonical authority and allows an approved future baseline to change versions without silently redefining the current snapshot.

## Schema model

M0-CORE-002 does not invent JSON Schema documents that are absent from CB-1.4.0. It validates the common Canonical envelope, the baseline DB schema declaration when present, and consumer-required top-level keys. Domain-specific DTO/Metric/Stage projections will be generated from the machine authorities by M0-CORE-003 rather than hand-copied into the loader.

## Error contract

`CanonicalArtifactError` always renders deterministic engineering context containing:

- `reason`
- `artifact_id`
- expected/actual artifact version context
- expected/actual schema version context
- failure detail

These reason strings are engineering diagnostics only; they are not TPAA Metric/business-status reason codes.

For byte/hash failure, the loader deliberately does not parse the untrusted payload to recover an apparent version; it reports `UNTRUSTED_NOT_PARSED`.

## Verification

```bash
python tools/dev/tpaa_dev.py verify-canonical
python tools/dev/tpaa_dev.py test-unit
python tools/dev/tpaa_dev.py test-contract
```

`tools/canonical/verify_loader.py` emits machine-readable M0 gate evidence and exercises both the 21-artifact success path and fail-closed negative contracts.
