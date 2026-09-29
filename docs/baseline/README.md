# Implementation baseline index

The active software-development implementation baseline is **SDIB-1.5**, adopted on protected main `84b130e728254d5ff8e1e0da2dcb4f0e9933f3d8` after PR #153 exact-head Run #475 and protected-main Run #476 both passed all 14 required jobs.

Adoption evidence:
- parent implementation baseline: SDIB-1.4
- adoption prerequisite protected-main SHA: `aae1e692774f7c10114d66fd79acb254c2aabfef`
- prerequisite protected-main Run #472 / `36556569965`: PASS, 14/14 jobs
- qualified PR #153 head: `647cf98e2c407d7c6c99e4e0a6bf254d764d7f57`
- qualified exact-head Run #475 / `36576098823`: PASS, 14/14 jobs
- adoption merge SHA: `84b130e728254d5ff8e1e0da2dcb4f0e9933f3d8`
- adoption merge parents: `aae1e692774f7c10114d66fd79acb254c2aabfef` + `647cf98e2c407d7c6c99e4e0a6bf254d764d7f57`
- protected-main Run #476 / `36580435140`: PASS, 14/14 jobs
- current capability: P1_M5_QUALIFIED; P2 remains not admitted
- Core baseline: CB-1.4.0
- DB schema: 1.6.0
- program policy: #149
- M6 tracking: #150
- P2 C3 authority closure: #151
- baseline directory: `docs/baseline/SDIB-1.5/`
- adopted main document SHA-256: `6e5ea15a6d2217837ea9ecac34a297e0880f1305a6aba77ef5e44275879fa646`
- adopted M6 task baseline SHA-256: `026b5718c8c603c1126b079ac5070283284ac6f291827b749dcdad0d779e7918`

SDIB-1.5 refines M6 `P2 Attribution Activation` into 17 Tasks / four coarse batches. P2 remains dormant until protected-main M6 Exit GO. P1 observations/releases remain immutable; P3-P6 remain inactive.

C3 #151 is the fail-closed blocker for exact P2 factor/reference/cohort representation, identifiability/uncertainty semantics, cross-layer P2 DTO projection and Release/evidence binding.

Program #149 adopts one-milestone-ahead rolling design: while M6 implementation is active, M7/P3 detailed design is refined from real implementation evidence without activating P3.

Historical baselines remain for auditability. See `docs/reviews/SDIB-1.5_ADOPTION_REVIEW.md`.
