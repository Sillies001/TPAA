# Implementation baseline index

The candidate software-development implementation baseline for this branch is
**SDIB-1.3**. The repository's currently adopted protected-main predecessor is SDIB-1.2
until SDIB-1.3 completes exact-head PR and protected-main adoption.

- Candidate baseline directory: `docs/baseline/SDIB-1.3/`
- Candidate main document SHA-256: `cf17b1ce7af3b80d81d40fd42d5d0967dda451043bfc1ae24b27662b6cbd098a`
- M4 task baseline SHA-256: `31b9450bb3fc9950146e798ad7b4dcbc18ef9332c86327212cca81bacd9e9ef5`
- Parent implementation baseline: SDIB-1.2
- M3 Exit authority SHA: `53c591adbab1dea0618d0d3a727b0bf4638e00de`
- M3 Exit protected-main Run #414 / `36380613937`: PASS / GO
- Source design package: TPAA V8.0 / ED-2.0 Rebaseline R3.3
- Core baseline: CB-1.4.0

SDIB-1.3 is the post-M3 C1 refinement that freezes M4 `P1 Longitudinal & Debrief Closure`
into a 21-Task, four-batch backlog. It binds exact 104 eligible / 12 excluded Catalog
longitudinal membership while preserving CB-1.4.0 and DB schema 1.6.0.

C3 #122 is explicitly fail-closed for exact trend-profile/canonicalization and
longitudinal/debrief DTO semantics; SDIB-1.3 does not invent them.

Historical baselines remain for auditability.
See `docs/reviews/SDIB-1.3_ADOPTION_REVIEW.md`.
