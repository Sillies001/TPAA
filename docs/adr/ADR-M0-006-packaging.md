# ADR-M0-006 — Packaging

- **Status:** CLOSED
- **Decision date:** 2026-09-23
- **Owner role:** WS-PLATFORM / WS-DEVOPS technical lead
- **Milestone:** M0 Engineering Bootstrap
- **Authority:** SDIB-1.0 §9, §15.2, §17, §18; Appendix F/H/I; PLATFORM_COMPATIBILITY_REGISTRY
- **Machine policy:** `tools/manifest/PACKAGING_POLICY.json`

## Decision

TPAA freezes the M0 development-package model as **profile-specific source/runtime bundles produced from one source revision and one `uv.lock`**. These are development/pre-release artifacts, not M5 qualified installers.

1. The four governed profile identifiers are `WINDOWS_DESKTOP_X64`, `WINDOWS_SERVICE_X64`, `LINUX_DESKTOP_X64`, and `LINUX_SERVICE_X64`.
2. Windows development bundles use deterministic ZIP archives; Linux development bundles use deterministic `.tar.gz` archives. Archive bytes are platform artifacts and are not logical business identity.
3. Every bundle contains the reviewed source needed by the profile, frozen `uv.lock`, `pyproject.toml`, baseline snapshot/lock, generated projections, launcher metadata, build manifest, SBOM/license/native-dependency skeletons, and a package manifest with hashes.
4. Desktop and Service packages may share source files at M0. Profile metadata controls the acceptance path; source duplication is preferable to inventing an early plugin/package split.
5. Clean-install acceptance extracts into a new directory, synchronizes the frozen environment with `uv sync --locked`, verifies baseline/generated contracts, starts the profile smoke path, and exits cleanly. It must not depend on an existing repository `.venv`.
6. M0 artifacts are explicitly marked `DEVELOPMENT_NOT_M5_QUALIFIED`. MSI/MSIX, signed installers, DEB/RPM, container images, service registration, upgrade/uninstall qualification, and native dependency bundling remain M5 decisions unless a later ADR changes this.
7. Package filenames include product version and certification profile. The source revision, Core/Catalog/schema, dependency lock, package hash, and native dependency manifest live inside the build/package evidence.
8. No package path, extraction root, PID, OS-specific separator, or archive byte hash enters business logical hashes.

## Rationale

The M0 Exit requires clean install/start/stop and reproducible development artifacts, but SDIB explicitly defers formal qualification packaging to M5. A deterministic source/runtime bundle proves the build substrate without prematurely freezing installer technology that depends on deployment operations, signing, and enterprise service-management constraints.

## Alternatives considered

- **Freeze MSI/MSIX + DEB/RPM at M0:** rejected as premature formal-delivery coupling.
- **Container-only Service package:** rejected because Windows Service remains a mandatory profile and M0 does not yet freeze deployment infrastructure.
- **One OS-neutral ZIP for every profile:** rejected; Linux archive conventions and permission metadata are better represented by tar, while logical equivalence remains independent of archive format.
- **Build directly from an untracked developer working tree:** rejected; package evidence must bind to source revision and frozen dependency/baseline inputs.

## Verification / evidence

- `tools/manifest/PACKAGING_POLICY.json`
- M0-DEV-003..006 package/manifest/cold-start implementation
- Windows/Linux package smoke in hosted CI
- build/package manifest and package SHA-256

## Reopen conditions

Reopen before M5 qualification, when signing/installer/service-management requirements are approved, when a mandatory profile cannot consume the frozen bundle model, or when native dependency bundling requires a different package boundary.
