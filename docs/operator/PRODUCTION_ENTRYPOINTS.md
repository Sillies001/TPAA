# TPAA production entry points

This document describes the minimum configuration contract for the durable
Desktop and Service entry points. Qualification fixtures and in-memory
repositories are not valid product configuration.

## Desktop

From a source checkout, use the unified developer command:

```text
python tools/dev/tpaa_dev.py run-gui
```

An installed project exposes the `tpaa-desktop` GUI script. It also accepts an
explicit absolute data root:

```text
tpaa-desktop --data-root <absolute-path>
```

The script, the local backend child, and packaged PIQB Desktop launchers all
delegate to the public `tpaa_desktop` production factory. A non-editable wheel
deployment must set `TPAA_AUTHORITY_ROOT` as described below.

`TPAA_DESKTOP_DATA_ROOT` may be set to an absolute path. When it is omitted,
TPAA uses the platform per-user data location:

- Windows: `%LOCALAPPDATA%\TPAA` (falling back to `%APPDATA%`, then the home directory)
- Linux: `$XDG_DATA_HOME/tpaa` (falling back to `~/.local/share/tpaa`)

The first startup creates and verifies:

```text
<data-root>/tpaa.sqlite3   DB 1.9 / CB-1.5.0 authority
<data-root>/objects/      managed product object storage
```

An existing database is verified and never silently replaced. A relative data
root is rejected.

## Service

From a source checkout, use the unified developer command:

```text
python tools/dev/tpaa_dev.py run-api --host 127.0.0.1 --port 8000
```

An installed project exposes the equivalent `tpaa-service` console script.
The packaged PIQB launchers continue to configure their own application module
path and runtime root.

Before binding a socket, validate the same production composition and all live
dependencies:

```text
tpaa-service --check-config
python tools/dev/tpaa_dev.py run-api --check-config
```

The command returns secret-free `TPAA_SERVICE_PREFLIGHT_V1` JSON and exits with
status 2 when configuration, PostgreSQL, object storage, authority, worker, or
readiness validation fails.

The public Service entry point accepts one runtime-document pointer:

| Variable | Meaning |
|---|---|
| `TPAA_RUNTIME_CONFIG_FILE` | Absolute path to strict `TPAA_RUNTIME_CONFIG_V1` configuration |
| `TPAA_AUTHORITY_ROOT` | Absolute `CB-1.5.0/canonical` directory when an installed runtime cannot discover authority |

Database and S3 secrets are `env://NAME` references inside the document. Inline
secrets and the former direct environment configuration are rejected. Service
identity must be `OIDC_MTLS`, with an HTTPS issuer/JWKS URI, client CA bundle,
SPIFFE allowlist, and reloadable revocation registry.

Service uses the local object backend by default. To select an S3-compatible
backend, install the `service-s3` extra and configure it in the document:

| Runtime document field | Meaning |
|---|---|
| `object_store.backend` | `LOCAL` or `S3` |
| `object_store.bucket` | Existing governed bucket |
| `object_store.prefix` | Governed key prefix |
| `object_store.endpoint_url` | Optional S3-compatible endpoint |
| `object_store.region` | Explicit region |
| `object_store.access_key_id_ref` | `env://` secret reference |
| `object_store.secret_access_key_ref` | `env://` secret reference |

The adapter stores TPAA logical URIs below the configured prefix and verifies
TPAA-owned SHA-256 metadata/bytes rather than treating an S3 ETag as content
identity. Immutable writes use conditional create and reject a conflicting
existing object. Bucket readiness is checked before runtime composition.

Business roles are `TRAINEE`, `INSTRUCTOR`, `EVALUATOR`, `TRAINING_MANAGER`,
`UNIT_ANALYST`, `MAINTENANCE_ENGINEERING`, `DATA_ENGINEER`, `ADMINISTRATOR`, and
`MODEL_REVIEWER`. Legacy Canonical role names remain view projections only.

Missing identity configuration, unknown roles, invalid hashes, privilege
escalation, DB authority mismatch, or unavailable object storage fail closed.
Inspect the current secret-free permission wiring and unresolved gaps with:

```text
tpaa-admin permissions
```

The command reports the active policy hash, `COMPLETE`, and default `DENY`.
Model release, product publish, publication override, and plugin install require
separate maker/checker identities and one-time exact-target approval.

## Desktop local identity

The loopback bearer token protects only the GUI-owned transport channel. Issue a
short-lived OS-account/device assignment with `tpaa-admin identity-issue`, then set
`TPAA_DESKTOP_IDENTITY_FILE` and `TPAA_DESKTOP_IDENTITY_KEY_REF`. Missing or tampered
identity leaves business routes closed while health/readiness remain available.

## Packaged PIQB probes

Target Service probes must use the same short-lived OIDC token and mTLS identity as
other callers. Static fingerprint credentials remain qualification compatibility
inputs only and are not accepted by the public Service configuration.

The PIQB product package must not contain `app/tests/`, fixture directories,
the legacy `ProductRuntimeConfig`, a SYSTEM all-privilege identity fallback,
or a packaging-only copy of the Desktop/Service production composition. Its
launchers and probes delegate to the public `tpaa_desktop` and `tpaa_service`
factories; long-running commands delegate to their public `main` entry points.

## Desktop administration

Installed environments expose the following fail-closed commands:

```text
tpaa-admin init --data-root <absolute-path>
tpaa-admin verify --data-root <absolute-path>
tpaa-admin status --data-root <absolute-path>
tpaa-admin source-stage --data-root <absolute-path> --artifact-id <uuid> --source-file <absolute-path>
tpaa-admin backup --data-root <absolute-path> --destination <absolute-new-path>
tpaa-admin restore --data-root <absolute-clean-path> --backup <absolute-path>
```

Omitting `--data-root` uses the same platform default as `tpaa-desktop`.
`init` is idempotent for a valid DB 1.9 instance but never replaces an invalid
database. Backup destinations must not exist. Restore requires a missing
database and an absent or empty object root. Command output never includes
database credentials or bearer material.

Desktop production write transactions and `tpaa-admin backup` share one
cross-process write-quiescence lock below the object root. A backup therefore
captures its SQLite copy and managed-object inventory while production DB
writes are paused. Backup schema V2 records the database hash, object inventory
hash, and their combined snapshot watermark; lock and atomic-temporary files
are excluded. After the final backup directory is in place, TPAA re-verifies
the V2 payload and atomically records a local backup-status marker. `tpaa-admin
status` re-verifies the referenced manifest and payload before reporting
`VERIFIED`; missing, moved, or modified backup material reports `INVALID`.
The external manifest path is never returned by the command or API. Restore
verifies all three identities before touching a clean target and records the
same verified status for the restored Desktop data root.

`create_managed_service_production_backup` now acquires the exclusive
PostgreSQL advisory write gate used by every production Service write UoW,
records a secret-free transaction snapshot and WAL LSN, and holds the gate
across authority verification, `pg_dump`, and object inventory capture. The
lower-level `create_service_production_backup` still accepts an externally
enforced drain for deployment integrations, but the managed wrapper should be
preferred. Direct/internal UoWs that deliberately omit the production gate are
not covered by this protocol and must not be used as product mutation paths.

Service restore accepts only `staging_conninfo` and `staging_object_root`, and
requires `staging_target_confirmed=True`. It returns a
`TPAA_SERVICE_STAGING_RESTORE_V1` receipt whose activation state is always
`NOT_ACTIVATED`. `activate_verified_service_staging` accepts only that verified
snapshot, write-disables the target, asks an injected deployment traffic-switch
adapter to route traffic, performs a health check, and only then enables target
writes. A pre-enable failure routes traffic back to the previous generation.
The repository includes an atomic-file reference adapter for local qualification;
real load balancer/service-discovery integration remains deployment-specific.
Installed Service qualification additionally requires the operator-provided
values below. They must be set only after the stated actions have actually
completed:

```text
TPAA_SERVICE_WRITE_DRAIN_CONFIRMATION=WRITE_DRAIN_ENFORCED
TPAA_SERVICE_RESTORE_STAGING_CONFIRMATION=CLEAN_STAGING_TARGET
```

`/runtime/observability` now publishes only aggregate, low-cardinality fields:
job counts by frozen state, bounded/sanitized failure-code counts, active jobs,
adapter failures, access denials, DB/object scan latency, object count/bytes,
filesystem capacity, and verified backup status/age. It does not return job
IDs, principal keys, object paths, connection strings, backup paths, source
payloads, or exception text. Service backup status remains
`EXTERNAL_GOVERNANCE_REQUIRED` until a deployment-level backup registry is
implemented.

`/runtime/metrics` projects the same governed subset as Prometheus text format
and is protected by the same unified Service authentication middleware as all
other runtime routes. Labels are limited to frozen job states, sanitized reason
codes, and bounded backup states; identities, paths, payloads and credentials
are never labels. Service collection is cached for five seconds to bound repeat
scrape cost. Alert thresholds, retention and backup-age SLA remain deployment
policy rather than hard-coded product behavior.

`source-stage` copies one non-empty UTF-8 Source document (maximum 64 MiB) into
the Desktop managed object root and returns a strict `source_artifact` object:
`logical_uri`, `artifact_sha256`, and `byte_size`. The same artifact UUID may
be replayed only with identical bytes. Production `BUILD_P1_RELEASE` jobs must
send this object and the returned `source_import_binding`; inline `source_json`,
unmanaged/file URIs, unknown reference fields, hash/size drift, and attempts to
overwrite an artifact UUID fail closed. Source bytes are materialized only in
the isolated worker message after the parent process verifies the managed
object; the durable job identity remains the immutable reference payload.

This is the first managed-object ingress slice. Service may now persist these
objects through the S3-compatible backend above; a streaming HTTP upload API,
native decoder isolation, and any new Source family remain outside the current
approved scope.

No production `migrate` command is exposed yet. The current migration code is a
governed engineering harness rather than an approved in-place product API;
presenting it as an operator command would create an unsafe authority bypass.
