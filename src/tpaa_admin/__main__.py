"""Fail-closed administration CLI for the TPAA Desktop profile."""

from __future__ import annotations

import argparse
import getpass
import hashlib
import json
import os
import platform
import sys
from collections.abc import Sequence
from datetime import UTC, datetime, timedelta
from pathlib import Path

from tpaa_application import ReleaseManagementService
from tpaa_platform.filesync import atomic_replace_bytes
from tpaa_runtime import (
    create_desktop_production_backup,
    create_service_migration_backup,
    default_desktop_data_root,
    desktop_backup_status,
    desktop_write_quiescence_lock,
    permission_governance_status,
    prepare_desktop_production_config,
    resolve_authority_root,
    restore_desktop_production_backup,
    service_production_config_from_environment,
    stage_source_artifact_file,
)
from tpaa_security import (
    ASSIGNMENT_SCHEMA,
    EnvironmentSecretManager,
    SecurityRole,
    sign_assignment,
)
from tpaa_service import project_version
from tpaa_storage import (
    TARGET_SCHEMA_VERSION,
    BootstrapVerification,
    LocalObjectStore,
    PostgreSQLMigrationService,
    SQLiteDesktopUnitOfWork,
    SQLiteMigrationService,
    verify_sqlite,
)

RESULT_SCHEMA = "TPAA_ADMIN_RESULT_V1"


def _absolute(path: Path, *, field: str) -> Path:
    expanded = path.expanduser()
    if not expanded.is_absolute():
        raise ValueError(f"{field} must be an absolute path")
    return expanded.resolve(strict=False)


def _data_root(configured: Path | None) -> Path:
    if configured is None:
        return default_desktop_data_root()
    return _absolute(configured, field="data_root")


def _paths(data_root: Path) -> tuple[Path, Path]:
    return data_root / "tpaa.sqlite3", data_root / "objects"


def _migration_service(
    *,
    data_root: Path,
    authority_root: Path,
    migration_authority_root: Path | None,
) -> SQLiteMigrationService:
    historical = (
        authority_root.parents[2] / "migrations" / "authority"
        if migration_authority_root is None
        else _absolute(
            migration_authority_root,
            field="migration_authority_root",
        )
    )
    return SQLiteMigrationService(
        _paths(data_root)[0],
        current_authority_root=authority_root,
        migration_authority_root=historical,
    )


def _migration_command(args: argparse.Namespace) -> dict[str, object]:
    authority_root = resolve_authority_root(anchor=Path(__file__))
    historical = (
        authority_root.parents[2] / "migrations" / "authority"
        if args.migration_authority_root is None
        else _absolute(args.migration_authority_root, field="migration_authority_root")
    )
    if args.profile == "DESKTOP":
        service: SQLiteMigrationService | PostgreSQLMigrationService = _migration_service(
            data_root=_data_root(args.data_root),
            authority_root=authority_root,
            migration_authority_root=historical,
        )
    else:
        if args.data_root is not None:
            raise ValueError("Service migration forbids --data-root")
        if args.state_root is None:
            raise ValueError("Service migration requires --state-root")
        config = service_production_config_from_environment(
            product_build_version=project_version(),
            authority_root=authority_root,
        )
        if config.service_conninfo is None:
            raise ValueError("Service migration requires PostgreSQL configuration")
        service_conninfo = config.service_conninfo

        def backup_provider(
            evidence: dict[str, object] | object,
            operation_id: str,
        ) -> tuple[Path, str]:
            if not isinstance(evidence, dict):
                raise ValueError("Service migration write-drain evidence is invalid")
            if args.backup_root is None:
                raise ValueError("Service migration mutation requires --backup-root")
            backup_root = _absolute(args.backup_root, field="backup_root")
            backup_root.mkdir(parents=True, exist_ok=True)
            dump = create_service_migration_backup(
                conninfo=service_conninfo,
                object_root=config.object_root,
                destination=backup_root / operation_id,
                managed_drain_receipt=evidence,
                pg_dump_executable=args.pg_dump_executable,
            )
            digest = hashlib.sha256(dump.read_bytes()).hexdigest()
            return dump, digest

        service = PostgreSQLMigrationService(
            service_conninfo,
            state_root=_absolute(args.state_root, field="state_root"),
            current_authority_root=authority_root,
            migration_authority_root=historical,
            backup_provider=backup_provider,
        )
    action = str(args.migrate_command)
    if action == "plan":
        return service.plan(str(args.to_version)).payload()
    if action == "verify":
        verification = service.verify()
        return {
            "schema": RESULT_SCHEMA,
            "command": "migrate.verify",
            "status": "PASS",
            "schema_version": verification.schema_version,
            "core_baseline": verification.core_baseline,
            "authority_sha256": verification.authority_sha256,
        }
    if action == "apply":
        return service.apply(str(args.to_version))
    if action == "resume":
        return service.resume()
    if action == "rollback":
        return service.rollback(str(args.to_version))
    if action == "status":
        return service.status().payload()
    raise RuntimeError(f"unsupported migration command: {action}")


def _release_command(args: argparse.Namespace) -> dict[str, object]:
    data_root = _data_root(args.data_root)
    authority_root = resolve_authority_root(anchor=Path(__file__))
    database, object_root = _paths(data_root)
    verify_sqlite(database, authority_root=authority_root)

    def read_uow() -> SQLiteDesktopUnitOfWork:
        return SQLiteDesktopUnitOfWork(database, authority_root=authority_root)

    def write_uow() -> SQLiteDesktopUnitOfWork:
        return SQLiteDesktopUnitOfWork(
            database,
            write=True,
            authority_root=authority_root,
            write_consistency_lock=desktop_write_quiescence_lock(object_root),
        )

    service = ReleaseManagementService(read_uow, write_uow)  # type: ignore[arg-type]
    action = str(args.release_command)
    if action == "list":
        items = service.list(scope_type=args.scope_type, scope_key=args.scope_key)
        return {
            "schema": RESULT_SCHEMA,
            "command": "release.list",
            "status": "COMPLETE",
            "items": [item.payload() for item in items],
        }
    common = {
        "expected_version_token": args.expected_version_token,
        "principal_key": args.principal_key,
        "actor_id": args.actor_id,
        "request_id": args.request_id,
        "reason": args.reason,
    }
    if action == "withdraw":
        receipt = service.withdraw(args.release_id, **common)
    elif action == "supersede":
        receipt = service.supersede(
            args.release_id,
            successor_release_id=args.successor_release_id,
            **common,
        )
    else:
        raise RuntimeError(f"unsupported release command: {action}")
    return {
        "schema": RESULT_SCHEMA,
        "command": f"release.{action}",
        "status": "COMPLETE",
        "receipt": receipt.payload(),
    }


def _verification_payload(
    command: str,
    data_root: Path,
    verification: BootstrapVerification,
) -> dict[str, object]:
    _database, object_root = _paths(data_root)
    object_ready = (
        object_root.is_dir() and os.access(object_root, os.R_OK) and os.access(object_root, os.W_OK)
    )
    if not object_ready:
        raise RuntimeError("Desktop object root is unavailable")
    return {
        "schema": RESULT_SCHEMA,
        "command": command,
        "status": "READY",
        "profile": "DESKTOP",
        "data_root": str(data_root),
        "db_schema_version": verification.schema_version,
        "core_baseline": verification.core_baseline,
        "authority_sha256": verification.authority_sha256,
        "object_root_ready": True,
        "backup": desktop_backup_status(data_root / "tpaa.sqlite3"),
    }


def _verify(command: str, data_root: Path, authority_root: Path) -> dict[str, object]:
    database, _object_root = _paths(data_root)
    verification = verify_sqlite(database, authority_root=authority_root)
    return _verification_payload(command, data_root, verification)


def _execute(args: argparse.Namespace) -> dict[str, object]:
    command = str(args.command)
    if command == "migrate":
        return _migration_command(args)
    if command == "release":
        return _release_command(args)
    if command == "permissions":
        return {
            "schema": RESULT_SCHEMA,
            "command": command,
            "permission_governance": permission_governance_status(),
        }
    data_root = _data_root(args.data_root)
    if command == "identity-issue":
        roles = tuple(SecurityRole(value) for value in args.role)
        scopes = tuple(dict.fromkeys(args.scope))
        if not roles or not scopes or args.valid_hours < 1 or args.valid_hours > 168:
            raise ValueError("Desktop identity roles, scopes, or validity are invalid")
        material = EnvironmentSecretManager(os.environ).resolve(args.key_ref)
        now = datetime.now(UTC)
        payload: dict[str, object] = {
            "schema": ASSIGNMENT_SCHEMA,
            "key_id": material.key_id,
            "account_id": args.account_id or getpass.getuser(),
            "device_id": args.device_id or platform.node(),
            "subject": args.subject,
            "roles": [role.value for role in roles],
            "scopes": list(scopes),
            "issued_at": now.isoformat().replace("+00:00", "Z"),
            "expires_at": (now + timedelta(hours=args.valid_hours))
            .isoformat()
            .replace("+00:00", "Z"),
        }
        target = data_root / "desktop-identity.json"
        target.parent.mkdir(parents=True, exist_ok=True)
        atomic_replace_bytes(
            target,
            json.dumps(
                {**payload, "signature": sign_assignment(payload, material.value)},
                sort_keys=True,
                separators=(",", ":"),
            ).encode(),
        )
        return {
            "schema": RESULT_SCHEMA,
            "command": command,
            "status": "COMPLETE",
            "identity_file": str(target),
            "key_id": material.key_id,
            "roles": [role.value for role in roles],
            "expires_at": payload["expires_at"],
        }
    authority_root = resolve_authority_root(anchor=Path(__file__))
    database, object_root = _paths(data_root)

    if command == "init":
        prepare_desktop_production_config(
            product_build_version=project_version(),
            authority_root=authority_root,
            data_root=data_root,
        )
        return _verify(command, data_root, authority_root)
    if command in {"verify", "status"}:
        return _verify(command, data_root, authority_root)
    if command == "source-stage":
        source_file = _absolute(args.source_file, field="source_file")
        _verify(command, data_root, authority_root)
        reference = stage_source_artifact_file(
            LocalObjectStore(object_root),
            artifact_id=str(args.artifact_id),
            source_file=source_file,
        )
        return {
            "schema": RESULT_SCHEMA,
            "command": command,
            "status": "COMPLETE",
            "profile": "DESKTOP",
            "artifact_id": str(args.artifact_id),
            "source_artifact": reference.as_payload(),
            "source_import_binding": {
                "source_ref": reference.logical_uri,
                "uri_kind": "MANAGED",
            },
        }
    if command == "backup":
        destination = _absolute(args.destination, field="destination")
        _verify(command, data_root, authority_root)
        manifest = create_desktop_production_backup(
            database=database,
            object_root=object_root,
            destination=destination,
            authority_root=authority_root,
        )
        return {
            "schema": RESULT_SCHEMA,
            "command": command,
            "status": "COMPLETE",
            "profile": "DESKTOP",
            "manifest": str(manifest),
        }
    if command == "restore":
        backup = _absolute(args.backup, field="backup")
        restore_desktop_production_backup(
            backup=backup,
            target_database=database,
            target_object_root=object_root,
            authority_root=authority_root,
        )
        return _verify(command, data_root, authority_root)
    raise RuntimeError(f"unsupported admin command: {command}")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="tpaa-admin")
    subcommands = parser.add_subparsers(dest="command", required=True)

    for name in ("init", "verify", "status"):
        command = subcommands.add_parser(name)
        command.add_argument("--data-root", type=Path)

    backup = subcommands.add_parser("backup")
    backup.add_argument("--data-root", type=Path)
    backup.add_argument("--destination", type=Path, required=True)

    restore = subcommands.add_parser("restore")
    restore.add_argument("--data-root", type=Path)
    restore.add_argument("--backup", type=Path, required=True)
    source_stage = subcommands.add_parser("source-stage")
    source_stage.add_argument("--data-root", type=Path)
    source_stage.add_argument("--artifact-id", required=True)
    source_stage.add_argument("--source-file", type=Path, required=True)
    subcommands.add_parser("permissions")
    identity = subcommands.add_parser("identity-issue")
    identity.add_argument("--data-root", type=Path)
    identity.add_argument("--subject", required=True)
    identity.add_argument(
        "--role", action="append", required=True, choices=tuple(SecurityRole)
    )
    identity.add_argument("--scope", action="append", required=True)
    identity.add_argument("--key-ref", required=True)
    identity.add_argument("--valid-hours", type=int, default=8)
    identity.add_argument("--account-id")
    identity.add_argument("--device-id")

    migrate = subcommands.add_parser("migrate")
    migrate_subcommands = migrate.add_subparsers(
        dest="migrate_command",
        required=True,
    )
    for name in ("plan", "verify", "apply", "resume", "rollback", "status"):
        command = migrate_subcommands.add_parser(name)
        command.add_argument("--profile", choices=("DESKTOP", "SERVICE"), default="DESKTOP")
        command.add_argument("--data-root", type=Path)
        command.add_argument("--migration-authority-root", type=Path)
        command.add_argument("--state-root", type=Path)
        command.add_argument("--backup-root", type=Path)
        command.add_argument("--pg-dump-executable", default="pg_dump")
        if name in {"plan", "apply"}:
            command.add_argument("--to", dest="to_version", default=TARGET_SCHEMA_VERSION)
        elif name == "rollback":
            command.add_argument("--to", dest="to_version", required=True)

    release = subcommands.add_parser("release")
    release_subcommands = release.add_subparsers(
        dest="release_command",
        required=True,
    )
    release_list = release_subcommands.add_parser("list")
    release_list.add_argument("--data-root", type=Path)
    release_list.add_argument("--scope-type", choices=("SESSION", "LONGITUDINAL"), required=True)
    release_list.add_argument("--scope-key", required=True)
    for name in ("withdraw", "supersede"):
        command = release_subcommands.add_parser(name)
        command.add_argument("--data-root", type=Path)
        command.add_argument("--release-id", required=True)
        if name == "supersede":
            command.add_argument("--successor-release-id", required=True)
        command.add_argument("--expected-version-token", type=int, required=True)
        command.add_argument("--principal-key", required=True)
        command.add_argument("--actor-id")
        command.add_argument("--request-id")
        command.add_argument("--reason", required=True)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        payload = _execute(args)
    except Exception as exc:
        command = str(args.command)
        migrate_command = getattr(args, "migrate_command", None)
        if command == "migrate" and migrate_command:
            command = f"migrate.{migrate_command}"
        release_command = getattr(args, "release_command", None)
        if command == "release" and release_command:
            command = f"release.{release_command}"
        payload = {
            "schema": RESULT_SCHEMA,
            "command": command,
            "status": "FAILED",
            "error_type": type(exc).__name__,
        }
        print(json.dumps(payload, sort_keys=True), file=sys.stderr)
        return 2
    print(json.dumps(payload, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
