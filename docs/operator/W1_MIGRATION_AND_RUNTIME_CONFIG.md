# W1 migration and runtime configuration operations

Status: W1 local closure candidate; no production deployment authorization.

## Governed Desktop and Service migration

`tpaa-admin migrate` operates only on an existing `tpaa.sqlite3`. It never creates,
deletes, or silently rebuilds a user database. Use `tpaa-admin init` only for an
explicit clean installation.

```text
tpaa-admin migrate plan --data-root <absolute-data-root> [--to 1.9.0]
tpaa-admin migrate verify --data-root <absolute-data-root>
tpaa-admin migrate apply --data-root <absolute-data-root> [--to 1.9.0]
tpaa-admin migrate resume --data-root <absolute-data-root>
tpaa-admin migrate rollback --data-root <absolute-data-root> --to <version>
tpaa-admin migrate status --data-root <absolute-data-root>
```

Supported graph: `1.6.0 -> 1.7.0 -> 1.8.0 -> 1.9.0`, bound to ACP-216,
ACP-219, and ACP-221. Each operation verifies its source authority, acquires an
exclusive migration lock, creates a SQLite online backup, writes an atomic journal,
and verifies the target authority. A non-empty relation introduced by a hop blocks
rollback. A failed or interrupted operation blocks a new apply/rollback until
`resume` succeeds.

Source checkouts discover historical snapshots under `migrations/authority`.
Installed layouts must pass an absolute `--migration-authority-root` which contains
the same frozen, hash-verified snapshots.

The same command surface supports PostgreSQL Service. The Service profile reads
connection information only from `TPAA_RUNTIME_CONFIG_FILE` (or the deprecated
environment compatibility path); a connection string is never accepted as a CLI
argument. Mutating commands require an absolute backup root. They acquire the
exclusive peer of the normal shared write gate, capture a real custom-format
`pg_dump`, persist an atomic journal, and then migrate one transaction per hop.

```text
tpaa-admin migrate plan --profile SERVICE --state-root <absolute-state-root>
tpaa-admin migrate verify --profile SERVICE --state-root <absolute-state-root>
tpaa-admin migrate apply --profile SERVICE --state-root <absolute-state-root> \
  --backup-root <absolute-backup-root>
tpaa-admin migrate resume --profile SERVICE --state-root <absolute-state-root>
tpaa-admin migrate rollback --profile SERVICE --state-root <absolute-state-root> \
  --backup-root <absolute-backup-root> --to <version>
tpaa-admin migrate status --profile SERVICE --state-root <absolute-state-root>
```

`resume` verifies the original backup and database identity before continuing.
Downgrade is blocked if any relation introduced by the reverted hop is non-empty.
Migration never bootstraps a missing database and never replaces a failed database
with a clean one.

## Shared runtime configuration document

Set `TPAA_RUNTIME_CONFIG_FILE` to an absolute path containing
`TPAA_RUNTIME_CONFIG_V1`. Both public Desktop and Service entry configuration
functions consume this schema. The document binds the product build, Core baseline,
DB migration head, authority directory, profile directories, identity file, and
storage backend.

Secrets are never embedded in this document. Service connection information and S3
credentials use `env://VARIABLE_NAME` references. Missing references, inline secret
values, relative paths, version drift, profile-field mixing, and unknown fields fail
closed.

Minimal Desktop example:

```json
{
  "schema": "TPAA_RUNTIME_CONFIG_V1",
  "profile": "DESKTOP",
  "product_build_version": "1.0.0",
  "core_baseline": "CB-1.5.0",
  "db_schema_version": "1.9.0",
  "authority_root": "C:/ProgramData/TPAA/authority/CB-1.5.0/canonical",
  "data_root": "C:/Users/operator/AppData/Local/TPAA"
}
```

Minimal Service example with local object storage:

```json
{
  "schema": "TPAA_RUNTIME_CONFIG_V1",
  "profile": "SERVICE",
  "product_build_version": "1.0.0",
  "core_baseline": "CB-1.5.0",
  "db_schema_version": "1.9.0",
  "authority_root": "/opt/tpaa/authority/CB-1.5.0/canonical",
  "object_root": "/var/lib/tpaa/control",
  "migration_state_root": "/var/lib/tpaa/migrations",
  "principals_file": "/etc/tpaa/principals.json",
  "database": {
    "backend": "POSTGRESQL",
    "conninfo_ref": "env://TPAA_SERVICE_CONNINFO_SECRET"
  },
  "object_store": {"backend": "LOCAL"}
}
```

The earlier environment-variable-only Service configuration is deprecated and is
retained only through the W2/W3 development window. It must be removed before the W3
exit gate and cannot be used as formal release evidence. `TPAA_RUNTIME_CONFIG_V1` is
the only W1 target configuration and explicitly carries `migration_state_root`.

## Product governance registries

`GovernanceRegistryService` is the engine-neutral Desktop/Service application
boundary for Context publish/replay/list/lookup/retire, aircraft configuration
create/review/list/snapshot, and aircraft lifecycle event record/list. Context bytes
are immutable governed objects. Deterministic identities, hashes, independent review,
and persistent audit apply to every mutation and replay.

`ReleaseManagementService` supplies engine-neutral list, CAS-protected withdraw, and
lineage-checked supersede behavior. `tpaa-admin release` exposes the Desktop operator
surface; Service transports reuse the same application boundary and PostgreSQL UoW.

## READY behavior

READY requires migration head/journal, authority closure, object store, identity, and
worker. The Service migration probe obtains a shared advisory lock: it remains
compatible with normal writes but fails while an exclusive migration/backup drain is
active. A pending/failed journal or active drain therefore forces `NOT_READY`.
