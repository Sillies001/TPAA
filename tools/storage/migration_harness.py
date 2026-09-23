#!/usr/bin/env python3
"""M0-STO-005 migration harness for unchanged schema target 1.6.0.

No synthetic schema revision is invented. The harness proves clean bootstrap,
rollback, committed-drift rejection, forward recovery, historical fixture hook,
and repository conformance against the current frozen authority.
"""

from __future__ import annotations

import json
import shutil
import sqlite3
import sys
import tempfile
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
SRC_ROOT = REPO_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from tpaa_storage.bootstrap import (  # noqa: E402
    BOOTSTRAP_MANIFEST_TABLE,
    BootstrapError,
    bootstrap_sqlite,
    verify_sqlite,
)
from tpaa_storage.sqlite_repository import sqlite_repository_smoke  # noqa: E402

FIXTURE_MANIFEST = (
    REPO_ROOT / "fixtures" / "golden" / "M0_BASIC_TRANSPORT_V1" / "manifest.json"
)


def _backup_database(source: Path, destination: Path) -> None:
    with sqlite3.connect(source) as src, sqlite3.connect(destination) as dst:
        src.backup(dst)


def _restore_database(source: Path, destination: Path) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(source) as src, sqlite3.connect(destination) as dst:
        src.backup(dst)


def run() -> dict[str, object]:
    checks: dict[str, bool] = {}
    with tempfile.TemporaryDirectory(prefix="tpaa-migration-") as raw:
        root = Path(raw)
        database = root / "active.sqlite3"
        recovery = root / "recovery.sqlite3"

        bootstrap = bootstrap_sqlite(database)
        checks["clean_bootstrap"] = bootstrap.schema_version == "1.6.0"
        checks["readiness_verify"] = verify_sqlite(database) == bootstrap

        _backup_database(database, recovery)

        with sqlite3.connect(database) as connection:
            connection.execute("BEGIN")
            connection.execute(
                f'UPDATE "{BOOTSTRAP_MANIFEST_TABLE}" SET schema_version=? WHERE singleton=1',
                ("rollback-probe",),
            )
            connection.rollback()
        checks["rollback"] = verify_sqlite(database).schema_version == "1.6.0"

        with sqlite3.connect(database) as connection:
            connection.execute(
                f'UPDATE "{BOOTSTRAP_MANIFEST_TABLE}" SET schema_version=? WHERE singleton=1',
                ("drift-probe",),
            )
            connection.commit()
        drift_rejected = False
        try:
            verify_sqlite(database)
        except BootstrapError as exc:
            drift_rejected = exc.reason == "BOOTSTRAP_MANIFEST_MISMATCH"
        checks["committed_drift_fail_closed"] = drift_rejected

        database.unlink()
        for suffix in ("-wal", "-shm"):
            sidecar = Path(str(database) + suffix)
            if sidecar.exists():
                sidecar.unlink()
        _restore_database(recovery, database)
        checks["forward_recovery"] = verify_sqlite(database).schema_version == "1.6.0"

        repository = sqlite_repository_smoke(database)
        checks["repository_conformance"] = repository["schema_version"] == "1.6.0"

        fixture = json.loads(FIXTURE_MANIFEST.read_text(encoding="utf-8"))
        replay = fixture.get("replay")
        checks["historical_fixture_hook"] = (
            isinstance(replay, dict)
            and isinstance(replay.get("release_id"), str)
            and isinstance(replay.get("frozen_input_sha256"), str)
        )

    status = "PASS" if all(checks.values()) else "FAIL"
    return {
        "schema": "TPAA_M0_MIGRATION_HARNESS_V1",
        "task": "M0-STO-005",
        "status": status,
        "schema_target": "1.6.0",
        "schema_transition": "NONE_CURRENT_BASELINE",
        "checks": checks,
        "note": (
            "No artificial 1.6.0->new migration is created. PostgreSQL clean bootstrap/"
            "rollback/conformance remain covered by the existing M0-STO-001/003 harnesses."
        ),
    }


def main() -> int:
    result = run()
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0 if result["status"] == "PASS" else 2


if __name__ == "__main__":
    raise SystemExit(main())
