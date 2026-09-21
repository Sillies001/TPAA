# Evidence

`evidence/generated/` is reserved for CI/local execution evidence. Generated evidence is ignored by Git by default because it contains run timestamps and source revision metadata; release/milestone pipelines should archive it as an immutable build artifact.
