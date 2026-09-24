# M1-DATA-002 — Source Registry / Artifact Registration

## Scope

This task closes the SDIB-1.0.1 M1-DATA-002 minimum acceptance:

> 原始 bundle 与 Context artifact 均有 immutable ref/hash

The implementation builds deterministic immutable identities for every governed
M1 synthetic source bundle, its physical source artifact, and its fixture
context file.

## Boundary

This task deliberately does **not** persist Canonical registry rows yet.

That is required to avoid inventing data that belongs to later tasks:

- `registry.data_source` references `registry.training_session`, whose
  authoritative Session Time is owned by M1-DATA-003;
- the fixture evaluation-context file is not itself one of the allowed
  `registry.context_artifact.artifact_kind` values;
- M1-DATA-006 owns binding governed Rule Set / Metric Profile artifacts into the
  Evaluation Context and must not be pre-empted by a fabricated artifact kind.

Therefore M1-DATA-002 produces prepared deterministic registration identities
and an immutable registry index, while recording:

```text
database_persistence_executed = false
session_time_transform_executed = false
canonical_projection_executed = false
evaluation_context_binding_executed = false
canonical_context_artifact_kind_invented = false
```

## Immutable identities

Each of the eight governed fixture bundles receives:

- immutable bundle ref + aggregate input SHA-256;
- deterministic `source_id`;
- deterministic `source_stream_id`;
- immutable source-artifact ref + SHA-256;
- deterministic source-artifact object ID;
- immutable context-file ref + SHA-256;
- deterministic context object-ref ID.

IDs are UUIDv5 values derived solely from immutable logical identity. No wall
clock, host path, OS, locale, or random generator participates.

## Canonical compatibility

The prepared IDs correspond to future use of existing Canonical objects:

- `registry.data_source`
- `registry.source_stream`
- `registry.source_artifact`
- `registry.object_reference`

No new table or schema field is introduced.

The fixture context file remains an immutable object reference only. It is not
claimed to be a `ContextArtifactRefDTO` until M1-DATA-006 resolves actual
governed `RULE_SET` / `METRIC_PROFILE` artifacts.

## Acceptance command

```text
python tools/dev/tpaa_dev.py m1-source-registry-check
```

Windows/Linux CI archives exact evidence under
`evidence/m1-data-002/<platform>/source-registry.json`.
