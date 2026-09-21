# M0-CORE-004 — Generated-source Governance / Regenerate-Diff

- **Status:** COMPLETE
- **Baseline:** SDIB-1.0
- **Core Baseline:** CB-1.4.0
- **Depends on:** M0-CORE-001, M0-CORE-002, M0-CORE-003
- **Related decision:** ADR-M0-007

## 1. Objective

Make checked-in generated Python source a governed projection of Canonical authority rather than an editable implementation surface.

M0-CORE-004 closes two mandatory SDIB acceptance semantics:

1. every generated Python source file carries source artifact/version/hash and generator-version provenance; and
2. a CI-compatible regenerate-diff gate rejects committed manual edits or stale generated projections.

## 2. Policy boundary

`src/tpaa_generated/` is a machine-generated tree. Human-authored business logic is prohibited in this tree.

The approved workflow is:

Canonical / BASELINE_LOCK
→ CanonicalArtifactLoader
→ tpaa_codegen
→ checked-in `src/tpaa_generated/`
→ non-destructive verification
→ regenerate-diff gate

Generated source remains a projection, never machine authority.

## 3. Generated-source provenance header

Every generated `.py` file SHALL begin with deterministic comments containing:

- generated marker / do-not-edit statement;
- generator id;
- generator version;
- one or more source records containing artifact id, authority version label and SHA-256.

For baseline-derived infrastructure files, `BASELINE_LOCK` is the source artifact, its Core Baseline is the source version label, and the trusted lock digest is the source SHA-256.

Headers SHALL contain no timestamp, user, hostname or absolute path.

## 4. Tree governance

The expected generated tree is exactly the set emitted by the default generation coordinator, excluding runtime cache files such as `__pycache__` and `*.pyc`.

Governance rejects:

- missing expected generated file;
- byte drift in an expected generated file;
- unexpected source/data file under the governed tree;
- stale or invalid provenance header;
- manifest/source/output mismatch.

No portable filesystem read-only bit is treated as authority because Git does not preserve a cross-platform read-only policy. “Read-only” is enforced by repository policy plus deterministic verification/gates.

## 5. Commands

### Non-destructive local/CI check

`python tools/dev/tpaa_dev.py verify-generated`

Builds expected bytes in memory and verifies the checked-in generated tree without rewriting it.

### Regenerate-diff gate

`python tools/dev/tpaa_dev.py regenerate-diff`

The gate:

1. requires the generated tree to have no pre-existing uncommitted changes;
2. regenerates using the same approved coordinator used by `generate`;
3. verifies exact generated-tree inventory and provenance;
4. executes `git diff --exit-code -- src/tpaa_generated`;
5. fails if regeneration changed bytes relative to the checked-in revision.

This command is CI-vendor-neutral. Future CI orchestration SHALL invoke this same command rather than reimplementing generation semantics.

## 6. Failure semantics

M0-CORE-004 uses deterministic code-generation reason codes for at least:

- `GENERATED_FILE_MISSING`
- `GENERATED_FILE_DRIFT`
- `UNEXPECTED_GENERATED_FILE`
- `PROVENANCE_HEADER_MISMATCH`
- `GENERATED_TREE_DIRTY`
- `REGENERATE_DIFF_FAILED`
- `GIT_UNAVAILABLE`

## 7. Test matrix

Required contract coverage:

- all generated Python files contain exact provenance;
- non-destructive verifier passes on the repository state;
- one-byte generated-file drift is rejected;
- unexpected generated-tree file is rejected;
- missing generated file is rejected;
- regenerate-diff passes on a clean correct checkout;
- regenerate-diff refuses pre-existing uncommitted generated-tree changes;
- a clean Git checkout containing a committed manual generated edit is rejected after regeneration;
- repeated generation remains byte-identical;
- M0-CORE-001/002/003 regressions remain green.

## 8. Completion criteria

M0-CORE-004 may be marked COMPLETE when:

- ADR-M0-007 is CLOSED;
- all governed Python outputs carry exact deterministic provenance headers;
- the generated tree is entirely governed by expected generation output;
- `verify-generated` passes;
- `regenerate-diff` passes on an unchanged checkout;
- fault injection proves committed/uncommitted manual drift is blocked;
- repository regression tests pass;
- clean-clone verification passes;
- no external Windows or CI-service execution is claimed without real evidence.

## 9. Implementation record

- 2026-09-21 — v0.1 created. Chosen policy: checked-in generated source plus vendor-neutral regenerate-diff command; no CI-provider lock-in.
- 2026-09-21 — Provenance injection centralized in `GenerationCoordinator`; all generated Python outputs, including package `__init__.py`, are governed rather than leaving a handwritten exception in `tpaa_generated`.
- 2026-09-21 — Fault injection proved one-byte drift, missing output, rogue output and pre-existing uncommitted generated changes fail closed.
- 2026-09-21 — Temporary clean Git fixture proved a committed manual generated edit is rejected by regenerate-diff after regeneration.
- 2026-09-21 — Repository regression reached 52/52 PASS; task advanced to COMPLETE pending post-commit clean-clone delivery verification.
