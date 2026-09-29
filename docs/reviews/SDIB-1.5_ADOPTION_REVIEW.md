# SDIB-1.5 Adoption / M6 Refinement Review

## Review identity
- **Change class:** C1 — post-M5 backlog refinement.
- **Adopted implementation baseline:** SDIB-1.5; parent SDIB-1.4.
- **Tracking issue:** #150; program policy #149; P2 authority closure #151.
- **Core baseline / DB schema:** CB-1.4.0 / 1.6.0.
- **Document SHA-256:** `6e5ea15a6d2217837ea9ecac34a297e0880f1305a6aba77ef5e44275879fa646`.
- **M6 manifest SHA-256:** `026b5718c8c603c1126b079ac5070283284ac6f291827b749dcdad0d779e7918`.

## Entry evidence
Protected main `aae1e692774f7c10114d66fd79acb254c2aabfef`, Run #472 / `36556569965` is PASS (14/14 jobs) and preserves the formally qualified P1 product state.

## Candidate refinement
SDIB-1.5 freezes 17 M6 Tasks across exact required workstreams: CAPABILITY, DATA, TEST, GUI and GOVERNANCE; exactly four coarse batches.

M6 is a C4 admission program for P2, but this C1 baseline does **not** itself admit P2. P1 remains immutable/currently admitted; P3-P6 remain inactive.

## Corrective qualification evidence
Run #473 / `36570933366` on `4b709d6dbcf46cd5ba9bb01d01dc28f336824440` failed because the recorded SDIB-1.5 SHA-256 was stale (`dc070548abe6b0a7a2fd3decfe0e4e7e2a8f420877d4d68b5d4dee4e7606a9b4`) while the governed document actually hashes to `6e5ea15a6d2217837ea9ecac34a297e0880f1305a6aba77ef5e44275879fa646`.

The single corrective commit `647cf98e2c407d7c6c99e4e0a6bf254d764d7f57` changes only the four governed hash references. PR #153 presents that exact corrected head. Run #475 / `36576098823` is the qualified PR #153 exact-head run and is PASS with all 14 required jobs. Run #474 / `36576016413` independently passed the same corrected SHA on the superseded PR #152 branch.

## Protected-main adoption
- qualified candidate head: `647cf98e2c407d7c6c99e4e0a6bf254d764d7f57`
- pre-merge protected main / PR base: `aae1e692774f7c10114d66fd79acb254c2aabfef`
- merge: guarded with the exact expected candidate head
- actual merge SHA: `84b130e728254d5ff8e1e0da2dcb4f0e9933f3d8`
- merge parent1: `aae1e692774f7c10114d66fd79acb254c2aabfef`
- merge parent2: `647cf98e2c407d7c6c99e4e0a6bf254d764d7f57`
- protected-main Run #476 / `36580435140`: event `push`, branch `main`, exact head `84b130e728254d5ff8e1e0da2dcb4f0e9933f3d8`, PASS 14/14

This evidence adopts SDIB-1.5 as the active M6 implementation baseline. It does **not** satisfy M6 Exit and does not admit P2.

## C3 boundary
Existing Canonical defines P2 high-level semantics and Core tables `assessment.factor_feature_set`, `assessment.attribution_run`, and `capability.adjusted_capability_estimate`. The implementation-level semantic gap remains fail-closed in #151.

## Rolling design
Program #149 requires one-milestone-ahead design. During active M6 implementation, M7/P3 is refined to task/interface/test detail using actual P2 implementation evidence; P3 implementation/admission remains forbidden until M6 protected-main Exit GO.

**Decision: ADOPTED — SDIB-1.5 / M6 task baseline. P2 remains NOT ADMITTED.**
