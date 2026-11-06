# W0-W2 local candidate qualification

Date: 2026-10-20
Branch: `local-r8-review`
Source checkpoint: `8401751f27d3d52926caba54a9cfa91ae26f526b`
Status: `PASS / LOCAL_ONLY / NOT_PUSHED / NOT_DEPLOYED`

## Candidate preparation

- Reviewed all tracked modifications and untracked candidates before staging.
- Excluded `evidence/local/`, including PostgreSQL dumps, runtime journals,
  object-store fixtures and real-data inputs/derivatives.
- Scanned the candidate for private-key markers, AWS access-key forms, GitHub
  token forms, credential-bearing PostgreSQL/MongoDB URIs and suspicious
  credential file names; no match was found.
- Confirmed no new candidate file exceeded 1 MiB.
- Confirmed `git diff --cached --check` passed before commit.
- Committed 259 files as the local W0-W2 reproducible checkpoint; no remote
  operation was performed.

## Verification

| Gate | Result |
|---|---|
| Ruff, complete repository | `PASS` |
| mypy, 275 source files | `PASS` |
| generated-source deterministic verification | `PASS` |
| CB-1.5.0 authority baseline | `37/37 PASS` |
| Python compileall | `PASS` |
| unit suite | `737 PASS` |
| contract suite | `815 PASS / 0 FAIL` |
| clean-worktree development package contract | `PASS` |

The contract run still reports two upstream FastAPI/Starlette deprecation
warnings; they are not assertion failures and remain dependency-governance
work.

## Package evidence

Profile: `WINDOWS_DESKTOP_X64`
Artifact: `tpaa-1.0.0-WINDOWS_DESKTOP_X64.zip`
Bytes: `3528391`
SHA-256: `7adcb81e1e35b3ae991e2664340d6f27782d7742319f1c5d485f601573538d8a`
Summary SHA-256: `bd9de0aade8b1e63c1e94860f2687455cedad1d3e6cab3a6162d2d8a50716d7a`

The archive contains `build-evidence/build-manifest.json`,
`build-evidence/package-manifest.json` and `build-evidence/sbom.cdx.json`.
The summary explicitly labels the artifact `DEVELOPMENT_NOT_M5_QUALIFIED`.
The package and summary remain under ignored local evidence and were not
uploaded or deployed.

## Boundary

This closes the previously deferred clean-worktree development packaging gate
for the W0-W2 local candidate. It does not claim protected-main status,
signature, M5 qualification, production readiness or deployment approval.
