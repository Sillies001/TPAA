# M1-DATA-006 — Evaluation Context resolver

## Scope

M1-DATA-006 resolves the governed M1 synthetic Evaluation Context into an
immutable Basic Flight context view. It consumes the existing Canonical
contracts rather than defining new Context, DTO, Stage, Metric, or persistence
semantics.

The implementation owner is `src/tpaa_context`.

## Frozen authority contract

The resolver follows the existing detailed design and CB-1.4.0 authority:

- `EvaluationContextDTO` defines the exact context projection vocabulary;
- `ContextArtifactRefDTO` defines immutable artifact-ref fields;
- `context.evaluation_context` remains the persistence authority;
- `context.context_artifact_binding` permits the existing `RULE_SET` and
  `METRIC_PROFILE` binding roles;
- `BASIC_FLIGHT_V1` is selected from `STAGE_REGISTRY 1.1.0`;
- no `STAGE_PROFILE` persistence binding role is invented.

The controlled M1 Basic profile is the frozen context version
`M1-BASIC-CONTEXT-1.0.0`. The controlled metric profile is the versioned
fixture token `M1_BASIC_AIR_PROFILE_V1`.

## Immutable resolution

For each of the eight governed fixtures the resolver:

1. reuses the already-governed Source Registry context-file identity/hash;
2. validates the canonical non-nil `context_id`;
3. binds `RULE_SET` to frozen `CORE_RULES` under `CB-1.4.0`;
4. binds `METRIC_PROFILE` to the exact embedded versioned metric-profile
   object and its deterministic content hash;
5. validates `BASIC_FLIGHT_V1` against the generated Stage profile and the
   frozen Stage Registry hash;
6. stable-sorts artifact refs by `binding_role`;
7. emits a deterministic logical hash for replay evidence.

The controlled fixture has no separate metric-profile version field, so its
versioned profile identifier `M1_BASIC_AIR_PROFILE_V1` is carried as the
required M1 `metric_profile_version` token. This is fixture-contract
consumption, not a new Canonical semantic definition.

## CR-006 replay behavior

`BF_M1_REPLAY_V1` intentionally contains simulated future values in
`current_refs` while preserving the historical values in `frozen_refs`.

The resolver must use the exact frozen/context values and must never fall back to
current/latest values. Acceptance therefore requires:

- exactly one fixture using `frozen_refs`;
- exactly one fixture where `current_refs` differs;
- `current_latest_fallback_used = false`.

This directly exercises CR-006 Context Immutability.

## Hard boundary

This task does **not**:

- persist `context.evaluation_context`;
- persist `registry.context_artifact` or
  `context.context_artifact_binding`;
- create a `STAGE_PROFILE` binding enum/value;
- project Episode/Stage/World products;
- execute Metric logic;
- implement M1-DATA-007 lineage/quality propagation.

The already-completed M1-C Episode / Stage / World design remains the parallel
one-wave-ahead runway. M1-D/M1-E detailed design is not advanced two waves ahead
by this task.

## Evidence

The governed acceptance command is:

`python tools/dev/tpaa_dev.py m1-evaluation-context-check`

Windows/Linux CI archives:

`evidence/m1-data-006/<platform>/evaluation-context.json`

Acceptance requires eight replay-stable context resolutions, 16 immutable
artifact refs (two per fixture), exact Basic/Stage/Metric profile selection,
frozen-reference replay behavior, and no downstream persistence/Stage/World/
Metric execution.
