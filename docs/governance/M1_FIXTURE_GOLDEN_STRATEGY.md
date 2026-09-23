# M1 Synthetic / Golden Development Data Strategy

## Purpose and authority

This document freezes the SDIB-1.0.1 M1 entry strategy required by §19.1(7), §22, and Appendix O.

It is an **entry-governance contract only**. It does not admit M1, create business capability, or authorize M1 feature implementation.

Machine policy: `tools/testing/M1_FIXTURE_POLICY.json`.

## Data-governance boundary

The M1 baseline fixture program depends on **synthetic data only**.

- default allowed classification: `SYNTHETIC`;
- operational-data dependency: **false**;
- sensitive-data dependency: **false**;
- unauthorized operational/sensitive data: **prohibited**.

If a future test requires operational or sensitive data, that is outside this baseline strategy and requires a separately approved controlled-data environment plus an explicit approval reference. Such an exception does not alter the default M1 fixture baseline.

## Required fixture bundles

The exact M1 bundle set is:

1. `BF_M1_NOMINAL_V1`
2. `BF_M1_GAP_V1`
3. `BF_M1_ANGLE_WRAP_V1`
4. `BF_M1_STRUCTURED_PARTIAL_V1`
5. `BF_M1_STAGE_BOUNDARY_V1`
6. `BF_M1_REPLAY_V1`
7. `BF_M1_CROSS_PLATFORM_V1`
8. `BF_M1_FAILURE_V1`

Their purposes and minimum coverage are frozen machine-readably in `M1_FIXTURE_POLICY.json`.

This document does **not** create the fixture payloads themselves; that remains `M1-TST-001` after M1 admission.

## Golden lifecycle

Each fixture follows:

```text
DRAFT
  ↓ independent input / expected-result review
REVIEWED
  ↓ hash/version freeze
APPROVED_GOLDEN
  ↓ CI / milestone evidence
RETIRED
```

A retired fixture remains addressable for historical regression and replay.

## Change rules

- Input-byte changes require a fixture version change and new input hash.
- Expected-result changes require an explicit rationale distinguishing Golden correction from upstream semantic change.
- Metric or Stage semantic changes may not be hidden by updating only `expected/`; the relevant authority/version must change first.
- Harness-only fixes may not silently reapprove expected results.
- Tolerance changes require rationale and review; tolerance must not be widened merely to hide a cross-platform or algorithmic defect.

## Expected-result independence

Expected results must be independently reviewable and cannot be copied from the first output of the implementation under test.

Permitted approaches include:

- human-recalculable expected values;
- an independent reference script;
- an independent reference implementation.

The Golden reviewer must be independent of the implementation/expected-result author for acceptance. The named reviewer is intentionally **not invented here**; §19.1(8) remains blocked until explicit human assignments are recorded.

## Common manifest requirements

Every M1 fixture manifest must carry at least:

- fixture id;
- fixture version;
- input SHA-256;
- expected-result SHA-256;
- authority refs;
- tolerance profile;
- data classification;
- review state.

## Admission boundary

Publishing this strategy can satisfy the data-strategy portion of §19.1(7) once repository CI accepts it, but it does not satisfy §19.1(8) and does not change:

`M1_NOT_ADMITTED`
