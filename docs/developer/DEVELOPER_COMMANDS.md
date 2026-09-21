# TPAA Developer Command Contract

**Controlling baseline:** SDIB-1.0 Appendix I  
**Dispatcher:** `python tools/dev/tpaa_dev.py <command>`

The Python dispatcher is the cross-platform semantic entry point. Windows and Linux may use different shell launchers later, but they must invoke the same dispatcher semantics and produce equivalent evidence.

Run `python tools/dev/tpaa_dev.py list` to discover every governed command and its current implementation state.

## Implemented

- `bootstrap` — validate CPython 3.13, `uv.lock`, CB-1.4.0 and optionally sync the frozen environment.
- `verify-baseline` — M0-CORE-001 exact baseline verification.
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

Quality commands use an already-installed exact tool version when available. Otherwise they invoke `uv tool run --from <tool>==<frozen-version>`, so local and CI semantics do not silently float to `latest`.

## Reserved and fail-closed

`run`/`run-api`/`run-gui`, `package`, `manifest`, and `cold-start` are intentionally discoverable now but exit with `NOT_IMPLEMENTED` until their controlling SDIB tasks are implemented. A placeholder command must never report success for a capability that does not yet exist.

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
