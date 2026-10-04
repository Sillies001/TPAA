# ACP-221 DB 1.9.0 Authority Adoption Review

This review is machine-gated by `tools/testing/acp_221_authority_adoption.py`.

Acceptance requires: exact revision identity; exactly 14/14 Hosted CI required jobs; immutable DB 1.8.0 historical snapshot; exact additive DB 1.9.0 relation inventory; SQLite/PostgreSQL migration and downgrade qualification; no shadow authority; and protected-main execution before qualification may become `ACP221_DB_1_9_0_ADOPTED`.

A pull-request candidate may only report `PENDING_PROTECTED_MAIN` / `ACP221_DB_1_9_0_CANDIDATE`.
