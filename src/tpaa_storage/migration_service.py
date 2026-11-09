"""Governed SQLite/PostgreSQL migration services for production administration.

The service deliberately consumes the frozen migration authority snapshots instead
of inferring an old schema from the current model.  Every mutation is preceded by a
verified backup and recorded in an atomically replaced sidecar journal.  Existing
databases are never bootstrapped or rebuilt by this module.
"""

from __future__ import annotations

import hashlib
import json
import os
import sqlite3
import uuid
from collections.abc import Callable, Iterator, Mapping, Sequence
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import UTC, datetime
from importlib import import_module
from pathlib import Path
from typing import Any

from tpaa_platform.filesync import atomic_replace_bytes

from .bootstrap import (
    BOOTSTRAP_MANIFEST_TABLE,
    CORE_MODEL_ARTIFACT_ID,
    POSTGRES_ENGINE_PROFILE,
    BootstrapError,
    BootstrapVerification,
    _configure_sqlite,
    _load_authority,
    _postgres_catalog_hash_query,
    _postgres_create_statements,
    _postgres_expected_tables,
    _postgres_table_order,
    _schema_fingerprint,
    _SchemaAuthority,
    _sqlite_create_statements,
    _verify_connection,
)
from .postgres_repository import SERVICE_WRITE_GATE_LOCK_ID

MIGRATION_RESULT_SCHEMA = "TPAA_MIGRATION_RESULT_V1"
MIGRATION_JOURNAL_SCHEMA = "TPAA_MIGRATION_JOURNAL_V1"
TARGET_SCHEMA_VERSION = "1.9.0"
SUPPORTED_SCHEMA_VERSIONS = ("1.6.0", "1.7.0", "1.8.0", "1.9.0")

_HISTORICAL_AUTHORITY: Mapping[str, tuple[str, str, str]] = {
    "1.6.0": (
        "CORE_LOGICAL_MODEL_DB_1_6_0.json",
        "cfde6638e6899167267375c899bff2f04a490ce12f32e0005be4e15dda956245",
        "9920b59601d8441f883879e813164f33ee5c02db81aa5e1b759e3a1772469e51",
    ),
    "1.7.0": (
        "CORE_LOGICAL_MODEL_DB_1_7_0.json",
        "dd8461ff572338006455f7b6eac5325900c60640f5d163c3b61c3f5bd5767f74",
        "a55ccc5f75d128c4dc3c3208064596eeb2dda7ffaf340d87726a22d4b62f93c6",
    ),
    "1.8.0": (
        "CORE_LOGICAL_MODEL_DB_1_8_0.json",
        "cbb15c1e0029be45213e4d7ab57a78fac47d7cc09c4627a9c388fafdadd2d44e",
        "2f3690d5e74e585a34ae35fdef9fb1e0cccb5504c6983d0c97417bb6a106b389",
    ),
}


class MigrationServiceError(RuntimeError):
    """A migration operation failed closed."""

    def __init__(self, reason: str, detail: str) -> None:
        self.reason = reason
        self.detail = detail
        super().__init__(f"MIGRATION_FAIL reason={reason} detail={detail}")


@dataclass(frozen=True, slots=True)
class MigrationHop:
    proposal: str
    source_version: str
    target_version: str
    direction: str
    affected_relations: tuple[str, ...]

    def payload(self) -> dict[str, object]:
        return {
            "proposal": self.proposal,
            "source_version": self.source_version,
            "target_version": self.target_version,
            "direction": self.direction,
            "affected_relations": list(self.affected_relations),
        }


@dataclass(frozen=True, slots=True)
class MigrationPlan:
    observed_version: str
    target_version: str
    direction: str
    hops: tuple[MigrationHop, ...]

    def payload(self) -> dict[str, object]:
        return {
            "schema": MIGRATION_RESULT_SCHEMA,
            "command": "plan",
            "status": "NOOP" if not self.hops else "PLANNED",
            "observed_version": self.observed_version,
            "target_version": self.target_version,
            "direction": self.direction,
            "requires_backup": bool(self.hops),
            "hops": [hop.payload() for hop in self.hops],
        }


@dataclass(frozen=True, slots=True)
class MigrationStatus:
    schema_version: str
    verified: bool
    target_version: str
    at_head: bool
    journal_state: str
    pending_target_version: str | None

    def payload(self, *, command: str = "status") -> dict[str, object]:
        return {
            "schema": MIGRATION_RESULT_SCHEMA,
            "command": command,
            "status": "READY" if self.verified and self.at_head else "NOT_READY",
            "schema_version": self.schema_version,
            "migration_head": self.target_version,
            "at_migration_head": self.at_head,
            "authority_verified": self.verified,
            "journal_state": self.journal_state,
            "pending_target_version": self.pending_target_version,
        }


@dataclass(frozen=True, slots=True)
class _Step:
    proposal: str
    source: str
    target: str


_STEPS = (
    _Step("ACP-216", "1.6.0", "1.7.0"),
    _Step("ACP-219", "1.7.0", "1.8.0"),
    _Step("ACP-221", "1.8.0", "1.9.0"),
)


def _utc_now() -> str:
    return datetime.now(tz=UTC).isoformat().replace("+00:00", "Z")


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _required_text(value: object, *, field: str) -> str:
    if not isinstance(value, str) or not value or value != value.strip():
        raise MigrationServiceError("JOURNAL_INVALID", f"{field} must be text")
    return value


def _load_migration_authority(
    version: str,
    *,
    current_authority_root: Path,
    migration_authority_root: Path,
) -> _SchemaAuthority:
    if version == TARGET_SCHEMA_VERSION:
        authority = _load_authority(authority_root=current_authority_root)
    else:
        metadata = _HISTORICAL_AUTHORITY.get(version)
        if metadata is None:
            raise MigrationServiceError("UNSUPPORTED_SCHEMA_VERSION", f"version={version}")
        filename, expected_hash, lock_hash = metadata
        path = migration_authority_root / filename
        if not path.is_file():
            raise MigrationServiceError("MIGRATION_AUTHORITY_MISSING", f"artifact={filename}")
        raw = path.read_bytes()
        actual_hash = hashlib.sha256(raw).hexdigest()
        if actual_hash != expected_hash:
            raise MigrationServiceError(
                "MIGRATION_AUTHORITY_HASH_MISMATCH", f"artifact={filename}"
            )
        payload: object = json.loads(raw.decode("utf-8"))
        if not isinstance(payload, Mapping):
            raise MigrationServiceError("MIGRATION_AUTHORITY_INVALID", f"artifact={filename}")
        tables = payload.get("tables")
        core_baseline = payload.get("core_baseline")
        if (
            payload.get("db_schema_version") != version
            or not isinstance(tables, Mapping)
            or not tables
            or not isinstance(core_baseline, str)
            or not core_baseline
        ):
            raise MigrationServiceError("MIGRATION_AUTHORITY_INVALID", f"artifact={filename}")
        authority = _SchemaAuthority(
            schema_version=version,
            core_baseline=core_baseline,
            authority_sha256=expected_hash,
            baseline_lock_sha256=lock_hash,
            tables=tables,
        )
    if authority.schema_version != version:
        raise MigrationServiceError("AUTHORITY_VERSION_MISMATCH", f"expected={version}")
    return authority


class SQLiteMigrationService:
    """Apply the approved DB 1.6 -> 1.9 graph to one explicit SQLite file."""

    def __init__(
        self,
        database: Path,
        *,
        current_authority_root: Path,
        migration_authority_root: Path,
    ) -> None:
        self.database = database.expanduser().resolve(strict=False)
        self.current_authority_root = current_authority_root.expanduser().resolve(
            strict=False
        )
        self.migration_authority_root = migration_authority_root.expanduser().resolve(
            strict=False
        )
        state_root = self.database.parent / ".tpaa-migrations"
        self.journal_path = state_root / f"{self.database.name}.journal.json"
        self.lock_path = state_root / f"{self.database.name}.lock"
        self.backup_root = state_root / "backups"
        self._authorities: dict[str, _SchemaAuthority] = {}

    def _require_database(self) -> None:
        if not self.database.is_file():
            raise MigrationServiceError(
                "DATABASE_NOT_FOUND",
                "migration refuses to bootstrap or rebuild a missing database",
            )

    def _authority(self, version: str) -> _SchemaAuthority:
        cached = self._authorities.get(version)
        if cached is not None:
            return cached
        authority = _load_migration_authority(
            version,
            current_authority_root=self.current_authority_root,
            migration_authority_root=self.migration_authority_root,
        )
        self._authorities[version] = authority
        return authority

    def _observed_version(self) -> str:
        self._require_database()
        try:
            connection = sqlite3.connect(str(self.database))
            try:
                row = connection.execute(
                    f'SELECT schema_version FROM "{BOOTSTRAP_MANIFEST_TABLE}" '
                    "WHERE singleton=1"
                ).fetchone()
            finally:
                connection.close()
        except sqlite3.DatabaseError as exc:
            raise MigrationServiceError("MANIFEST_UNAVAILABLE", str(exc)) from exc
        if row is None or str(row[0]) not in SUPPORTED_SCHEMA_VERSIONS:
            raise MigrationServiceError(
                "UNSUPPORTED_SCHEMA_VERSION", f"observed={None if row is None else row[0]!r}"
            )
        return str(row[0])

    def verify(self) -> BootstrapVerification:
        version = self._observed_version()
        authority = self._authority(version)
        connection = sqlite3.connect(str(self.database))
        try:
            _configure_sqlite(connection, file_backed=True, set_wal=False)
            return _verify_connection(
                connection,
                authority=authority,
                expected_journal_mode="wal",
            )
        except (sqlite3.DatabaseError, BootstrapError) as exc:
            raise MigrationServiceError("DATABASE_VERIFY_FAILED", str(exc)) from exc
        finally:
            connection.close()

    def _relations(self, source: str, target: str) -> tuple[str, ...]:
        source_names = set(self._authority(source).tables)
        target_names = tuple(self._authority(target).tables)
        relations = tuple(name for name in target_names if name not in source_names)
        if not relations:
            raise MigrationServiceError(
                "EMPTY_MIGRATION_STEP", f"source={source} target={target}"
            )
        removed = sorted(source_names - set(target_names))
        if removed:
            raise MigrationServiceError(
                "NON_ADDITIVE_AUTHORITY_STEP", f"removed={removed!r}"
            )
        return relations

    def plan(self, target_version: str = TARGET_SCHEMA_VERSION) -> MigrationPlan:
        if target_version not in SUPPORTED_SCHEMA_VERSIONS:
            raise MigrationServiceError(
                "UNSUPPORTED_TARGET_VERSION", f"target={target_version}"
            )
        observed = self._observed_version()
        source_index = SUPPORTED_SCHEMA_VERSIONS.index(observed)
        target_index = SUPPORTED_SCHEMA_VERSIONS.index(target_version)
        if source_index == target_index:
            return MigrationPlan(observed, target_version, "NONE", ())
        direction = "UP" if target_index > source_index else "DOWN"
        selected: list[MigrationHop] = []
        if direction == "UP":
            steps: Sequence[_Step] = _STEPS[source_index:target_index]
            for step in steps:
                selected.append(
                    MigrationHop(
                        step.proposal,
                        step.source,
                        step.target,
                        direction,
                        self._relations(step.source, step.target),
                    )
                )
        else:
            steps = tuple(reversed(_STEPS[target_index:source_index]))
            for step in steps:
                selected.append(
                    MigrationHop(
                        step.proposal,
                        step.target,
                        step.source,
                        direction,
                        self._relations(step.source, step.target),
                    )
                )
        return MigrationPlan(observed, target_version, direction, tuple(selected))

    def _read_journal(self) -> dict[str, object] | None:
        if not self.journal_path.is_file():
            return None
        try:
            value: object = json.loads(self.journal_path.read_text(encoding="utf-8"))
        except Exception as exc:
            raise MigrationServiceError("JOURNAL_UNREADABLE", "invalid JSON") from exc
        if not isinstance(value, dict) or value.get("schema") != MIGRATION_JOURNAL_SCHEMA:
            raise MigrationServiceError("JOURNAL_INVALID", "schema mismatch")
        return value

    def _write_journal(self, journal: Mapping[str, object]) -> None:
        self.journal_path.parent.mkdir(parents=True, exist_ok=True)
        payload = json.dumps(journal, indent=2, sort_keys=True) + "\n"
        atomic_replace_bytes(self.journal_path, payload.encode("utf-8"))

    @contextmanager
    def _exclusive_lock(self) -> Iterator[None]:
        self.lock_path.parent.mkdir(parents=True, exist_ok=True)
        stream = self.lock_path.open("a+b")
        locked = False
        try:
            stream.seek(0, os.SEEK_END)
            if stream.tell() == 0:
                stream.write(b"0")
                stream.flush()
            stream.seek(0)
            try:
                if os.name == "nt":
                    import msvcrt

                    msvcrt.locking(stream.fileno(), msvcrt.LK_NBLCK, 1)
                else:
                    import fcntl

                    fcntl.flock(  # type: ignore[attr-defined]
                        stream.fileno(),
                        fcntl.LOCK_EX | fcntl.LOCK_NB,  # type: ignore[attr-defined]
                    )
                locked = True
            except OSError as exc:
                raise MigrationServiceError(
                    "MIGRATION_LOCKED", "another migration operation is active"
                ) from exc
            yield
        finally:
            try:
                if locked:
                    stream.seek(0)
                    if os.name == "nt":
                        import msvcrt

                        msvcrt.locking(stream.fileno(), msvcrt.LK_UNLCK, 1)
                    else:
                        import fcntl

                        fcntl.flock(  # type: ignore[attr-defined]
                            stream.fileno(), fcntl.LOCK_UN  # type: ignore[attr-defined]
                        )
            finally:
                stream.close()

    def _backup(self, operation_id: str) -> tuple[Path, str]:
        self.backup_root.mkdir(parents=True, exist_ok=True)
        destination = self.backup_root / f"{self.database.name}.{operation_id}.sqlite3"
        if destination.exists():
            raise MigrationServiceError("BACKUP_COLLISION", "backup already exists")
        try:
            source_connection = sqlite3.connect(str(self.database))
            destination_connection = sqlite3.connect(str(destination))
            try:
                source_connection.backup(destination_connection)
            finally:
                destination_connection.close()
                source_connection.close()
        except sqlite3.DatabaseError as exc:
            destination.unlink(missing_ok=True)
            raise MigrationServiceError("BACKUP_FAILED", str(exc)) from exc
        return destination, _sha256_file(destination)

    def _update_manifest(
        self,
        connection: sqlite3.Connection,
        authority: _SchemaAuthority,
    ) -> None:
        physical_hash = _schema_fingerprint(_sqlite_create_statements(authority))
        connection.execute(
            f'''UPDATE "{BOOTSTRAP_MANIFEST_TABLE}"
                SET schema_version=?, core_baseline=?, authority_artifact_id=?,
                    authority_sha256=?, baseline_lock_sha256=?,
                    physical_schema_sha256=?
                WHERE singleton=1''',
            (
                authority.schema_version,
                authority.core_baseline,
                CORE_MODEL_ARTIFACT_ID,
                authority.authority_sha256,
                authority.baseline_lock_sha256,
                physical_hash,
            ),
        )

    def _apply_hop(self, hop: MigrationHop) -> None:
        source = self._authority(hop.source_version)
        target = self._authority(hop.target_version)
        connection = sqlite3.connect(str(self.database))
        try:
            _configure_sqlite(connection, file_backed=True, set_wal=False)
            _verify_connection(
                connection,
                authority=source,
                expected_journal_mode="wal",
            )
            connection.execute("BEGIN IMMEDIATE")
            if hop.direction == "UP":
                target_statements = dict(
                    zip(target.tables, _sqlite_create_statements(target), strict=True)
                )
                for relation in hop.affected_relations:
                    connection.execute(target_statements[relation])
            else:
                nonempty = []
                for relation in hop.affected_relations:
                    row = connection.execute(
                        f'SELECT COUNT(*) FROM "{relation}"'
                    ).fetchone()
                    if row is None or int(row[0]) != 0:
                        nonempty.append(relation)
                if nonempty:
                    raise MigrationServiceError(
                        "ROLLBACK_BLOCKED_NONEMPTY_RELATION",
                        f"relations={nonempty!r}",
                    )
                for relation in reversed(hop.affected_relations):
                    connection.execute(f'DROP TABLE "{relation}"')
            self._update_manifest(connection, target)
            _verify_connection(
                connection,
                authority=target,
                expected_journal_mode="wal",
            )
            connection.commit()
        except MigrationServiceError:
            connection.rollback()
            raise
        except (sqlite3.DatabaseError, BootstrapError) as exc:
            connection.rollback()
            raise MigrationServiceError("MIGRATION_HOP_FAILED", str(exc)) from exc
        finally:
            connection.close()

    def _new_journal(self, plan: MigrationPlan) -> dict[str, object]:
        operation_id = str(uuid.uuid4())
        backup, backup_hash = self._backup(operation_id)
        now = _utc_now()
        return {
            "schema": MIGRATION_JOURNAL_SCHEMA,
            "operation_id": operation_id,
            "database": str(self.database),
            "direction": plan.direction,
            "source_version": plan.observed_version,
            "target_version": plan.target_version,
            "state": "PREPARED",
            "created_at_utc": now,
            "updated_at_utc": now,
            "backup_path": str(backup),
            "backup_sha256": backup_hash,
            "completed_hops": [],
            "pending_hops": [hop.proposal for hop in plan.hops],
        }

    def _validate_resumable_journal(self, journal: Mapping[str, object]) -> str:
        state = _required_text(journal.get("state"), field="state")
        if state not in {"PREPARED", "APPLYING", "FAILED"}:
            raise MigrationServiceError("NOTHING_TO_RESUME", f"state={state}")
        database = _required_text(journal.get("database"), field="database")
        if Path(database).resolve(strict=False) != self.database:
            raise MigrationServiceError("JOURNAL_DATABASE_MISMATCH", "database differs")
        target = _required_text(journal.get("target_version"), field="target_version")
        backup = Path(_required_text(journal.get("backup_path"), field="backup_path"))
        backup_hash = _required_text(
            journal.get("backup_sha256"), field="backup_sha256"
        )
        if not backup.is_file() or _sha256_file(backup) != backup_hash:
            raise MigrationServiceError("BACKUP_VERIFY_FAILED", "backup missing or changed")
        return target

    def _run(self, plan: MigrationPlan, journal: dict[str, object]) -> dict[str, object]:
        journal["state"] = "APPLYING"
        journal["updated_at_utc"] = _utc_now()
        journal.pop("failure_reason", None)
        self._write_journal(journal)
        completed = journal.get("completed_hops")
        if not isinstance(completed, list) or not all(
            isinstance(value, str) for value in completed
        ):
            raise MigrationServiceError("JOURNAL_INVALID", "completed_hops invalid")
        try:
            for hop in plan.hops:
                if hop.proposal in completed:
                    continue
                self._apply_hop(hop)
                completed.append(hop.proposal)
                journal["completed_hops"] = completed
                journal["pending_hops"] = [
                    item.proposal for item in plan.hops if item.proposal not in completed
                ]
                journal["updated_at_utc"] = _utc_now()
                self._write_journal(journal)
            verification = self.verify()
        except Exception as exc:
            journal["state"] = "FAILED"
            journal["failure_reason"] = type(exc).__name__
            journal["updated_at_utc"] = _utc_now()
            self._write_journal(journal)
            raise
        journal["state"] = "COMPLETED"
        journal["completed_at_utc"] = _utc_now()
        journal["updated_at_utc"] = journal["completed_at_utc"]
        self._write_journal(journal)
        return {
            "schema": MIGRATION_RESULT_SCHEMA,
            "command": "apply" if plan.direction == "UP" else "rollback",
            "status": "COMPLETE",
            "source_version": plan.observed_version,
            "target_version": verification.schema_version,
            "operation_id": journal["operation_id"],
            "completed_hops": list(completed),
            "backup_sha256": journal["backup_sha256"],
            "authority_verified": True,
        }

    def apply(self, target_version: str = TARGET_SCHEMA_VERSION) -> dict[str, object]:
        with self._exclusive_lock():
            existing = self._read_journal()
            if existing is not None and existing.get("state") in {
                "PREPARED",
                "APPLYING",
                "FAILED",
            }:
                raise MigrationServiceError(
                    "RESUME_REQUIRED", "an incomplete migration journal exists"
                )
            plan = self.plan(target_version)
            if plan.direction == "DOWN":
                raise MigrationServiceError(
                    "ROLLBACK_COMMAND_REQUIRED", "use rollback for a lower target"
                )
            if not plan.hops:
                verification = self.verify()
                return {
                    "schema": MIGRATION_RESULT_SCHEMA,
                    "command": "apply",
                    "status": "NOOP",
                    "target_version": verification.schema_version,
                    "authority_verified": True,
                }
            journal = self._new_journal(plan)
            self._write_journal(journal)
            return self._run(plan, journal)

    def rollback(self, target_version: str) -> dict[str, object]:
        with self._exclusive_lock():
            existing = self._read_journal()
            if existing is not None and existing.get("state") in {
                "PREPARED",
                "APPLYING",
                "FAILED",
            }:
                raise MigrationServiceError(
                    "RESUME_REQUIRED", "an incomplete migration journal exists"
                )
            plan = self.plan(target_version)
            if plan.direction != "DOWN":
                raise MigrationServiceError(
                    "LOWER_ROLLBACK_TARGET_REQUIRED", "rollback target is not lower"
                )
            journal = self._new_journal(plan)
            self._write_journal(journal)
            return self._run(plan, journal)

    def resume(self) -> dict[str, object]:
        with self._exclusive_lock():
            journal = self._read_journal()
            if journal is None:
                raise MigrationServiceError("NOTHING_TO_RESUME", "journal absent")
            target = self._validate_resumable_journal(journal)
            plan = self.plan(target)
            if not plan.hops:
                verification = self.verify()
                journal["state"] = "COMPLETED"
                journal["completed_at_utc"] = _utc_now()
                journal["updated_at_utc"] = journal["completed_at_utc"]
                self._write_journal(journal)
                return {
                    "schema": MIGRATION_RESULT_SCHEMA,
                    "command": "resume",
                    "status": "COMPLETE",
                    "target_version": verification.schema_version,
                    "operation_id": journal["operation_id"],
                    "authority_verified": True,
                }
            result = self._run(plan, journal)
            result["command"] = "resume"
            return result

    def status(self) -> MigrationStatus:
        version = self._observed_version()
        try:
            self.verify()
            verified = True
        except MigrationServiceError:
            verified = False
        journal = self._read_journal()
        journal_state = "NONE" if journal is None else str(journal.get("state", "INVALID"))
        pending = None
        if journal_state in {"PREPARED", "APPLYING", "FAILED"} and journal is not None:
            value = journal.get("target_version")
            pending = value if isinstance(value, str) else None
        return MigrationStatus(
            schema_version=version,
            verified=verified,
            target_version=TARGET_SCHEMA_VERSION,
            at_head=version == TARGET_SCHEMA_VERSION and journal_state not in {
                "PREPARED",
                "APPLYING",
                "FAILED",
            },
            journal_state=journal_state,
            pending_target_version=pending,
        )

PostgreSQLConnectionFactory = Callable[[str], Any]
PostgreSQLBackupProvider = Callable[[Mapping[str, object], str], tuple[Path, str]]


def _postgres_connect(conninfo: str) -> Any:
    try:
        psycopg = import_module("psycopg")
        return psycopg.connect(conninfo, autocommit=False)
    except Exception as exc:
        raise MigrationServiceError("POSTGRES_CONNECT_FAILED", type(exc).__name__) from exc


class PostgreSQLMigrationService:
    """Apply the governed DB 1.6 -> 1.9 graph to one Service database."""

    def __init__(
        self,
        conninfo: str,
        *,
        state_root: Path,
        current_authority_root: Path,
        migration_authority_root: Path,
        backup_provider: PostgreSQLBackupProvider | None = None,
        connection_factory: PostgreSQLConnectionFactory | None = None,
    ) -> None:
        if not conninfo.strip():
            raise ValueError("conninfo must be non-empty")
        self._conninfo = conninfo
        self.state_root = state_root.expanduser().resolve(strict=False)
        self.current_authority_root = current_authority_root.expanduser().resolve(strict=False)
        self.migration_authority_root = migration_authority_root.expanduser().resolve(strict=False)
        identity = hashlib.sha256(conninfo.encode("utf-8")).hexdigest()[:16]
        self.journal_path = self.state_root / f"postgres-{identity}.journal.json"
        self._backup_provider = backup_provider
        self._connect = connection_factory or _postgres_connect
        self._authorities: dict[str, _SchemaAuthority] = {}

    def _authority(self, version: str) -> _SchemaAuthority:
        cached = self._authorities.get(version)
        if cached is not None:
            return cached
        authority = _load_migration_authority(
            version,
            current_authority_root=self.current_authority_root,
            migration_authority_root=self.migration_authority_root,
        )
        self._authorities[version] = authority
        return authority

    def _read_journal(self) -> dict[str, object] | None:
        if not self.journal_path.is_file():
            return None
        try:
            value: object = json.loads(self.journal_path.read_text(encoding="utf-8"))
        except Exception as exc:
            raise MigrationServiceError("JOURNAL_UNREADABLE", "invalid JSON") from exc
        if not isinstance(value, dict) or value.get("schema") != MIGRATION_JOURNAL_SCHEMA:
            raise MigrationServiceError("JOURNAL_INVALID", "schema mismatch")
        return value

    def _write_journal(self, journal: Mapping[str, object]) -> None:
        self.journal_path.parent.mkdir(parents=True, exist_ok=True)
        payload = json.dumps(journal, indent=2, sort_keys=True) + "\n"
        atomic_replace_bytes(self.journal_path, payload.encode("utf-8"))

    @staticmethod
    def _manifest_row(connection: Any) -> tuple[object, ...]:
        try:
            with connection.cursor() as cursor:
                cursor.execute(
                    f'''SELECT engine_profile, schema_version, core_baseline,
                               authority_artifact_id, authority_sha256,
                               baseline_lock_sha256, physical_schema_sha256,
                               catalog_schema_sha256
                        FROM "public"."{BOOTSTRAP_MANIFEST_TABLE}"
                        WHERE singleton=1'''
                )
                row = cursor.fetchone()
        except Exception as exc:
            raise MigrationServiceError("MANIFEST_UNAVAILABLE", type(exc).__name__) from exc
        if row is None or len(row) != 8:
            raise MigrationServiceError("MANIFEST_UNAVAILABLE", "singleton row absent")
        return tuple(row)

    def _observed_version(self, connection: Any | None = None) -> str:
        owned = connection is None
        active = self._connect(self._conninfo) if owned else connection
        assert active is not None
        try:
            row = self._manifest_row(active)
            version = str(row[1])
            if version not in SUPPORTED_SCHEMA_VERSIONS:
                raise MigrationServiceError("UNSUPPORTED_SCHEMA_VERSION", f"observed={version!r}")
            return version
        finally:
            if owned:
                active.close()

    def _verify_connection(
        self,
        connection: Any,
        authority: _SchemaAuthority,
    ) -> BootstrapVerification:
        row = self._manifest_row(connection)
        projection_hash = _schema_fingerprint(_postgres_create_statements(authority))
        expected = (
            POSTGRES_ENGINE_PROFILE,
            authority.schema_version,
            authority.core_baseline,
            CORE_MODEL_ARTIFACT_ID,
            authority.authority_sha256,
            authority.baseline_lock_sha256,
            projection_hash,
        )
        if tuple(str(value) for value in row[:7]) != expected:
            raise MigrationServiceError("DATABASE_VERIFY_FAILED", "manifest mismatch")
        try:
            with connection.cursor() as cursor:
                cursor.execute(
                    """SELECT n.nspname || '.' || c.relname
                       FROM pg_catalog.pg_class AS c
                       JOIN pg_catalog.pg_namespace AS n ON n.oid = c.relnamespace
                       WHERE c.relkind = 'r'
                         AND n.nspname NOT IN ('pg_catalog', 'information_schema')
                       ORDER BY 1"""
                )
                actual_tables = {str(item[0]) for item in cursor.fetchall()}
                cursor.execute(_postgres_catalog_hash_query())
                hash_row = cursor.fetchone()
        except Exception as exc:
            raise MigrationServiceError("DATABASE_VERIFY_FAILED", type(exc).__name__) from exc
        expected_tables = set(_postgres_expected_tables(authority))
        if actual_tables != expected_tables:
            raise MigrationServiceError(
                "DATABASE_VERIFY_FAILED",
                f"table_inventory missing={sorted(expected_tables - actual_tables)!r} "
                f"extra={sorted(actual_tables - expected_tables)!r}",
            )
        catalog_hash = None if hash_row is None else str(hash_row[0])
        if catalog_hash != str(row[7]):
            raise MigrationServiceError("DATABASE_VERIFY_FAILED", "catalog hash mismatch")
        return BootstrapVerification(
            engine_profile=POSTGRES_ENGINE_PROFILE,
            schema_version=authority.schema_version,
            core_baseline=authority.core_baseline,
            authority_artifact_id=CORE_MODEL_ARTIFACT_ID,
            authority_sha256=authority.authority_sha256,
            baseline_lock_sha256=authority.baseline_lock_sha256,
            physical_schema_sha256=projection_hash,
            table_count=len(authority.tables),
            journal_mode="n/a",
            catalog_schema_sha256=catalog_hash,
        )

    def verify(self) -> BootstrapVerification:
        connection = self._connect(self._conninfo)
        try:
            version = self._observed_version(connection)
            result = self._verify_connection(connection, self._authority(version))
            connection.rollback()
            return result
        finally:
            connection.close()

    def _relations(self, source: str, target: str) -> tuple[str, ...]:
        source_names = set(self._authority(source).tables)
        target_names = tuple(self._authority(target).tables)
        relations = tuple(name for name in target_names if name not in source_names)
        if not relations:
            raise MigrationServiceError("EMPTY_MIGRATION_STEP", f"source={source} target={target}")
        removed = sorted(source_names - set(target_names))
        if removed:
            raise MigrationServiceError("NON_ADDITIVE_AUTHORITY_STEP", f"removed={removed!r}")
        return relations

    def plan(self, target_version: str = TARGET_SCHEMA_VERSION) -> MigrationPlan:
        if target_version not in SUPPORTED_SCHEMA_VERSIONS:
            raise MigrationServiceError("UNSUPPORTED_TARGET_VERSION", f"target={target_version}")
        observed = self._observed_version()
        source_index = SUPPORTED_SCHEMA_VERSIONS.index(observed)
        target_index = SUPPORTED_SCHEMA_VERSIONS.index(target_version)
        if source_index == target_index:
            return MigrationPlan(observed, target_version, "NONE", ())
        direction = "UP" if target_index > source_index else "DOWN"
        selected: list[MigrationHop] = []
        steps: Sequence[_Step]
        if direction == "UP":
            steps = _STEPS[source_index:target_index]
            for step in steps:
                selected.append(
                    MigrationHop(
                        step.proposal,
                        step.source,
                        step.target,
                        direction,
                        self._relations(step.source, step.target),
                    )
                )
        else:
            steps = tuple(reversed(_STEPS[target_index:source_index]))
            for step in steps:
                selected.append(
                    MigrationHop(
                        step.proposal,
                        step.target,
                        step.source,
                        direction,
                        self._relations(step.source, step.target),
                    )
                )
        return MigrationPlan(observed, target_version, direction, tuple(selected))

    @contextmanager
    def _exclusive_connection(self) -> Iterator[tuple[Any, dict[str, object]]]:
        connection = self._connect(self._conninfo)
        acquired = False
        try:
            with connection.cursor() as cursor:
                cursor.execute(
                    "SELECT pg_try_advisory_lock(%s)",
                    (SERVICE_WRITE_GATE_LOCK_ID,),
                )
                row = cursor.fetchone()
            connection.commit()
            acquired = row is not None and row[0] is True
            if not acquired:
                raise MigrationServiceError("MIGRATION_LOCKED", "Service writes are active")
            with connection.cursor() as cursor:
                cursor.execute(
                    "SELECT current_database(), txid_current_snapshot()::text, "
                    "pg_current_wal_lsn()::text"
                )
                watermark = cursor.fetchone()
            connection.commit()
            if watermark is None:
                raise MigrationServiceError("MIGRATION_LOCK_FAILED", "watermark unavailable")
            evidence: dict[str, object] = {
                "schema": "TPAA_SERVICE_WRITE_DRAIN_V1",
                "state": "MANAGED_WRITES_BLOCKED",
                "acquired_at_utc": _utc_now(),
                "lock_id": SERVICE_WRITE_GATE_LOCK_ID,
                "database_identity_sha256": hashlib.sha256(
                    str(watermark[0]).encode("utf-8")
                ).hexdigest(),
                "transaction_snapshot": str(watermark[1]),
                "wal_lsn": str(watermark[2]),
            }
            yield connection, evidence
        finally:
            if acquired:
                try:
                    with connection.cursor() as cursor:
                        cursor.execute(
                            "SELECT pg_advisory_unlock(%s)",
                            (SERVICE_WRITE_GATE_LOCK_ID,),
                        )
                    connection.commit()
                finally:
                    connection.close()
            else:
                connection.close()

    @staticmethod
    def _table_statements(authority: _SchemaAuthority) -> dict[str, str]:
        schemas = {name.split(".", 1)[0] for name in authority.tables}
        statements = _postgres_create_statements(authority)[len(schemas) :]
        return dict(zip(_postgres_table_order(authority), statements, strict=True))

    def _update_manifest(self, connection: Any, authority: _SchemaAuthority) -> None:
        projection_hash = _schema_fingerprint(_postgres_create_statements(authority))
        with connection.cursor() as cursor:
            cursor.execute(_postgres_catalog_hash_query())
            row = cursor.fetchone()
            catalog_hash = None if row is None else str(row[0])
            if not catalog_hash:
                raise MigrationServiceError("CATALOG_HASH_UNAVAILABLE", authority.schema_version)
            cursor.execute(
                f'''UPDATE "public"."{BOOTSTRAP_MANIFEST_TABLE}"
                    SET schema_version=%s, core_baseline=%s,
                        authority_artifact_id=%s, authority_sha256=%s,
                        baseline_lock_sha256=%s, physical_schema_sha256=%s,
                        catalog_schema_sha256=%s
                    WHERE singleton=1''',
                (
                    authority.schema_version,
                    authority.core_baseline,
                    CORE_MODEL_ARTIFACT_ID,
                    authority.authority_sha256,
                    authority.baseline_lock_sha256,
                    projection_hash,
                    catalog_hash,
                ),
            )

    def _apply_hop(self, connection: Any, hop: MigrationHop) -> None:
        source = self._authority(hop.source_version)
        target = self._authority(hop.target_version)
        self._verify_connection(connection, source)
        connection.rollback()
        try:
            with connection.cursor() as cursor:
                if hop.direction == "UP":
                    statements = self._table_statements(target)
                    for relation in hop.affected_relations:
                        cursor.execute(statements[relation])
                else:
                    nonempty: list[str] = []
                    for relation in hop.affected_relations:
                        schema, table = relation.split(".", 1)
                        cursor.execute(f'SELECT COUNT(*) FROM "{schema}"."{table}"')
                        row = cursor.fetchone()
                        if row is None or int(row[0]) != 0:
                            nonempty.append(relation)
                    if nonempty:
                        raise MigrationServiceError(
                            "ROLLBACK_BLOCKED_NONEMPTY_RELATION", f"relations={nonempty!r}"
                        )
                    for relation in reversed(hop.affected_relations):
                        schema, table = relation.split(".", 1)
                        cursor.execute(f'DROP TABLE "{schema}"."{table}"')
            self._update_manifest(connection, target)
            self._verify_connection(connection, target)
            connection.commit()
        except MigrationServiceError:
            connection.rollback()
            raise
        except Exception as exc:
            connection.rollback()
            raise MigrationServiceError("MIGRATION_HOP_FAILED", type(exc).__name__) from exc

    def _new_journal(
        self,
        plan: MigrationPlan,
        evidence: Mapping[str, object],
    ) -> dict[str, object]:
        if self._backup_provider is None:
            raise MigrationServiceError("BACKUP_PROVIDER_REQUIRED", "Service migration requires backup")
        operation_id = str(uuid.uuid4())
        backup, backup_hash = self._backup_provider(evidence, operation_id)
        resolved = backup.expanduser().resolve(strict=False)
        if not resolved.is_file() or _sha256_file(resolved) != backup_hash:
            raise MigrationServiceError("BACKUP_VERIFY_FAILED", "backup missing or changed")
        now = _utc_now()
        return {
            "schema": MIGRATION_JOURNAL_SCHEMA,
            "operation_id": operation_id,
            "database_identity_sha256": evidence["database_identity_sha256"],
            "direction": plan.direction,
            "source_version": plan.observed_version,
            "target_version": plan.target_version,
            "state": "PREPARED",
            "created_at_utc": now,
            "updated_at_utc": now,
            "backup_path": str(resolved),
            "backup_sha256": backup_hash,
            "write_drain": dict(evidence),
            "completed_hops": [],
            "pending_hops": [hop.proposal for hop in plan.hops],
        }

    @staticmethod
    def _validate_backup(journal: Mapping[str, object]) -> None:
        backup = Path(_required_text(journal.get("backup_path"), field="backup_path"))
        expected = _required_text(journal.get("backup_sha256"), field="backup_sha256")
        if not backup.is_file() or _sha256_file(backup) != expected:
            raise MigrationServiceError("BACKUP_VERIFY_FAILED", "backup missing or changed")

    def _run(
        self,
        connection: Any,
        plan: MigrationPlan,
        journal: dict[str, object],
    ) -> dict[str, object]:
        journal["state"] = "APPLYING"
        journal["updated_at_utc"] = _utc_now()
        journal.pop("failure_reason", None)
        self._write_journal(journal)
        completed = journal.get("completed_hops")
        if not isinstance(completed, list) or not all(isinstance(item, str) for item in completed):
            raise MigrationServiceError("JOURNAL_INVALID", "completed_hops invalid")
        try:
            for hop in plan.hops:
                if hop.proposal in completed:
                    continue
                self._apply_hop(connection, hop)
                completed.append(hop.proposal)
                journal["completed_hops"] = completed
                journal["pending_hops"] = [
                    item.proposal for item in plan.hops if item.proposal not in completed
                ]
                journal["updated_at_utc"] = _utc_now()
                self._write_journal(journal)
            verification = self._verify_connection(connection, self._authority(plan.target_version))
            connection.rollback()
        except Exception as exc:
            journal["state"] = "FAILED"
            journal["failure_reason"] = type(exc).__name__
            journal["updated_at_utc"] = _utc_now()
            self._write_journal(journal)
            raise
        journal["state"] = "COMPLETED"
        journal["completed_at_utc"] = _utc_now()
        journal["updated_at_utc"] = journal["completed_at_utc"]
        self._write_journal(journal)
        return {
            "schema": MIGRATION_RESULT_SCHEMA,
            "command": "apply" if plan.direction == "UP" else "rollback",
            "status": "COMPLETE",
            "source_version": plan.observed_version,
            "target_version": verification.schema_version,
            "operation_id": journal["operation_id"],
            "completed_hops": list(completed),
            "backup_sha256": journal["backup_sha256"],
            "authority_verified": True,
            "write_drain_verified": True,
        }

    def _mutate(self, target_version: str, *, rollback: bool) -> dict[str, object]:
        with self._exclusive_connection() as (connection, evidence):
            existing = self._read_journal()
            if existing is not None and existing.get("state") in {"PREPARED", "APPLYING", "FAILED"}:
                raise MigrationServiceError("RESUME_REQUIRED", "incomplete migration journal exists")
            observed = self._observed_version(connection)
            connection.rollback()
            plan = self.plan(target_version)
            if plan.observed_version != observed:
                raise MigrationServiceError("MIGRATION_RACE", "schema changed while locking")
            if rollback and plan.direction != "DOWN":
                raise MigrationServiceError("LOWER_ROLLBACK_TARGET_REQUIRED", "target is not lower")
            if not rollback and plan.direction == "DOWN":
                raise MigrationServiceError("ROLLBACK_COMMAND_REQUIRED", "use rollback")
            if not plan.hops:
                verification = self._verify_connection(connection, self._authority(observed))
                connection.rollback()
                return {
                    "schema": MIGRATION_RESULT_SCHEMA,
                    "command": "rollback" if rollback else "apply",
                    "status": "NOOP",
                    "target_version": verification.schema_version,
                    "authority_verified": True,
                }
            journal = self._new_journal(plan, evidence)
            self._write_journal(journal)
            return self._run(connection, plan, journal)

    def apply(self, target_version: str = TARGET_SCHEMA_VERSION) -> dict[str, object]:
        return self._mutate(target_version, rollback=False)

    def rollback(self, target_version: str) -> dict[str, object]:
        return self._mutate(target_version, rollback=True)

    def resume(self) -> dict[str, object]:
        with self._exclusive_connection() as (connection, evidence):
            journal = self._read_journal()
            if journal is None or journal.get("state") not in {"PREPARED", "APPLYING", "FAILED"}:
                raise MigrationServiceError("NOTHING_TO_RESUME", "journal absent or complete")
            if journal.get("database_identity_sha256") != evidence["database_identity_sha256"]:
                raise MigrationServiceError("JOURNAL_DATABASE_MISMATCH", "database differs")
            self._validate_backup(journal)
            target = _required_text(journal.get("target_version"), field="target_version")
            observed = self._observed_version(connection)
            connection.rollback()
            plan = self.plan(target)
            if plan.observed_version != observed:
                raise MigrationServiceError("MIGRATION_RACE", "schema changed while locking")
            result = self._run(connection, plan, journal)
            result["command"] = "resume"
            return result

    def status(self) -> MigrationStatus:
        version = self._observed_version()
        try:
            self.verify()
            verified = True
        except MigrationServiceError:
            verified = False
        journal = self._read_journal()
        journal_state = "NONE" if journal is None else str(journal.get("state", "INVALID"))
        pending = None
        if journal_state in {"PREPARED", "APPLYING", "FAILED"} and journal is not None:
            value = journal.get("target_version")
            pending = value if isinstance(value, str) else None
        return MigrationStatus(
            schema_version=version,
            verified=verified,
            target_version=TARGET_SCHEMA_VERSION,
            at_head=version == TARGET_SCHEMA_VERSION and journal_state not in {
                "PREPARED",
                "APPLYING",
                "FAILED",
            },
            journal_state=journal_state,
            pending_target_version=pending,
        )

    def ready(self) -> bool:
        """Report head/journal readiness and reject an active exclusive write drain."""

        status = self.status()
        if not status.verified or not status.at_head:
            return False
        connection = self._connect(self._conninfo)
        acquired = False
        try:
            with connection.cursor() as cursor:
                cursor.execute(
                    "SELECT pg_try_advisory_lock_shared(%s)",
                    (SERVICE_WRITE_GATE_LOCK_ID,),
                )
                row = cursor.fetchone()
            connection.commit()
            acquired = row is not None and row[0] is True
            return acquired
        except Exception:
            return False
        finally:
            if acquired:
                try:
                    with connection.cursor() as cursor:
                        cursor.execute(
                            "SELECT pg_advisory_unlock_shared(%s)",
                            (SERVICE_WRITE_GATE_LOCK_ID,),
                        )
                    connection.commit()
                finally:
                    connection.close()
            else:
                connection.close()


__all__ = [
    "MIGRATION_JOURNAL_SCHEMA",
    "MIGRATION_RESULT_SCHEMA",
    "SUPPORTED_SCHEMA_VERSIONS",
    "TARGET_SCHEMA_VERSION",
    "MigrationHop",
    "MigrationPlan",
    "MigrationServiceError",
    "MigrationStatus",
    "PostgreSQLBackupProvider",
    "PostgreSQLMigrationService",
    "SQLiteMigrationService",
]
