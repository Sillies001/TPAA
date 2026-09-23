# M0-TST-001..006 — Test / Fixture Harness

- **Status:** IN-PROGRESS — repository implementation is present; hosted Windows/Linux Golden/replay
  framework smoke and cross-platform logical-equivalence evidence are required before Step 9 completion.
- **Workstream:** WS-TEST
- **Authority:** SDIB-1.0 §14, §15.1, §17 (`M0-TST-001`..`M0-TST-006`), §39 step 9,
  Appendix A, Appendix F, Appendix I, Appendix O, Appendix T.
- **Starting revision:** `0c56f064aa033b3f7d467fb36dc0d9a8ce682e56` (Step 8 complete on `main`).

## M0 scope boundary

Step 9 establishes the verification substrate required before the remaining M0 backlog and before M1.
It does **not** implement M1 Metric algorithms, Basic Flight Stage projection, production Release/Replay,
or the eight M1 synthetic bundles.

Appendix F requires only framework smoke at M0 for Golden and replay. The cross-platform Gate compares
a basic frozen logical product. Production Metric/Stage/Release semantics remain owned by their later
milestone tasks.

## Implemented harness

1. `tests/unit`, `tests/contract`, `tests/golden`, `tests/replay`, `tests/migration`, and
   `tests/e2e` are all executable through the same `tools/dev/tpaa_dev.py` dispatcher semantics.
2. `fixtures/golden/M0_BASIC_TRANSPORT_V1` is a frozen framework-smoke bundle with fixture id/version,
   exact input and expected hashes, Context/Stage/Profile refs, numeric tolerance, known invalid and
   insufficient cases, and a replay provenance record.
3. The fixture uses NUMERIC/TEXT/BOOLEAN/STRUCTURED values and a Session Time decimal string larger than
   the JavaScript safe-integer range so transport behavior is exercised without inventing a production
   Metric.
4. `tools/testing/fixture_harness.py` validates paths, lifecycle, hashes, fixture version, typed values,
   Session Time representation, expected logical products, replay frozen refs, evidence metadata, and
   Windows/Linux logical equivalence.
5. Missing input, corrupt/hash-drift input, unsupported fixture version, and insufficient payload produce
   deterministic engineering failure classifications.
6. Fixture evidence carries source revision, project/build version marker, Core Baseline, Baseline Lock
   hash, DB schema, Metric/Stage/DTO authority hashes, dependency-lock hash, platform profile, fixture
   id/version/hash, job identity, tolerance, replay source Release, start/end timestamps, and controlled
   failure classification.
7. The fixture lifecycle is `REVIEWED`, not `APPROVED_GOLDEN`. This is deliberate: the M0 harness
   does not fabricate an independent Metric-mathematics approval. Promotion to `APPROVED_GOLDEN`
   remains governed by Appendix O review discipline.

## CI integration

The existing Windows/Linux matrix remains the platform execution authority. Each platform now:

- runs `test-golden`, `test-replay`, and the M0 framework `test-e2e` inside `ci-check`;
- emits `evidence/tests/framework-<platform>.json`;
- emits `evidence/cross-platform/<platform>.json`;
- archives those files with the existing per-platform CI evidence.

A dependent `M0 logical equivalence` job downloads both immutable matrix artifacts and compares the
Windows/Linux logical products. Stable identity, Session Time, kind/status-like discrete values and
structured values are exact; NUMERIC values use the one tolerance frozen in the fixture manifest.
There is no OS-specific threshold.

## Ticket coverage

- **M0-TST-001:** executable unit/contract/golden/replay/migration/e2e directories and unified runners.
- **M0-TST-002:** explicit Canonical contracts cover Core/DTO/Metric/Stage/P-M-WS authority loading,
  supplementing the already governed loader/codegen contracts.
- **M0-TST-003:** NUMERIC/TEXT/BOOLEAN/STRUCTURED JSON transport round-trip smoke.
- **M0-TST-004:** Session Time remains a decimal string beyond `2^53-1`; no float conversion is allowed.
- **M0-TST-005:** deterministic missing/corrupt/version-mismatch and insufficient fixture failures.
- **M0-TST-006:** machine-archivable fixture/platform/logical-equivalence evidence.

## Completion discipline

Step 9 remains **IN-PROGRESS** until a real GitHub Actions run on the Step 9 checkpoint proves:

1. Windows Golden/replay/framework E2E GREEN;
2. Linux Golden/replay/framework E2E GREEN;
3. both platform evidence artifacts are generated for the same source revision and fixture hash;
4. the dependent logical-equivalence comparison is GREEN with zero mismatches;
5. existing Step 8 and earlier M0 gates remain GREEN.

This task does not claim packaging, SBOM/build manifest, cold-start, remaining M0 backlog, M0 Exit,
or any M1 capability.
