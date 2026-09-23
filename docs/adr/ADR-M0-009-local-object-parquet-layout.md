# ADR-M0-009 — Local Object / Parquet Layout

- **Status:** CLOSED
- **Decision date:** 2026-09-23
- **Owner role:** WS-STORAGE / WS-PLATFORM technical lead
- **Milestone:** M0 Engineering Bootstrap
- **Authority:** SDIB-1.0 §9–§11, §17; Appendix Q; PLATFORM_COMPATIBILITY_REGISTRY
- **Machine policy:** `tools/storage/OBJECT_LAYOUT_POLICY.json`

## Decision

TPAA freezes an **explicit local object root plus logical URI abstraction** for development storage.

1. The logical schemes are `tpaa-object://` and `tpaa-parquet://`. Logical identifiers use forward-slash URI segments regardless of host OS.
2. A logical URI never contains a drive letter, UNC prefix, repository root, home directory, temporary directory, PID, or other absolute local path.
3. The physical root is configuration. Development default is the platform adapter's TPAA user-data root; `TPAA_OBJECT_ROOT` may override it for tests/controlled deployments.
4. Logical URI resolution is confined to the Storage/Platform adapter. Domain/Application layers exchange logical URIs and hashes, not absolute paths.
5. URI segments must be UTF-8/Unicode-safe, may not be `.`/`..`, and may not rely on case-insensitive filesystem behavior. A governed object tree rejects names that collide under Unicode NFC + casefold comparison.
6. Object publication writes job-scoped/staging bytes, closes handles, verifies artifact-byte hash, and uses the platform atomic-replace adapter before an object is considered sealed.
7. Parquet is a storage representation below the logical URI boundary. M0 freezes layout/identity only; it does not activate a Parquet engine or invent M1 schemas.
8. Logical content hashes are computed from governed logical content/URI identity and never from absolute physical path text.

## Rationale

A URI boundary allows the same logical references to survive Windows/Linux path differences and later movement to service/object storage. M0 only needs the abstraction and safety contract; Parquet table semantics belong to later Data/Metric tasks.

## Alternatives considered

- **Persist absolute filesystem paths as identities:** rejected as non-portable and prohibited by the platform registry.
- **Use `file://` as the business identifier:** rejected because it exposes deployment-specific physical location.
- **Activate PyArrow/Polars Parquet writes now:** rejected; M0-STO-004 is an abstraction skeleton, not a data-model delivery.

## Verification / evidence

- `tools/storage/OBJECT_LAYOUT_POLICY.json`
- M0-STO-004 object-store adapter tests
- M0-PLAT-001/003 Unicode/case/path/atomic tests
- logical hash tests proving physical-root independence

## Reopen conditions

Reopen when remote object-store semantics are activated, Parquet partitioning becomes a governed logical contract, or approved deployment profiles require a different physical root/configuration mechanism.
