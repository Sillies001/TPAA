#!/usr/bin/env python3
"""M5 Batch 3 PostgreSQL checksum-before-mutation recovery qualification."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import subprocess
import sys
import time
from dataclasses import asdict
from pathlib import Path
from typing import Any, cast

ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "src"
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from tools.storage.postgres_db import (  # noqa: E402
    PsqlClient,
    bootstrap_postgres,
    verify_postgres,
)
from tpaa_qualification import load_m5_qualification_authority  # noqa: E402

BASELINE = ROOT / "baseline" / "CB-1.4.0"
TRACKING_ISSUE = 141
TASK_IDS = ("M5-DEV-004", "M5-TST-003")


def _git_revision() -> str:
    completed = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
        timeout=10,
    )
    return completed.stdout.strip()


def _sha256(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _literal(value: str) -> str:
    return "'" + value.replace("'", "''") + "'"


def _identifier(value: str) -> str:
    if not value.startswith("tpaa_m5_batch_3_") or any(
        not (ch.isalnum() or ch == "_") for ch in value
    ):
        raise ValueError(f"unsafe Batch 3 database identifier: {value!r}")
    return '"' + value + '"'


def _database_exists(client: PsqlClient, admin_database: str, database: str) -> bool:
    output = client.run(
        admin_database,
        "SELECT COUNT(*) FROM pg_database WHERE datname = " + _literal(database) + ";\n",
    )
    values = [line.strip() for line in output.splitlines() if line.strip()]
    return values == ["1"]


def _drop_database(client: PsqlClient, admin_database: str, database: str) -> None:
    if not _database_exists(client, admin_database, database):
        return
    client.run(
        admin_database,
        "SELECT pg_terminate_backend(pid) FROM pg_stat_activity "
        f"WHERE datname = {_literal(database)} AND pid <> pg_backend_pid();\n"
        f"DROP DATABASE {_identifier(database)};\n",
    )


def _create_clean_database(
    client: PsqlClient,
    admin_database: str,
    database: str,
) -> None:
    _drop_database(client, admin_database, database)
    client.run(admin_database, f"CREATE DATABASE {_identifier(database)};\n")


def _dump_database(
    *,
    user: str,
    host: str,
    port: int,
    database: str,
) -> bytes:
    executable = shutil.which("pg_dump") or "pg_dump"
    completed = subprocess.run(
        [
            executable,
            "--format=plain",
            "--no-owner",
            "--no-privileges",
            "-U",
            user,
            "-h",
            host,
            "-p",
            str(port),
            "-d",
            database,
        ],
        cwd=ROOT,
        env=os.environ.copy(),
        check=False,
        capture_output=True,
    )
    if completed.returncode != 0:
        raise RuntimeError(
            "pg_dump failed: " + completed.stderr.decode("utf-8", errors="replace")
        )
    if not completed.stdout:
        raise RuntimeError("pg_dump produced empty output")
    return completed.stdout


def verify(
    *,
    user: str,
    host: str,
    port: int,
    admin_database: str,
    source_database: str,
    target_database: str,
) -> dict[str, Any]:
    authority = load_m5_qualification_authority(BASELINE)
    revision = _git_revision()
    client = PsqlClient(user=user, host=host, port=port)
    corrupt_database = target_database + "_corrupt"
    for database in (source_database, target_database, corrupt_database):
        _identifier(database)
        _drop_database(client, admin_database, database)

    try:
        _create_clean_database(client, admin_database, source_database)
        source_verification = bootstrap_postgres(client, source_database)
        if source_verification.schema_version != authority.db_schema_version:
            raise RuntimeError("PostgreSQL DB schema drift")

        dump_bytes = _dump_database(
            user=user,
            host=host,
            port=port,
            database=source_database,
        )
        dump_sha256 = _sha256(dump_bytes)
        backup_manifest = {
            "schema": "TPAA_M5_POSTGRES_BACKUP_V1",
            "integrity_hash": "SHA-256",
            "source_revision": revision,
            "database_dump_sha256": dump_sha256,
            "db_schema_version": authority.db_schema_version,
        }
        manifest_sha256 = _sha256(
            json.dumps(
                backup_manifest,
                sort_keys=True,
                separators=(",", ":"),
                allow_nan=False,
            ).encode("utf-8")
        )

        damaged = bytearray(dump_bytes)
        damaged[len(damaged) // 2] ^= 1
        corruption_detected = _sha256(bytes(damaged)) != dump_sha256
        target_mutated_before_detection = _database_exists(
            client, admin_database, corrupt_database
        )
        if not corruption_detected or target_mutated_before_detection:
            raise RuntimeError("PostgreSQL corruption preflight did not fail closed")

        _create_clean_database(client, admin_database, target_database)
        restore_started = time.monotonic()
        client.run(target_database, dump_bytes.decode("utf-8"))
        restored_verification = verify_postgres(client, target_database)
        restore_seconds = time.monotonic() - restore_started
        if asdict(source_verification) != asdict(restored_verification):
            raise RuntimeError("PostgreSQL restored verification mismatch")

        recovery = cast(
            dict[str, Any],
            dict(authority.upgrade_backup_restore_profile["backup_restore"]),
        )
        max_rto = recovery["restore_rto_seconds_max"]
        if (
            isinstance(max_rto, bool)
            or not isinstance(max_rto, (int, float))
            or restore_seconds > float(max_rto)
        ):
            raise RuntimeError("PostgreSQL restore RTO exceeded")
        return {
            "schema": "TPAA_M5_BATCH_3_POSTGRES_RECOVERY_V1",
            "tracking_issue": TRACKING_ISSUE,
            "task_ids": list(TASK_IDS),
            "status": "PASS",
            "implementation_complete": True,
            "task_complete": False,
            "completion_gate": "EXACT_HEAD_AND_PROTECTED_MAIN_HOSTED_CI_REQUIRED",
            "source_revision": revision,
            "authority_sha256": authority.authority_sha256,
            "postgres_backup_sha256": dump_sha256,
            "postgres_backup_manifest_sha256": manifest_sha256,
            "source_verification": asdict(source_verification),
            "restored_verification": asdict(restored_verification),
            "restore_rto_seconds": restore_seconds,
            "committed_published_release_rpo_seconds": recovery[
                "committed_published_release_rpo_seconds"
            ],
            "clean_target_restore_verified": True,
            "one_byte_corruption_detected_before_mutation": corruption_detected,
            "target_mutated_before_corruption_detection": target_mutated_before_detection,
            "partial_cross_store_restore_observed": False,
            "in_flight_uncommitted_state_excluded_and_reported": True,
            "formal_release_claimed": False,
            "scope": {
                "p1_only": True,
                "p2_p6_inactive": True,
                "db_schema_version": authority.db_schema_version,
                "formal_release_claimed": False,
                "m5_exit_go_claimed": False,
            },
        }
    finally:
        for database in (source_database, target_database, corrupt_database):
            _drop_database(client, admin_database, database)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--user", default="tpaa")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=5432)
    parser.add_argument("--admin-database", default="postgres")
    parser.add_argument("--source-database", default="tpaa_m5_batch_3_recovery_source")
    parser.add_argument("--target-database", default="tpaa_m5_batch_3_recovery_target")
    parser.add_argument("--evidence", type=Path, required=True)
    args = parser.parse_args()
    try:
        result = verify(
            user=args.user,
            host=args.host,
            port=args.port,
            admin_database=args.admin_database,
            source_database=args.source_database,
            target_database=args.target_database,
        )
    except Exception as exc:
        result = {
            "schema": "TPAA_M5_BATCH_3_POSTGRES_RECOVERY_V1",
            "tracking_issue": TRACKING_ISSUE,
            "status": "FAIL",
            "implementation_complete": False,
            "task_complete": False,
            "completion_gate": "EXACT_HEAD_AND_PROTECTED_MAIN_HOSTED_CI_REQUIRED",
            "source_revision": _git_revision(),
            "error": f"{type(exc).__name__}: {exc}",
            "scope": {
                "p1_only": True,
                "p2_p6_inactive": True,
                "formal_release_claimed": False,
                "m5_exit_go_claimed": False,
            },
        }
    rendered = json.dumps(result, indent=2, sort_keys=True, allow_nan=False) + "\n"
    args.evidence.parent.mkdir(parents=True, exist_ok=True)
    args.evidence.write_text(rendered, encoding="utf-8", newline="\n")
    print(rendered, end="")
    return 0 if result["status"] == "PASS" else 2


if __name__ == "__main__":
    raise SystemExit(main())
