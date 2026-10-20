# TPAA Developer Command Contract

**Controlling baseline:** SDIB-1.0 Appendix I  
**Dispatcher:** `python tools/dev/tpaa_dev.py <command>`

The Python dispatcher is the cross-platform semantic entry point. Windows and Linux may use different shell launchers later, but they must invoke the same dispatcher semantics and produce equivalent evidence.

Run `python tools/dev/tpaa_dev.py list` to discover every governed command and its current implementation state.

## Implemented

- `bootstrap` — validate CPython 3.13, `uv.lock`, CB-1.4.0 and optionally sync the frozen environment.
- `verify-baseline` — M0-CORE-001 exact baseline verification.
- `authority-diff` — W0-A deterministic comparison of two authority roots; the report is explicitly non-adopting.
- `verify-authority-consistency` — W0-B Core/DB/DTO/hash closure check with a separate `REVIEW_REQUIRED` state for historical schema compatibility awaiting approval.
- `verify-w0-successor` — W0-D/E deterministic reconstruction check for the approved local CB-1.5.0 successor package.
- `verify-canonical` — M0-CORE-002 Canonical loader verification.
- `generate` / `generate --check` — M0-CORE-003 deterministic generation and exact-tree check.
- `verify-generated` — M0-CORE-004 non-destructive generated-tree/provenance verification.
- `regenerate-diff` — M0-CORE-004 CI-vendor-neutral regenerate→Git-diff gate.
- `verify-architecture` — M0-CORE-005 SDIB package/layer dependency gate.
- `format` — frozen Ruff formatter entry point.
- `lint` — frozen Ruff linter entry point.
- `typecheck` — frozen mypy entry point.
- `test` plus the SDIB test-family commands — frozen pytest entry points.
- `doctor` — machine-readable report of runtime/resolver/lock/quality-tool availability.

Quality commands use an already-installed exact tool version when available. Otherwise they invoke `uv run --locked --with <tool>==<frozen-version> <tool> ...`, so the exact quality tool is overlaid onto the locked project environment rather than running in an isolated tool environment or silently floating to `latest`.

`authority-diff --reference-root <path> --candidate-root <path>` emits stable
hash/size/metadata plus table, field, CHECK/enum, index-declaration, DTO and API
transport/route summaries. A missing index or API-route authority is reported
explicitly rather than silently treated as unchanged. The command never changes
a lock or reports adoption. `verify-authority-consistency` returns `3` for `REVIEW_REQUIRED` when
the current physical Core/DB authority is internally valid but older semantic
artifacts still need an approved compatibility declaration. Use
`--report-only --json` for inventory/report generation without weakening the
status carried in the JSON payload.

`verify-w0-successor` reconstructs CB-1.5.0 from its immutable CB-1.4.0
predecessor plus the approved W0 decision, compatibility, index and API-route
rules, then compares the complete directory digest. It verifies local approval
integrity only and never pushes or deploys the baseline.

## Runtime commands

`run gui` and `run-gui` start the Desktop shell and its owned local backend.
`run api` and `run-api` start the durable Service composition and accept
`--host`/`--port`. The dispatcher supplies the source `PYTHONPATH`, so these
commands work before an editable installation.

Desktop composition has one public owner: `tpaa_desktop.create_runtime()` and
`tpaa_desktop.create_app()`. The installed `tpaa-desktop` script uses
`tpaa_desktop.__main__`; `python -m tpaa_gui` is only a compatibility delegate
to that same entry point. PIQB packaging code must not construct production
runtimes directly.

Both Service forms also accept `--check-config`, which composes the same
production runtime, runs live readiness checks, emits secret-free JSON, and
exits without opening a listening socket.

The Service entry remains fail-closed: PostgreSQL, object-root, principal, and
Canonical authority configuration must be valid before it binds a socket. See
`docs/operator/PRODUCTION_ENTRYPOINTS.md` for the required environment.

`package`, `manifest`, and `cold-start` retain their separately governed
implementation state shown by `tpaa_dev.py list --json`. A placeholder command
must never report success for a capability that does not exist.

`api-smoke` remains the M0-API-002 acceptance entry point for the FastAPI
health/readiness/version adapter.

## Bootstrap modes

`bootstrap --check-only` verifies runtime, resolver/lock consistency and the frozen Canonical baseline without changing `.venv`.

Plain `bootstrap` additionally executes `uv sync --frozen --offline`; this guarantees the local environment is derived from the committed lock and never silently updates it.

`bootstrap --with-quality-tools` also requires the exact Ruff/mypy/pytest versions in `tools/dev/TOOLCHAIN.json`. On a new machine those tools may need network access or a pre-populated uv cache.

## Generated-source governance

`verify-generated` never rewrites the worktree. It builds expected bytes in memory and verifies exact inventory, bytes and provenance under `src/tpaa_generated/`.

`regenerate-diff` is the mandatory CI-compatible gate for M0-CORE-004. It refuses pre-existing uncommitted generated-tree changes, regenerates through the approved generator coordinator, verifies the governed tree, then requires `git diff --exit-code -- src/tpaa_generated`. CI providers must call this command rather than duplicating generator logic.

## Architecture dependency gate

`verify-architecture` scans `src/` with the standard-library AST and evaluates imports against the
SDIB-derived machine-readable policy. The same command is the required local/later-CI entry point;
CI providers must not maintain a second dependency-rule implementation. See
`docs/developer/ARCHITECTURE_DEPENDENCIES.md`.

## Cross-platform CI

`verify-ci` is the M0-PLAT-004/M0-PLAT-005 provider-orchestration verifier. It checks that the GitHub Actions workflow uses real Windows and Linux x64 runners, exact CPython/uv versions, immutable action commit pins, fail-closed required gates, and the unified dispatcher rather than duplicating application logic in YAML.

`ci-check --expected-platform <windows|linux> --evidence <path>` is the platform-neutral required Gate aggregator for SDIB §39 step 8. It executes the currently implemented M0 baseline/codegen/architecture/storage/API/Desktop/test gates on either OS and emits machine-readable runner evidence. It deliberately excludes later packaging, SBOM, build-manifest, cold-start, M0 Exit, and the step-9 Golden/replay/logical-equivalence harness.

The GitHub workflow first installs project dependencies with `uv sync --locked`, verifies `uv lock --check`, and then invokes these dispatcher commands. Ruff/mypy/pytest remain governed by ADR-M0-003 and `tools/dev/TOOLCHAIN.json`; the CI runner must obtain those exact tools rather than floating to latest versions.
