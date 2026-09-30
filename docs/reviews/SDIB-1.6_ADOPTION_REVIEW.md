# SDIB-1.6 Adoption Candidate / M7 Refinement Review

## Review identity
- **Change class:** C1 — post-M6 backlog refinement.
- **Candidate implementation baseline:** SDIB-1.6; parent SDIB-1.5.
- **Tracking:** #168; program #149; P3 C3 #169; M8 runway #170.
- **Core baseline / DB schema:** CB-1.4.0 / 1.6.0.
- **Document SHA-256:** `7be4a44ab24a0384c45dd4f2693cf6d7c070e71d73d5111fe620344649ba5913`.
- **M7 manifest SHA-256:** `29788e3eb003ea8f1411b8e8b72185f3a3bf3f107bc5aca4721e2225e16e2800`.

## Entry evidence
Protected main `892e4a64a321be9c7252b66207a7d1d90a6ce98d`, Run #494 / `36697493917` is PASS 14/14. Final M6 Exit is GO with `P2_M6_QUALIFIED`, `p2_admitted=true` and `failed_acceptance=[]`.

## Candidate refinement
SDIB-1.6 freezes 18 M7 tasks in four coarse batches. Existing DB 1.6.0 already contains the four P3 product carriers, so this C1 refinement creates no schema or shadow tables.

## C3 boundary
#169 remains fail-closed. SDIB-1.6 does not select a P3 model algorithm/plugin, validation/OOD threshold or intrinsic-claim threshold. Non-null model/surface URI fields must map to sealed ACTIVE `registry.object_reference.managed_uri` with matching governed hashes.

## Capability boundary
P1/P2 remain admitted immutable layers. P3 remains NOT ADMITTED until protected-main exact M7 Exit GO. P4-P6 remain inactive. P2 NOT_IDENTIFIABLE is valid evidence but not a numeric P3 training target; historical P3 construction/replay may not use current/latest/default identity resolution.

## Rolling design
#170 is the M8/P4-P5 design-only runway required by #149 while M7 is active. It does not authorize P4/P5 implementation.

## Protected-main adoption
- qualified candidate head: `5b1d758df75b14dfccbf4e715e1d8baaf9e63117`
- exact-head Run #496 / `36706668280`: 14/14 PASS
- pre-merge protected main: `892e4a64a321be9c7252b66207a7d1d90a6ce98d`
- actual merge SHA: `d590a3a9a05db1a8b566b2dafec05e93028436e5`
- merge parents: `892e4a64a321be9c7252b66207a7d1d90a6ce98d` + `5b1d758df75b14dfccbf4e715e1d8baaf9e63117`
- protected-main Run #497 / `36709415054`: 14/14 PASS

## Adoption decision
**ADOPTED** — SDIB-1.6 is the active M7 implementation baseline. P3 remains NOT ADMITTED until M7 Exit GO.
