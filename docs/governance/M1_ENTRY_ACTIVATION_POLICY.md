# M1 Entry Activation Policy

## Purpose

This policy minimizes governance-only merge churn while preserving exact post-merge evidence.

The repository keeps a **static admission-candidate review** and lets the merged-main CI produce the final **M1 admission activation artifact** for the exact protected-`main` revision. This avoids a second review-only merge solely to rewrite the final commit SHA.

Machine policy: `docs/governance/M1_ENTRY_ACTIVATION_POLICY.json`.

## States

```text
M1_NOT_ADMITTED
        ↓ explicit role assignments
M1_ADMISSION_CANDIDATE
        ↓ PR Windows/Linux exact-manifest verification
M1_ADMISSION_CANDIDATE_VERIFIED
        ↓ merge + protected-main Run, all governed jobs success
M1_ADMITTED
```

Only the final state authorizes M1 implementation.

## Static candidate requirements

Before the final admission PR can be merged:

- M1 Primary WS owner is explicitly assigned;
- Golden independent reviewer is explicitly assigned;
- M1 Exit reviewer is explicitly assigned;
- Golden independence attestation is explicit;
- §19.1 conditions 1, 2, 3, 4, 5, 7, 8, 9 and 10 are PASS;
- condition 6 is `RUNTIME_VERIFY_REQUIRED`;
- `implementation_authorized=false`.

The final source revision cannot be known before merge, so condition 6 is completed by runtime manifest verification.

## PR verification

The pull-request run must generate Windows and Linux M1 Entry manifests for the same PR synthetic merge revision and verify all frozen authority hashes.

A successful PR activation check may produce only:

`M1_ADMISSION_CANDIDATE_VERIFIED`

It may not authorize implementation.

## Merged-main activation

After merge, the activation step runs inside the already-required `M0 Exit Review` status check, after its governed Windows/Linux, PostgreSQL, and logical-equivalence dependencies have succeeded.

It verifies that both platform manifests are bound to the exact merged-main `github.sha` and retain:

- CB-1.4.0;
- DB schema 1.6.0;
- Baseline Lock SHA-256;
- dependency-lock SHA-256;
- P1 Metric Catalog SHA-256;
- Stage authority SHA-256;
- DTO authority SHA-256.

Only then may the generated activation artifact state:

```text
decision = M1_ADMITTED
implementation_authorized = true
conditions_passed_after_runtime_verification = 10
```

## Fail-closed rules

Admission fails closed on any of the following:

- missing role identity;
- missing Golden independence attestation;
- Windows/Linux source-revision mismatch;
- authority-hash mismatch;
- platform-profile mismatch;
- inconsistent static review state.

## Evidence

Final machine evidence path:

`evidence/m1-entry/activation.json`

Artifact naming:

`tpaa-m1-entry-activation-<source_revision>`

The committed review remains the admission candidate. The merged-main activation artifact is the final machine evidence that authorizes M1 implementation.
