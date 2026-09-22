# M0-GUI-004 — UI automation smoke harness

Status: **IN PROGRESS**

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

Code-level validation is **219/219 PASS**: unit 93/93, migration 26/26, contract 100/100. Historical Baseline/Canonical/codegen/generated/regenerate-diff/architecture/Repository-policy/Desktop-lifecycle-policy/bootstrap/API-smoke/Desktop-backend-smoke/offline-lock gates PASS. A real PySide6 execution of the unified `ui-automation-smoke` command is still required before this task may be marked COMPLETE in an environment where the governed 46-package lock can be synchronized. The current Chat sandbox reports the deterministic `PYSIDE6_DEPENDENCY_MISSING` blocker rather than claiming a UI run.

## Explicit non-scope

- Cross-platform CI configuration and runner admission (SDIB §39 step 8).
- Packaging, build manifest/SBOM, and cold-start completion.
- Pixel/image comparison or full application workflow automation.
- Reimplementation of READY/mismatch semantics in the GUI harness.
