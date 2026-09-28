# Implementation baseline index

The active software-development implementation baseline is **SDIB-1.3**.

Protected-main adoption evidence:
- SDIB-1.3 merge SHA: `bf8d7e8a2dae94ea78f3a7f6f859ccb391dd70d8`
- protected-main Run #416 / `36392479151`: PASS, 12/12 jobs
- baseline directory: `docs/baseline/SDIB-1.3/`
- main document SHA-256: `cf17b1ce7af3b80d81d40fd42d5d0967dda451043bfc1ae24b27662b6cbd098a`
- M4 task baseline SHA-256: `31b9450bb3fc9950146e798ad7b4dcbc18ef9332c86327212cca81bacd9e9ef5`
- parent implementation baseline: SDIB-1.2
- M3 Exit authority SHA: `53c591adbab1dea0618d0d3a727b0bf4638e00de`
- M3 Exit Run #414 / `36380613937`: PASS / GO
- Core baseline: CB-1.4.0
- DB schema: 1.6.0

SDIB-1.3 freezes M4 `P1 Longitudinal & Debrief Closure` into 21 Tasks / four coarse batches with exact 104 eligible / 12 excluded Catalog longitudinal membership.

C3 #122 is implemented as controlled machine authority `M4_LONGITUDINAL_DEBRIEF_AUTHORITY.json`. Its semantics are usable by dependent M4 LONG/OBS/API/GUI code only after the Baseline Lock containing that artifact is adopted on protected main with exact merge-SHA Hosted CI PASS.

Historical baselines remain for auditability. See `docs/reviews/SDIB-1.3_ADOPTION_REVIEW.md`.
