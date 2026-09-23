# M0-PLAT-004 / M0-PLAT-005 — Cross-platform CI

- **Status:** IN-PROGRESS — repository implementation and locally available verification complete; exact-tool/PySide6 hosted-runner evidence is still required before completion.
- **Workstream:** WS-PLATFORM
- **Authority:** SDIB-1.0 §15, §17 (`M0-PLAT-004`, `M0-PLAT-005`), §39 step 8, Appendix F; ADR-M0-001/002/003; current completed M0 gate contracts.
- **Starting commit:** `46f6e7db2245e4c3cf5f7c98f96b40c487743026`

## Formal acceptance target

`M0-PLAT-004` requires a real Windows CI runner executing unit/contract/bootstrap/API/GUI smoke. `M0-PLAT-005` requires Linux CI to execute the same logical test set. SDIB §15 additionally requires baseline/generated/static-quality/architecture coverage as the corresponding implementations become available. The current M0-GUI-004 automation gate must remain in the matrix.

## Implementation

1. `.github/workflows/cross-platform-ci.yml` runs an explicit x64 matrix on `windows-2025` and `ubuntu-24.04`; macOS is not added because it is not part of the M0 authority.
2. Both jobs use exact CPython `3.13.5`, exact uv `0.12.17`, the single committed `uv.lock`, `uv sync --locked`, and `uv lock --check`.
3. GitHub Actions are pinned to immutable full commit SHAs. No `@main`, `continue-on-error`, or shell failure masking is used.
4. `python tools/dev/tpaa_dev.py verify-ci` validates the provider orchestration contract locally and on both runners.
5. `python tools/dev/tpaa_dev.py ci-check` is the unified platform-neutral Gate aggregator. Both OS jobs call the same command with only the expected platform identity changed.
6. The aggregate Gate covers current baseline/canonical/codegen/generated-source/architecture/repository-policy/desktop-lifecycle/static-quality/unit/contract/migration/SQLite bootstrap+repository/API/Desktop/UI automation/lock/Git-diff checks.
7. The Gate emits `TPAA_M0_CROSS_PLATFORM_CI_EVIDENCE_V1` JSON and the workflow uploads one evidence artifact per OS even when a required Gate fails. Artifact upload does not make a failed required Gate non-blocking.

## Local checkpoint verification

The current construction host is CPython 3.13.5 with uv 0.10.0 (within the frozen `>=0.10,<0.13` resolver range), but it does not have governed PySide6, Ruff, or mypy installed and has no package-download path. Therefore local evidence is deliberately split from hosted-runner evidence:

- unit: **96/96 PASS**;
- migration: **26/26 PASS**;
- contract: **110/110 PASS** when the known subprocess-heavy contract set is run in controlled partitions; an aggregate invocation exceeded the chat execution timeout and was not used as a false failure;
- total regression: **232/232 PASS** (unit 96 + migration 26 + contract 110);
- `verify-ci`: PASS;
- baseline/canonical/generate-check/verify-generated/regenerate-diff/architecture/Repository-policy/Desktop-lifecycle-policy/bootstrap-check/SQLite bootstrap+verify/SQLite Repository/API smoke/Desktop-backend smoke/offline lock/diff-check: PASS;
- local `gui-smoke --headless` and `ui-automation-smoke`: **not executable on this host** because PySide6 is absent; the hosted jobs install the frozen project lock before running them;
- local Ruff 0.16.8 and mypy 2.3.1: **not executable on this host** because those exact tools are absent and network fetch is unavailable; the hosted jobs acquire the exact frozen versions through the governed dispatcher.

No unavailable local gate is recorded as PASS. The checkpoint remains IN-PROGRESS until the real Windows and Linux jobs execute all required gates.

## First hosted-runner attempt and remediation

The first real GitHub Actions run against checkpoint `065affd1bf465bd07a153034d192ba73472a6a0c` correctly failed closed and produced actionable Windows/Linux evidence instead of being treated as completion:

- both runners reached and passed the CI orchestration, baseline, bootstrap, Canonical, generated-source, architecture, Repository-policy, and Desktop-lifecycle preflight gates;
- Ruff 0.16.8 exposed 75 pre-existing static-quality findings that could not have been observed on the package-isolated construction host; the repair normalizes those findings without weakening the frozen Ruff policy, including generator templates so generated output remains governed;
- mypy 2.3.1 stopped at duplicate namespace-module discovery for `tools/api/smoke.py` and `tools/gui/smoke.py`; `explicit_package_bases = true` now gives the repository namespace an unambiguous module root without excluding either file;
- hosted pytest could not import the repository-local `tools` namespace because only `src` was on the governed pytest path; the root path is now explicitly included together with `src`;
- Linux PySide6 import failed on missing `libEGL.so.1`; the Linux matrix branch now installs the minimal Ubuntu `libegl1` runtime package before executing the unchanged offscreen/headless GUI gates. Windows GUI and UI-automation smoke already passed in that first hosted attempt.

The CI verifier and contract tests now fail closed if the Linux EGL preparation or the pytest/mypy namespace configuration is removed. These repairs remain IN-PROGRESS until a new real hosted Windows/Linux run proves the exact Ruff/mypy/test/GUI gates on the amended commit.

## PostgreSQL boundary

M0-STO-003 already owns and completed real PostgreSQL 16 repository acceptance. SDIB §39 step 8 and the existing M0-PLAT task minimum do not explicitly require redefining that acceptance as a per-OS live PostgreSQL service Gate. This CI stage therefore preserves the completed PostgreSQL contract/migration coverage but does not invent a new Windows/Linux PostgreSQL-version policy. If a later authority requires live PostgreSQL in every runner, that change must be made explicitly rather than silently using different runner-provided majors.

## Deliberate non-scope

- packaging / installer;
- SBOM / license report;
- build manifest;
- cold-start job;
- M0 Exit Gate;
- step-9 complete test/fixture harness, Golden/replay, or cross-platform logical-equivalence report;
- release publishing/signing;
- M1 work.

## Completion discipline

The repository implementation is not `COMPLETE` until a real GitHub Actions run for the checkpoint commit provides GREEN evidence from both the Windows and Linux matrix jobs. Local Linux success, YAML parsing, or prior Windows workstation smoke results are not substitutes for hosted-runner evidence.
