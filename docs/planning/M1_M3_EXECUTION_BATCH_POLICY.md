# M1–M3 Coarse-Grained Execution Batch Policy

GitHub Issue #85 is the live governance anchor for this policy.

TPAA tracks implementation with no more than four open execution-batch Issues
per admitted milestone. SDIB Task IDs, minimum acceptance, dependencies and
protected-main evidence remain independently traceable inside each batch
acceptance matrix. A fine-grained Issue closed as `superseded` is not a claim
that its Task is complete.

## M1 batches

| Order | Issue | Scope | Depends on |
|---:|---:|---|---|
| 1 | #86 | World + representative Metric core product | admitted M1 Data Spine and WORLD-001..003 |
| 2 | #87 | Publication, persistence, API + replay backend | #86 protected-main PASS |
| 3 | #89 | Desktop vertical slice + Windows/Linux E2E | #87 protected-main PASS |
| 4 | #88 | Cross-platform qualification + M1 Exit | #86, #87 and #89 protected-main PASS |

Each batch normally produces one implementation branch, one PR, one hosted CI
run family and one protected-main verification. Focused local tests still run
throughout construction; the policy removes Task-by-Task PR/Run overhead, not
engineering feedback.

## M2 and M3

M2 execution Issues are created only after M1 Exit GO. M3 execution Issues are
created only after their SDIB prerequisite Gate. Each milestone starts directly
with at most four coarse execution batches and does not first import a large set
of open Task Issues.

Batch splitting is permitted only for a recorded safety, governance or hard
technical blocker. The split must preserve every Task ID and remaining
acceptance item and must be documented in #85 before execution diverges.
