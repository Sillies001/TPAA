# ADR-M0-001 — Python Runtime Baseline

- **Status:** CLOSED
- **Decision date:** 2026-09-21
- **Owner role:** WS-PLATFORM / WS-DEVOPS technical lead
- **Milestone:** M0 Engineering Bootstrap
- **Authority:** SDIB-1.0 §9, §15, §17, §39; CB-1.4.0 `PLATFORM_COMPATIBILITY_REGISTRY.json`

## Decision

TPAA freezes **CPython 3.13.x** as the M0/M1 Python runtime baseline.

1. `pyproject.toml` declares `requires-python = ">=3.13,<3.14"`.
2. `.python-version` requests minor `3.13` rather than silently following the machine default.
3. Normal GIL-enabled CPython is the supported build. The experimental free-threaded build is not a mandatory M0/M1 profile.
4. The same Python minor is mandatory for all four governed x64 profiles:
   - `WINDOWS_DESKTOP_X64`
   - `LINUX_DESKTOP_X64`
   - `WINDOWS_SERVICE_X64`
   - `LINUX_SERVICE_X64`
5. For a given controlled CI/release epoch, Windows and Linux should use the same approved 3.13 patch where practicable; the exact patch is recorded in execution evidence. A patch update remains inside this ADR only if it does not change the declared minor and all affected gates are rerun.

## Rationale

Python 3.13 is still in the upstream bugfix/support window and has a security-support horizon to approximately October 2029. It provides a conservative cross-platform base for the native dependency surface expected by TPAA (Qt/PySide6, Polars, database drivers and packaging) while avoiding an unnecessary runtime-minor migration during M0.

The governed platform authority requires Windows and Linux as mandatory OS families and defines four required x64 certification profiles. A single minor therefore minimizes logical-equivalence risk and directly implements the SDIB rule that the two OS families must not use different Python minors as normal operation.

## Rejected alternatives

- **Python 3.14 as M0 baseline:** newer feature line, but no M0 requirement depends on 3.14-specific features. Choosing it now would enlarge the native-dependency qualification surface without functional benefit.
- **Python 3.12:** mature, but already in security-only support by the decision date and therefore provides a shorter active maintenance runway.
- **Different Python minors on Windows/Linux:** explicitly violates SDIB-1.0.
- **Free-threaded CPython as default:** not required by current workload contracts and would create a separate native-extension qualification profile.

## Verification / evidence

Repository evidence:

- `.python-version`
- `pyproject.toml`
- `tools/dev/TOOLCHAIN.json`
- `python tools/dev/tpaa_dev.py bootstrap --check-only`
- contract test `tests/contract/test_m0_dev_toolchain.py`

Governed platform artifact at decision time:

- `PLATFORM_COMPATIBILITY_REGISTRY.json` SHA-256: `d127409485588d80b75c0353725f4042f310d196892fb91005978ea57dbaf106`
- CB-1.4.0 `BASELINE_LOCK.json` SHA-256: `9d96a7eb0ba2b1fb13b11d76943171f773fd42497df74bf79c01928cfa26e7fa`

## Reopen conditions

Reopen this ADR if TPAA needs a different Python minor, free-threaded CPython becomes a mandatory profile, an approved platform cannot run the chosen minor, or a critical dependency requires a conflicting Python baseline.
