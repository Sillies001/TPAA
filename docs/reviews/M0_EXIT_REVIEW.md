# M0 Exit Review

- **Status:** MERGED-MAIN GO / BASELINE TAG PUBLICATION PENDING
- **Authority:** SDIB-1.0 §16.3, §18, §39 step 11, Appendix F, Appendix K.
- **Accepted main revision:** `ee54e8500381e62a53e1f2352d485ed11892c9d6`.
- **Final hosted evidence:** GitHub Actions Run #31 (`35849313925`).
- **Decision:** **GO**.
- **Important boundary:** M0 GO admits the engineering substrate to M1 work. It is not P1 capability acceptance.

## 1. Scope

M0 proves the sustainable engineering substrate: one source tree can clean-checkout on Windows/Linux,
verify the frozen baseline, install frozen dependencies, bootstrap storage, execute tests, start API/Desktop,
produce traceable development artifacts and reproduce the result from a clean environment.

All M0 backlog IDs in SDIB §17 have implementation records and governed gates. No P1 capability is claimed.

## 2. Baseline

Final accepted inputs:

- source revision: `ee54e8500381e62a53e1f2352d485ed11892c9d6`;
- Core Baseline: `CB-1.4.0`;
- DB schema: `1.6.0`;
- dependency lock SHA-256: `302ab51a013c713af6ece61113526eb411f6edf302b70c7a924224701387257e`;
- Baseline Lock SHA-256: `9d96a7eb0ba2b1fb13b11d76943171f773fd42497df74bf79c01928cfa26e7fa`;
- P1 Metric Catalog authority SHA-256: `24ab6d06ced0b768ff16e4c945e778cc8fd2d3838be3ca30051ec8f8e0d7277d`;
- Stage authority SHA-256: `52377c097342fd52ad7b10e771a85420f3dca24f0446d171ff285306b8245691`;
- DTO authority SHA-256: `be9e83d18427c0a71d80df6ba2a56f7f611a059c749e1e163d9b5c0140b90e1c`.

## 3. Gate Results

Run #31 completed SUCCESS for all five Exit jobs:

1. `M0 windows`;
2. `M0 linux`;
3. `M0 Exit PostgreSQL`;
4. `M0 logical equivalence`;
5. `M0 Exit Review`.

The final review artifact `10744637893`
(`sha256:1047056f71ead3dbd997f6684d77932067d0314fd1281cd72af409783158472c`) records:

- `status=PASS`;
- `decision=GO`;
- all **14/14** SDIB §18 Exit gates PASS;
- `source_revision_consistent=true`;
- logical-equivalence `status=PASS`, `mismatches=[]`;
- source revision exactly `ee54e8500381e62a53e1f2352d485ed11892c9d6`.

## 4. Open Defects

At final Exit acceptance there are no open GitHub issues or open pull requests other than the baseline
publication change itself. No known M0 implementation defect is classified as a blocker.

The earlier PostgreSQL cold-start evidence gap is resolved by the live PostgreSQL Exit job and
clean-clone PostgreSQL cold-start included in Run #31.

## 5. Deviations / ADRs

ADR-M0-001 through ADR-M0-010 are CLOSED. The governance verifier checks status, owner role, decision and
evidence references. No unresolved M0 ADR is carried into M1.

Development packages remain intentionally pre-release and are marked `DEVELOPMENT_NOT_M5_QUALIFIED`.

## 6. Cross-platform

Windows Server 2025 and Ubuntu 24.04 execute the same governed M0 gate dispatcher with CPython 3.13.5,
uv 0.12.17 and the same `uv.lock`.

Run #31 logical-equivalence evidence reports `mismatches=[]` using identical frozen inputs. Platform
archive bytes, paths and host metadata remain outside logical identity.

## 7. Reproducibility

Windows and Linux cold-start evidence proves clean clone, frozen dependency sync, full governed M0 gates
and clean worktree. The live PostgreSQL Exit cold-start additionally re-executes PostgreSQL clean bootstrap
and Repository acceptance from the clean clone.

This satisfies SDIB §18.14 without relying only on retained earlier task evidence.

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

**GO.** Merged-main Run #31 proves every one of the 14 SDIB §18 Exit conditions on the accepted main
revision.

Per SDIB §18, the engineering baseline is now ready for publication as
`M0_IMPLEMENTATION_BASELINE`. The machine publication manifest is
`docs/baseline/M0_IMPLEMENTATION_BASELINE.json`.

The tag must point exactly to `ee54e8500381e62a53e1f2352d485ed11892c9d6`. The tag is engineering
baseline evidence only and must not be represented as a P1 capability release.
