# ADR-M0-003 — Static Quality Toolchain

- **Status:** CLOSED
- **Decision date:** 2026-09-21
- **Owner role:** WS-DEVOPS / WS-TEST technical lead
- **Milestone:** M0 Engineering Bootstrap
- **Authority:** SDIB-1.0 §9, §17, Appendix F, Appendix I

## Decision

TPAA freezes the following local/CI quality toolchain:

| Role | Tool | Frozen version | Governed command |
| --- | --- | ---: | --- |
| Formatter | Ruff | 0.16.8 | `ruff format` |
| Linter | Ruff | 0.16.8 | `ruff check` |
| Type checker | mypy | 2.3.1 | `mypy` |
| Test runner | pytest | 9.0.2 | `pytest` |

The exact pins are machine-readable in `tools/dev/TOOLCHAIN.json`. `pyproject.toml` contains the shared Ruff/mypy/pytest configuration. Local developers and CI must enter these tools through `tools/dev/tpaa_dev.py`; the dispatcher uses an exact installed version when present or invokes `uv tool run --from <tool>==<version>` so a command never silently follows `latest`.

The initial policy is intentionally strict enough to detect drift without multiplying overlapping tools:

- Ruff owns both formatting and import/code linting.
- mypy is configured for Python 3.13 and strict checking.
- pytest is the single test runner across unit/contract/golden/replay/migration/e2e families.

## Rationale

A single formatter/linter binary avoids Black+isort+flake8 configuration overlap. mypy provides explicit static type checking without coupling Domain code to an IDE. pytest can execute existing `unittest`-style tests while providing the fixtures/markers/reporting needed by later M0/M1 harnesses.

## Rejected alternatives

- **Black + isort + flake8:** more executables and overlapping formatting/import rules without an M0 requirement.
- **No type checker:** insufficient for the generated DTO/registry/repository contracts planned in M0.
- **Multiple test runners by workstream:** would violate the SDIB local/CI command-equivalence objective.
- **Floating tool versions:** makes CI/local differences difficult to reproduce.

## Verification / evidence

- `tools/dev/TOOLCHAIN.json`
- `pyproject.toml`
- `python tools/dev/tpaa_dev.py list`
- `python tools/dev/tpaa_dev.py doctor`
- `python tools/dev/tpaa_dev.py format --check`
- `python tools/dev/tpaa_dev.py lint`
- `python tools/dev/tpaa_dev.py typecheck`
- `python tools/dev/tpaa_dev.py test`

The current execution host may lack pre-cached Ruff/mypy binaries and may be network-isolated. That condition does **not** change the decision state; it is reported by `doctor` and prevents falsely claiming those quality gates passed until the exact frozen binaries are available.

## Reopen conditions

Reopen if a tool cannot support Python 3.13, cannot run on a mandatory Windows/Linux profile, conflicts with generated-source policy, or prevents deterministic local/CI execution.
