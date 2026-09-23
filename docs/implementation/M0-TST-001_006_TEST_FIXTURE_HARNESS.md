# M0-TST-001..006 — Test / Fixture Harness

- **Status:** COMPLETE — accepted on merged `main` revision `caf24b1c5c20d18e823012413fede6d0ca860f27`.
- **Workstream:** WS-TEST
- **Authority:** SDIB-1.0 §14, §15.1, §17 (`M0-TST-001`..`M0-TST-006`), §39 step 9,
  Appendix A, Appendix F, Appendix I, Appendix O, Appendix T.
- **Starting revision:** `0c56f064aa033b3f7d467fb36dc0d9a8ce682e56` (Step 8 complete on `main`).
- **Accepted main run:** GitHub Actions Run #18 (`35826990983`).

## M0 scope boundary

Step 9 establishes the verification substrate required before the remaining M0 backlog and before M1.
It does **not** implement M1 Metric algorithms, Basic Flight Stage projection, production Release/Replay,
or the eight M1 synthetic bundles.

Appendix F requires only framework smoke at M0 for Golden and replay. The cross-platform Gate compares
a basic frozen logical product. Production Metric/Stage/Release semantics remain owned by their later
milestone tasks.

## Implemented harness

1. `tests/unit`, `tests/contract`, `tests/golden`, `tests/replay`, `tests/migration`, and
   `tests/e2e` are executable through the same `tools/dev/tpaa_dev.py` dispatcher semantics.
2. `fixtures/golden/M0_BASIC_TRANSPORT_V1` freezes fixture id/version, exact input/expected hashes,
   Context/Stage/Profile refs, one numeric tolerance, invalid/insufficient cases, and replay provenance.
3. The fixture exercises NUMERIC/TEXT/BOOLEAN/STRUCTURED values and a Session Time decimal string beyond
   JavaScript safe-integer range without inventing a production Metric.
4. Missing input, corrupt/hash-drift input, unsupported fixture version, and insufficient payload produce
   deterministic engineering failure classifications.
5. Evidence records source revision, Core/Baseline/schema/Catalog/Stage/DTO authorities,
   dependency-lock hash, platform profile, fixture identity/hash, tolerance and replay source.
6. The lifecycle remains `REVIEWED` / `FRAMEWORK_SMOKE_ONLY`, not falsely
   `APPROVED_GOLDEN`.

## Cross-platform frozen-input closure

Run #12 exposed that Windows/Linux checkout line-ending behavior could produce different raw
`uv.lock` bytes while the first comparator revision did not yet compare that frozen input.
M0-TST-006 was repaired rather than accepting the green jobs at face value:

- governed text checkout is LF-stable on both OS families;
- the platform product carries Core/Baseline/schema/Catalog/Stage/DTO/dependency-lock frozen inputs;
- the logical-equivalence comparator requires exact frozen-input parity before comparing products.

Run #18 on merged `main` proves:

- `M0 windows` = SUCCESS;
- `M0 linux` = SUCCESS;
- `M0 logical equivalence` = SUCCESS;
- source revision = `caf24b1c5c20d18e823012413fede6d0ca860f27`;
- dependency-lock SHA-256 = `302ab51a013c713af6ece61113526eb411f6edf302b70c7a924224701387257e`;
- fixture = `M0_BASIC_TRANSPORT_V1@1.0.0`;
- `mismatches = []`;
- `failure_classification = null`.

## Ticket coverage

- **M0-TST-001:** executable unit/contract/golden/replay/migration/e2e directories and unified runners.
- **M0-TST-002:** Canonical contracts cover Core/DTO/Metric/Stage/P-M-WS authority loading.
- **M0-TST-003:** NUMERIC/TEXT/BOOLEAN/STRUCTURED transport round-trip smoke.
- **M0-TST-004:** Session Time remains a decimal string beyond `2^53-1`.
- **M0-TST-005:** deterministic missing/corrupt/version-mismatch and insufficient fixture failures.
- **M0-TST-006:** machine-archivable Windows/Linux fixture and frozen-input logical-equivalence evidence.

Step 9 is therefore **COMPLETE**. This completion still does not claim production Metric mathematics,
production Release/Replay qualification, M0 Exit, or any M1 capability.
