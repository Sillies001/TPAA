# ACP-219 DB 1.8.0 Authority Adoption Review

ACP-219 is an additive current-physical persistence correction for PIQB B2 Issue #209 and residual authority Issue #219.

The candidate is valid only when:
- DB 1.7.0 exact historical CORE bytes are preserved;
- the current CORE advances to DB 1.8.0 with exactly 94 relations;
- exactly two ordered-text relations are added;
- all pre-existing 92 relation semantics are byte-equivalent after excluding the table-level current schema-version marker;
- SQLite/PostgreSQL migration, downgrade fail-closed and re-upgrade evidence pass;
- Hosted CI remains exactly 14/14;
- the candidate PR reports `PENDING_PROTECTED_MAIN / ACP219_DB_1_8_0_CANDIDATE`.

Formal adoption occurs only on the actual protected-main merge SHA with 14/14 SUCCESS and reviewer `GO / ACP219_DB_1_8_0_ADOPTED`.
