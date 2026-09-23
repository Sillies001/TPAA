# ADR-M0-010 — SBOM / License Tooling

- **Status:** CLOSED
- **Decision date:** 2026-09-23
- **Owner role:** WS-DEVOPS / WS-SECURITY technical lead
- **Milestone:** M0 Engineering Bootstrap
- **Authority:** SDIB-1.0 §15.2, §17–§18; Appendix F/H/P/T
- **Machine policy:** `tools/manifest/SBOM_POLICY.json`

## Decision

TPAA freezes a **repository-controlled deterministic SBOM/license generator** driven by the reviewed `uv.lock` plus runtime/platform metadata.

1. The primary SBOM output is CycloneDX JSON, spec version 1.6, with one component record per governed locked third-party package and hashes/versions when available.
2. A separate TPAA license report JSON records package name/version and declared license metadata when available. Missing license metadata is explicit `UNKNOWN_REQUIRES_REVIEW`; the generator does not invent a license.
3. A third-party dependency manifest records the exact `uv.lock` SHA-256 and dependency records used to build the SBOM.
4. A native-dependency manifest is produced per platform/profile for Qt/native wheels/runtime libraries discovered by the packaging smoke. M0 may record names/versions/paths as physical evidence; paths never enter logical product hashes.
5. All outputs are UTF-8 deterministic JSON with schema/version fields and bind to source revision, product version, platform profile, and dependency-lock hash.
6. M0 license output is an engineering inventory skeleton, not legal approval. Any distribution/license clearance decision remains a separate governance review.
7. No credentials, tokens, repository authentication data, package-index credentials, or secret environment/config values may appear in these outputs.
8. The generator is invoked through the unified `manifest`/package path and runs on both Windows and Linux.

## Rationale

The lockfile is already the dependency authority. A repository-owned generator makes the M0 evidence deterministic and reviewable without introducing a second dependency-management tool. CycloneDX is a widely consumable exchange format while a separate license inventory avoids pretending the lock contains legal conclusions it does not carry.

## Alternatives considered

- **Freeze a third-party SBOM CLI immediately:** rejected because it would add another bootstrap dependency before M0 packaging exists.
- **SPDX only:** not rejected for future export, but CycloneDX JSON is the frozen primary M0 output.
- **Treat unknown license as an inferred common license:** rejected; unknown metadata must remain explicit.

## Verification / evidence

- `tools/manifest/SBOM_POLICY.json`
- M0-DEV-003/004 manifest and SBOM generators
- Windows/Linux package artifacts carrying SBOM/license/native-dependency evidence
- secret scanning contract tests

## Reopen conditions

Reopen if enterprise release tooling mandates a different primary format, if legal review requires additional license provenance fields, or if an approved third-party generator replaces the repository implementation with equivalent deterministic evidence.
