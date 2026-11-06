# W0 Authority Convergence and Closure Review

Status: **CLOSED / APPROVED_LOCAL_NOT_PUSHED**

Decision ID: `W0-AUTHORITY-CONVERGENCE-2026-10-19`

The project owner explicitly delegated the four outstanding W0 baseline
decisions to the implementation agent. This record approves and activates the
successor authority in the local worktree. It does not authorize a repository
push, production deployment, or production-readiness claim.

## Approved version tuple

- Overall: `TPAA V8.0`;
- Engineering: `ED-2.0`;
- Core: `CB-1.5.0`;
- DB schema: `1.9.0`;
- Product: `P1_METRIC_CATALOG-1.14.0`.

R3.3 and CB-1.4.0 remain immutable predecessors. The successor is a new
`baseline/CB-1.5.0` package; neither predecessor was overwritten.

## Closure evidence

- R3.3 reference lock SHA-256:
  `9d96a7eb0ba2b1fb13b11d76943171f773fd42497df74bf79c01928cfa26e7fa`.
- Immediate CB-1.4.0 predecessor lock SHA-256:
  `06fb823c8db79a19a45bb5f1da2c201644945c3967de94a312acd8f93d0ab437`.
- Approved CB-1.5.0 lock SHA-256:
  `ecdb68d0aa17ad49b2b0b3bdbad0e82559cd455725a0eb2a2a4855feba99edab`.
- Controlled artifacts: R3.3 `21`; CB-1.5.0 `37`.
- R3.3 to CB-1.5.0 diff: 16 added, 2 modified, 0 removed and 19
  unchanged.
- Structural delta remains 18 added tables, 31 added DTO contracts and 3
  added API transport rules. Only the Core model and cross-layer DTO contract
  are promoted relative to R3.3; unchanged predecessor authorities remain
  byte-identical and are covered by explicit Core inheritance declarations.
- CB-1.5.0 authority consistency: `PASS`, with zero hard failures and zero
  review findings.
- R3.3 validation: `65/65 PASS` and independent audit `24/24 PASS` on Windows
  and in a read-only Linux `python:3.11-slim` container.
- Local Python 3.13.5 regression: W0/loader `18 PASS`; unit suite `713 PASS`;
  contract suite `814 PASS` with only the clean-worktree packaging case
  deliberately excluded while local modifications remain uncommitted.
- Targeted Ruff checks and Python `compileall` pass. Polars tests required
  `POLARS_SKIP_CPU_CHECK=1` because the installed 1.44.2 wheel reports the
  current Windows `sse3` feature label as unknown; business assertions still
  executed normally.

Machine evidence:

- `docs/reviews/W0_R3_3_AUTHORITY_DIFF.json`;
- `docs/reviews/W0_AUTHORITY_CONSISTENCY.json`;
- `docs/compliance/W0_COMPLIANCE_MATRIX.json`;
- `baseline/CB-1.5.0/canonical/W0_BASELINE_AUTHORITY_DECISION.json`.

## Approved resolutions

1. A successor Core identity is mandatory because the logical model and DTO
   authority changed. Reusing CB-1.4.0 for both snapshots is prohibited.
2. All 23 historical DB 1.6 declarations retain their original value and are
   governed individually by `SCHEMA_COMPATIBILITY_AUTHORITY.json`. Each is
   approved for additive forward compatibility through DB 1.7, 1.8 and 1.9 via
   ACP-216/219/221 lineage.
3. Index authority is not N/A. `PHYSICAL_INDEX_AUTHORITY.json` governs the
   primary-key and unique indexes derivable from the Core model. Any secondary
   performance index requires a later authority change.
4. API route authority is not N/A. `API_ROUTE_AUTHORITY.json` freezes all
   statically declared FastAPI method/path/module/handler bindings and binds
   them to `CROSS_LAYER_DTO_CONTRACTS`.
5. The successor lock carries the complete predecessor lock lineage plus the
   immediate CB-1.4.0 lock hash.

## Implemented controls

1. `authority-diff` emits deterministic, non-adopting artifact and semantic
   differences for tables, fields, CHECK/enum constraints, indexes, DTOs and
   API transport/routes.
2. `verify-authority-consistency` verifies lock bytes, Core/DB/table/DTO
   identity, compatibility coverage, index authority, API route authority,
   the W0 decision and lock lineage.
3. `adopt_w0_successor.py --check` independently reconstructs CB-1.5.0 and
   compares the complete directory digest, preventing hand-edited successor
   drift.
4. The Canonical loader reads the locked inheritance authority and accepts an
   older Core identity only for an individually approved file; an undeclared
   predecessor identity still fails closed.
5. Runtime identity, the Canonical loader, generated projections, OpenAPI
   snapshots and current product API resolve CB-1.5.0. Historical fixtures and
   unchanged semantic authorities retain CB-1.4.0 identity under the approved
   Core-inheritance declaration instead of rewriting qualified history.
6. The R3.3 independent audit uses POSIX-normalized manifest paths on both
   Windows and Linux.

## Closure boundary

W0 is formally closed for this local worktree. Later W1-W9 traceability and
production gates remain open. The current result is a locally approved
engineering baseline, not a pushed, protected-main, signed, deployed or
production-qualified release.

## Post-closure local candidate verification (2026-10-20)

The earlier clean-worktree packaging exclusion is resolved. Authorized local
checkpoint `8401751` includes the governed W0-W2 candidate, and the complete
contract suite now reports `815 passed, 0 failed`. The Windows Desktop
development package, build/package manifests and SBOM pass without weakening
the clean-tree gate. The candidate remains local, unpushed, unsigned,
undeployed and explicitly not M5-qualified.
