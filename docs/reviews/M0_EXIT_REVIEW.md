# M0 Exit Review

- **Status:** PR ACCEPTANCE PASS / MAIN MERGE PENDING
- **Authority:** SDIB-1.0 §16.3, §18, §39 step 11, Appendix F, Appendix K.
- **Review baseline:** merged `main` revision `5768d53e6e2eb4cda59080ff4958d06e3984f499`.
- **Step 10 evidence:** GitHub Actions Run #26 (`35836960857`) — Windows/Linux/logical-equivalence SUCCESS.
- **Decision:** GO on PR acceptance revision `863ff928bb072775e5b99599571827d07cb19832`; merged-main GO still pending.
- **Important boundary:** M0 GO means engineering-substrate admission to M1 only. It is not P1 capability acceptance.

## 1. Scope

M0 objective is the sustainable engineering substrate: one source tree can clean-checkout on Windows/Linux,
verify the frozen baseline, install frozen dependencies, bootstrap storage, execute tests, start API/Desktop,
produce traceable development artifacts and reproduce the result from a clean environment.

All M0 backlog IDs in SDIB §17 have implementation records and governed gates. No P1 capability is claimed.

## 2. Baseline

Review baseline inputs are:

- source revision: `5768d53e6e2eb4cda59080ff4958d06e3984f499`;
- Core Baseline: `CB-1.4.0`;
- DB schema: `1.6.0`;
- dependency lock SHA-256: `302ab51a013c713af6ece61113526eb411f6edf302b70c7a924224701387257e`;
- Baseline Lock SHA-256: `9d96a7eb0ba2b1fb13b11d76943171f773fd42497df74bf79c01928cfa26e7fa`;
- P1 Metric Catalog authority SHA-256: `24ab6d06ced0b768ff16e4c945e778cc8fd2d3838be3ca30051ec8f8e0d7277d`;
- Stage authority SHA-256: `52377c097342fd52ad7b10e771a85420f3dca24f0446d171ff285306b8245691`;
- DTO authority SHA-256: `be9e83d18427c0a71d80df6ba2a56f7f611a059c749e1e163d9b5c0140b90e1c`.

## 3. Gate Results

Run #26 proves the merged Step 10 Windows/Linux gate set and cross-platform logical equivalence.

Step 11 adds two fail-closed jobs:

1. **M0 Exit PostgreSQL** — live PostgreSQL 16 clean bootstrap, fail-closed schema/provenance checks,
   Repository/UoW acceptance, and clean-clone cold-start that re-executes those PostgreSQL results.
2. **M0 Exit Review** — aggregates machine evidence for all 14 SDIB §18 Exit conditions and returns
   `GO` only if every condition is PASS for the same source revision.

GitHub Actions Run #29 (`35840449678`) completed SUCCESS for Windows, Linux, live PostgreSQL,
logical equivalence and the M0 Exit Review aggregator. Artifact `10741590060`
(`sha256:89d6b0e7a1bad27373b149a33bcdf9fc71c96e2c39cf2a4c67261f26f5325c09`) records
`status=PASS`, `decision=GO`, all 14 §18 gates PASS, `mismatches=[]`, and
`source_revision_consistent=true`.

This is PR acceptance evidence. The review is not final on `main` until this PR is merged and the same
Exit workflow produces GO for the merged revision.

## 4. Open Defects

At review start, the repository has no open GitHub issues and no other open PRs.

No known implementation defect is currently classified as an M0 blocker. The PostgreSQL cold-start
coverage gap described above is treated as an Exit-evidence blocker and is being closed in this review PR.

## 5. Deviations / ADRs

ADR-M0-001 through ADR-M0-010 are CLOSED. The governance verifier checks status, owner role, decision and
evidence references. No unresolved M0 ADR is permitted to enter M1.

Development packages remain intentionally pre-release and are marked `DEVELOPMENT_NOT_M5_QUALIFIED`.

## 6. Cross-platform

Windows Server 2025 and Ubuntu 24.04 run the same governed M0 gate dispatcher, CPython 3.13.5, uv 0.12.17
and the same `uv.lock`.

Run #26 logical-equivalence evidence reports `mismatches=[]` using identical frozen inputs. Platform
archive bytes, paths and host metadata are excluded from logical identity.

## 7. Reproducibility

Run #26 Windows and Linux cold-start evidence already proves clean clone + frozen dependency sync + M0 gates
+ clean worktree.

Step 11 strengthens this by requiring one clean-clone run against a live PostgreSQL 16 service so §18.14
also reproduces the PostgreSQL clean-bootstrap/Repository result instead of only retaining earlier task
evidence.

## 8. Data Governance

M0 tests/fixtures use synthetic/public development data. The framework fixture is
`REVIEWED / FRAMEWORK_SMOKE_ONLY`, not a production Metric Golden. Development data guard and secret
field fail-closed checks run on both OS families.

## 9. Known Limitations

- P1 Metric/Stage/Release capability is not implemented/admitted by M0.
- Golden/replay at M0 are framework smoke only.
- Development packages are not M5-qualified installers/releases.
- Performance/target-workload, upgrade/uninstall qualification and formal release acceptance belong to later milestones.

## 10. Decision

**PR ACCEPTANCE: GO.** Run #29 machine evidence reports every one of the 14 SDIB §18 Exit conditions PASS
for PR merge revision `863ff928bb072775e5b99599571827d07cb19832`.

This does **not** yet publish the M0 baseline. Final milestone closure requires:

1. merge this Exit Review PR;
2. obtain one fresh `main` run whose M0 Exit Review artifact again reports `decision=GO`;
3. publish the `M0_IMPLEMENTATION_BASELINE` manifest/tag against that accepted merged-main revision.

The tag is engineering baseline evidence only and must not be represented as a P1 capability release.
