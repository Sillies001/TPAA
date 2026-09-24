# M1-WORLD-003 Stage quality/status

## Authority and product boundary

This implementation enriches the governed M1-WORLD-002 `BASIC_FLIGHT_V1`
Stage projection with the four fields required by `episode.episode_stage` and
`STAGE_REGISTRY 1.1.0`: `stage_status`, `coverage`, `confidence`, and
`detector_version`. It is a separate product layer, so the WORLD-002 projector,
Stage identity, Stage order, and half-open boundaries remain unchanged.

The first controlled slice accepts only the complete authoritative official
marker sequence spanning the whole Basic Episode. Each published Stage
therefore has:

- `stage_status = VALID`
- `coverage = 1.0`
- `confidence = 1.0`
- `detector_version = M1_BASIC_FLIGHT_STAGE_PROJECTOR_V1`

Coverage here means coverage of the Stage boundary evidence by the governed
official markers. It is not Canonical channel coverage and is not Metric
coverage or confidence.

## Fail-closed behavior

Status and detector version must be non-empty. Coverage and confidence must be
finite numbers in the closed interval `[0,1]`. Invalid values fail with a
stable `StageQualityError` code. WORLD-002 validation still rejects invalid
marker sequences and boundaries before quality enrichment occurs.

## Hard boundary

This task does not persist rows, revise or supersede a Stage, compute logical
hashes, attach immutable evidence references, construct World products, or run
Metric logic. Those later tasks remain explicitly false in product and CI
evidence.
