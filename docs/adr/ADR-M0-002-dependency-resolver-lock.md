# ADR-M0-002 — Dependency Resolver and Lock

- **Status:** CLOSED
- **Decision date:** 2026-09-21
- **Owner role:** WS-DEVOPS technical lead
- **Milestone:** M0 Engineering Bootstrap
- **Authority:** SDIB-1.0 §9, §15, §17, Appendix P, Appendix I

## Decision

TPAA uses **uv** as the single Python project dependency resolver and **`uv.lock`** as the only canonical project dependency lock.

1. `pyproject.toml` is the human-reviewed dependency declaration.
2. `uv.lock` is the exact resolver output and a release/build input.
3. The lock is universal/cross-platform; TPAA does not maintain separate Windows and Linux Python lockfiles.
4. Developer/CI install semantics are `uv sync --frozen`; commands that merely validate use `uv lock --check` and must not rewrite the lock.
5. A dependency change must update `pyproject.toml` and `uv.lock` together and rerun the affected unit/contract/Golden/replay/cross-platform gates required by SDIB Appendix P.
6. `requirements.txt`, `poetry.lock`, `Pipfile.lock`, Conda environment locks, or per-OS Python lockfiles are forbidden as competing dependency authorities unless this ADR is reopened.
7. The bootstrap compatibility band for the resolver is `uv >=0.10,<0.13`. An uv upgrade is acceptable only when `uv lock --check` succeeds and the committed lock remains unchanged, or when a deliberate lock change is reviewed as a dependency/toolchain change.

## Current lock scope

At this construction increment the project has **no admitted third-party runtime packages yet**, so the valid `uv.lock` contains only the virtual TPAA project and the Python 3.13 constraint. This is intentional: M0-CORE-001 and the developer dispatcher are standard-library-only, and future subsystem dependencies should enter the lock when their controlling task is implemented rather than as unused speculative dependencies.

Static quality tools are separately frozen in `tools/dev/TOOLCHAIN.json` because they are developer executables, not TPAA product runtime dependencies.

For airborne-data metric/dataframe implementation, `docs/developer/DATAFRAME_POLICY.md` freezes **Polars-first** as the engineering policy. The first admitted task that actually needs a DataFrame engine will add Polars to `pyproject.toml` and regenerate `uv.lock`; Pandas is not a default dependency.

## Rationale

uv provides a single project workflow around `pyproject.toml`, produces a cross-platform lockfile, and supports frozen synchronization. This directly fits the SDIB requirement that Windows/Linux share one logical lock and that release provenance record the dependency-lock identity.

## Rejected alternatives

- **Unpinned pip install / `requirements.txt` generated ad hoc:** allows transitive drift and weakens replayability.
- **Separate Windows/Linux lockfiles:** violates the same-logical-lock rule and can hide dependency divergence.
- **Poetry/PDM as a second resolver:** creates two dependency authorities with no demonstrated benefit at M0.
- **Adding future libraries now:** expands the attack/compatibility surface before a task requires them.

## Verification / evidence

- `pyproject.toml`
- `uv.lock`
- `tools/dev/TOOLCHAIN.json`
- `python tools/dev/tpaa_dev.py bootstrap --check-only`
- `uv lock --check --offline` on the current controlled workspace
- contract test `tests/contract/test_m0_dev_toolchain.py`

The lock SHA-256 is emitted into the machine-readable M0 toolchain evidence for every accepted revision.

## Reopen conditions

Reopen if uv cannot represent a mandatory TPAA dependency/platform, a standardized lock format becomes required by packaging/release governance, or a resolver change is needed to preserve reproducible Windows/Linux builds.
