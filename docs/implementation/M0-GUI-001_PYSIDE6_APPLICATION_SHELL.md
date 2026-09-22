# M0-GUI-001 — PySide6 application shell

Status: **IN PROGRESS**

## Objective

Establish the native Desktop process/UI shell required by SDIB-1.0 §17/§39 without implementing the local FastAPI backend lifecycle owned by M0-GUI-002.

## Frozen dependency target

M0-GUI-001 owns governed activation of:

```text
PySide6==6.11.2
```

Qt for Python documents Python 3.13 support from PySide6 6.8.1 onward. The exact 6.11.2 lock must be produced by `uv` and shared by Windows/Linux; this checkpoint does not claim activation because the isolated Chat execution host cannot resolve/download PySide6.

## Implemented shell slice

- `tpaa_gui` is a transport/UI package only.
- Qt is loaded lazily at the concrete GUI adapter edge so non-GUI governance tooling remains importable without Qt installed.
- Missing PySide6 fails deterministically as `PYSIDE6_DEPENDENCY_MISSING`.
- The shell creates one `QApplication` and one `QMainWindow` with stable object names.
- `run-gui` and `run gui` dispatch the native shell.
- `gui-smoke --headless` creates the shell, enters the Qt event loop and requests deterministic controlled exit using `QTimer`.
- `auto_close_ms` exists only for smoke automation; normal GUI execution does not auto-close.

## Explicit non-scope

M0-GUI-001 does **not**:

- spawn or attach to the local FastAPI backend;
- generate or transfer bearer tokens;
- allocate/listen on loopback ports;
- perform `/readiness` or `/version` handshake;
- own crash recovery or shutdown escalation;
- import Storage/Canonical/Repository implementation packages.

Those behaviors remain M0-GUI-002 under ADR-M0-005.

## Completion gates still outstanding

The SDIB minimum acceptance is Windows/Linux startup-exit smoke PASS. Completion therefore requires:

1. `uv add "PySide6==6.11.2"` with a governed single `uv.lock` and no machine-specific package-index policy committed;
2. `uv run python -c "import PySide6; print(PySide6.__version__)"` = `6.11.2`;
3. `uv run python tools/dev/tpaa_dev.py gui-smoke --headless` PASS on Windows;
4. the same smoke PASS on Linux;
5. final repository regression and historical governance gates PASS.

Until those platform gates are evidenced, this task remains **IN PROGRESS**.
