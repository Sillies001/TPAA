# M0-GUI-004 — UI automation smoke harness

Status: **COMPLETE**

**Authority:** SDIB-1.0 §17 and §39 step 7  
**Minimum acceptance:** Desktop launch, READY, and close are automatically verifiable.

## Implementation

The governed command is:

```text
python tools/dev/tpaa_dev.py ui-automation-smoke
```

The harness uses the existing PySide6 6.11.2 runtime and the real composed Desktop path. It does not introduce a second UI framework or a new dependency. In offscreen mode it:

1. creates a real `QApplication`;
2. launches the composed Desktop runtime and its owned local backend child;
3. locates `tpaaMainWindow` through Qt's object tree;
4. waits for the authoritative diagnostics label `tpaaDiagnosticsReadiness` to show `Readiness: READY`;
5. verifies the frozen diagnostics object names are present and visible;
6. closes the real main window through Qt;
7. waits for `run_desktop()` to return and verifies the backend state is `EXITED`, not ready, and has no bound port.

The harness consumes GUI diagnostics and lifecycle state only. It does not evaluate Core baseline identity, duplicate mismatch constants, inspect the bearer token, or bypass M0-GUI-002 lifecycle ownership.

## Evidence status

M0-GUI-004 is **COMPLETE**. Governed Windows acceptance used CPython 3.13.5 and the unchanged 46-package lock via `uv sync --locked`; the unified `ui-automation-smoke` command executed the real PySide6 6.11.2 composed Desktop and reported PASS for `launch`, `backend_ready`, `diagnostics_visible`, `close`, and `backend_cleanup`. `uv lock --check` passed and `git status --short` remained empty after the run. The Qt headless font-directory and `propagateSizeHints()` messages were warnings only; the governed smoke exited successfully with status PASS.

Final repository validation is **220/220 PASS**: unit 93/93, migration 26/26, contract 101/101. Historical Baseline/Canonical/codegen/generated/regenerate-diff/architecture/Repository-policy/Desktop-lifecycle-policy/bootstrap/API-smoke/Desktop-backend-smoke/offline-lock gates PASS. SDIB §39 step 8 cross-platform CI is not claimed by this task.

## Explicit non-scope

- Cross-platform CI configuration and runner admission (SDIB §39 step 8).
- Packaging, build manifest/SBOM, and cold-start completion.
- Pixel/image comparison or full application workflow automation.
- Reimplementation of READY/mismatch semantics in the GUI harness.
