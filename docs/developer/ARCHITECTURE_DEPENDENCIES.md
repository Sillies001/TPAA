# Architecture Dependency Gate

**Controlling task:** M0-CORE-005
**Authority:** SDIB-1.0 §7.1 and Appendix E

Run:

```bash
python tools/dev/tpaa_dev.py verify-architecture
```

The gate is standard-library-only and scans Python source under `src/` using the AST. It checks
static imports plus literal `importlib.import_module(...)` / `__import__(...)` calls against
`tools/architecture/ARCHITECTURE_POLICY.json`.

The minimum M0-CORE-005 rules are fail-closed:

- governed lower layers may not import `tpaa_gui` or `tpaa_api`;
- governed business-core packages may not import `tpaa_platform` implementation directly.

The policy also encodes concrete import-level restrictions from Appendix E, including selected
reverse domain edges and framework/DB-driver leakage. `tpaa_generated` is constrained to Python
stdlib/self imports at M0.

First-party package identity comes from the executable policy as well as discovered source
packages. A prohibited package does not become "external" merely because its directory has not yet
been created in a partial checkout or fixture.

The command emits machine-readable evidence including the policy SHA-256, scanned-file/import
counts, deterministic violation records and explicit semantic constraints that an import scanner
cannot prove.

This gate does **not** claim to detect business behavior from imports alone. Examples deliberately
left to focused semantic/contract tests include Metric `current/latest` shortcuts and Observation
recomputation behavior.
