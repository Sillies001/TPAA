# SDIB §39 Step 10 — Remaining M0 Backlog + Cold Start

- **Status:** PR ACCEPTANCE PASS / MAIN MERGE PENDING
- **Branch revision:** `7b04c0aa769f0cc7c83abffe696fcaded0c0f222`
- **Authority:** SDIB-1.0 §17, §18, §30–§34, §39 step 10; Appendix E/F/H/I/P/Q/T.
- **Hosted acceptance:** GitHub Actions Run #24 (`35833762529`) on PR #5.
- **Scope:** remaining M0 backlog only. M0 Exit Review remains §39 step 11.

## Implemented backlog

### Storage

- **M0-STO-004:** local object/Parquet abstraction uses `tpaa-object://` and `tpaa-parquet://`
  logical URIs; physical roots and OS path syntax are excluded from logical identity.
- **M0-STO-005:** migration harness covers clean bootstrap, readiness, rollback, committed drift
  fail-closed, forward recovery, historical-fixture hook and Repository conformance without inventing
  a fake post-1.6.0 schema revision.
- **M0-STO-006:** separate canonical request, logical-content and exact artifact-byte SHA-256 primitives.
- **M0-STO-007:** disposable SQLite + logical-object backup/restore smoke verifies schema, Core refs,
  object identity and bytes after restore.

### API / Application

- **M0-API-003:** `api/openapi-m0.json` is generated deterministically from
  `CROSS_LAYER_DTO_CONTRACTS.json`; required/nullability/transport projections are contract-tested.
- **M0-API-004:** M0 job-control skeleton freezes canonical request hashing and
  Idempotency-Key same-key/same-request reuse vs same-key/different-request conflict.
- **M0-API-005:** Application/API status mapping keeps controlled business statuses separate from
  system failures and exposes the job skeleton through the Application boundary.

### Platform

- **M0-PLAT-001:** path/filesystem adapter rejects traversal, drive/backslash logical paths and
  Unicode/case collisions.
- **M0-PLAT-002:** real `multiprocessing` spawn round-trip proves serializable worker payloads with
  no fork-only inherited state.
- **M0-PLAT-003:** Windows/POSIX file-lock adapters and close-before-`os.replace` atomic publication
  are covered by platform tests and smoke on both hosted OS families.

### Security / governance

- **M0-SEC-001:** Desktop loopback/bearer/origin controls are retained and a governed path allowlist
  rejects non-approved paths.
- **M0-SEC-002:** structured audit events record actor/request/reason/version/hash framework fields.
- **M0-SEC-003:** development data guard permits synthetic/public development classifications and
  fails closed for unapproved sensitive/operational data.
- **M0-SEC-004:** structured observability rejects secret-bearing fields; token/credential data is
  excluded from logs, fixtures and build evidence.
- **M0-GOV-001..004:** all ADR-M0-001..010 are CLOSED; Issue/PR templates, Baseline Change workflow
  and PR/Feature/Milestone Definition of Done are executable repository governance.

### DevOps

- **M0-DEV-003:** build manifests bind source revision, product version, baseline hashes,
  dependency-lock hash and platform profile.
- **M0-DEV-004:** CycloneDX 1.6 SBOM, license inventory and native-dependency inventory are generated
  per platform/profile without claiming legal approval.
- **M0-DEV-005:** all four governed Desktop/Service development profiles produce deterministic
  development bundles explicitly marked `DEVELOPMENT_NOT_M5_QUALIFIED`; clean extraction,
  `uv sync --locked`, baseline/generated verification and Desktop/API start-stop smoke pass.
- **M0-DEV-006:** cold-start performs a clean local clone at the tested revision, frozen dependency
  sync, the current M0 gate set, and clean-worktree verification.

## Hosted evidence — Run #24

Both hosted platform jobs completed SUCCESS and the dependent logical-equivalence job completed SUCCESS.
The CI evidence for both platforms reports `failed_gate_names = []`.

Required Step 10 gates include:

- governance verification;
- OpenAPI snapshot;
- migration smoke;
- backup/restore smoke;
- security smoke;
- Ruff and mypy;
- unit/contract/Golden/replay/e2e;
- platform tests + real platform smoke;
- Repository/bootstrap/API/GUI/Desktop lifecycle/UI automation;
- clean development package smoke;
- frozen lock + clean Git diff;
- cold-start from a clean clone.

Cold-start evidence:

- Linux: `status=PASS`, `clean_clone=true`, `uv_sync_locked=true`, `m0_gates=PASS`,
  `worktree_clean=true`.
- Windows: the same five conditions are PASS/true.

Development package evidence exists for all four mandatory profiles:

- `LINUX_DESKTOP_X64`
- `LINUX_SERVICE_X64`
- `WINDOWS_DESKTOP_X64`
- `WINDOWS_SERVICE_X64`

Each artifact remains explicitly a development package, not an M5 qualified release.

The Run #24 logical-equivalence evidence is also PASS with the same frozen input hashes and
`mismatches=[]`.

## Completion discipline

The repository implementation and PR-hosted acceptance for §39 step 10 are complete enough for merge
review. **Step 10 is not yet recorded COMPLETE on `main`** because PR #5 has not been merged and no
post-merge main run exists yet.

After PR #5 merge, one fresh main run must prove the same Windows/Linux/cold-start/package/logical
evidence. Only then may §39 step 10 be marked COMPLETE and §39 step 11 M0 Exit Review begin.
