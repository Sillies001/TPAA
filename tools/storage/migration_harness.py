#!/usr/bin/env python3
"""M0-STO-005 / ACP-216 real schema-transition migration harness."""

from __future__ import annotations

import json
import sqlite3
import sys
import tempfile
from contextlib import closing
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
SRC_ROOT = REPO_ROOT / "src"
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from tools.storage.acp216_migration import (  # noqa: E402
    MigrationError,
    bootstrap_historical_sqlite,
    downgrade_sqlite,
    upgrade_sqlite,
    verify_historical_sqlite,
)
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
PROBE_ENTITY_ID = "94000000-0000-4000-8000-000000000001"
PROBE_ROW = (
    PROBE_ENTITY_ID,
    "AIRCRAFT",
    "ACP216-HISTORY-PROBE",
    "BLUE",
)


def _backup_database(source: Path, destination: Path) -> None:
    with closing(sqlite3.connect(source)) as src, closing(sqlite3.connect(destination)) as dst:
        src.backup(dst)


def _restore_database(source: Path, destination: Path) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True)
    with closing(sqlite3.connect(source)) as src, closing(sqlite3.connect(destination)) as dst:
        src.backup(dst)


def _write_historical_probe(database: Path) -> None:
    with closing(sqlite3.connect(database)) as connection:
        connection.execute(
            '''INSERT INTO "master.entity" (
                   entity_id, session_id, entity_type, parent_entity_id,
                   alias, actual_side_affiliation, created_at
               ) VALUES (?, NULL, ?, NULL, ?, ?, ?)''',
            (*PROBE_ROW, "2026-10-03T00:00:00Z"),
        )
        connection.commit()


def _read_historical_probe(database: Path) -> tuple[str, str, str, str] | None:
    with closing(sqlite3.connect(database)) as connection:
        row = connection.execute(
            '''SELECT entity_id, entity_type, alias, actual_side_affiliation
               FROM "master.entity" WHERE entity_id=?''',
            (PROBE_ENTITY_ID,),
        ).fetchone()
    if row is None:
        return None
    return (
        str(row[0]),
        str(row[1]),
        str(row[2]),
        str(row[3]),
    )


def run() -> dict[str, object]:
    checks: dict[str, bool] = {}
    with tempfile.TemporaryDirectory(prefix="tpaa-migration-") as raw:
        root = Path(raw)
        current = root / "current.sqlite3"
        recovery = root / "recovery.sqlite3"
        historical = root / "historical.sqlite3"

        clean = bootstrap_sqlite(current)
        checks["clean_bootstrap"] = clean.schema_version == "1.7.0"
        checks["readiness_verify"] = verify_sqlite(current) == clean

        _backup_database(current, recovery)
        with closing(sqlite3.connect(current)) as connection:
            connection.execute("BEGIN")
            connection.execute(
                f'UPDATE "{BOOTSTRAP_MANIFEST_TABLE}" SET schema_version=? WHERE singleton=1',
                ("rollback-probe",),
            )
            connection.rollback()
        checks["rollback"] = verify_sqlite(current).schema_version == "1.7.0"

        with closing(sqlite3.connect(current)) as connection:
            connection.execute(
                f'UPDATE "{BOOTSTRAP_MANIFEST_TABLE}" SET schema_version=? WHERE singleton=1',
                ("drift-probe",),
            )
            connection.commit()
        drift_rejected = False
        try:
            verify_sqlite(current)
        except BootstrapError as exc:
            drift_rejected = exc.reason == "BOOTSTRAP_MANIFEST_MISMATCH"
        checks["committed_drift_fail_closed"] = drift_rejected

        current.unlink()
        for suffix in ("-wal", "-shm"):
            sidecar = Path(str(current) + suffix)
            if sidecar.exists():
                sidecar.unlink()
        _restore_database(recovery, current)
        checks["forward_recovery"] = verify_sqlite(current).schema_version == "1.7.0"
        checks["repository_conformance"] = (
            sqlite_repository_smoke(current)["schema_version"] == "1.7.0"
        )

        source = bootstrap_historical_sqlite(historical)
        checks["historical_1_6_bootstrap"] = source.schema_version == "1.6.0"
        _write_historical_probe(historical)
        before = _read_historical_probe(historical)
        upgraded = upgrade_sqlite(historical)
        checks["upgrade_1_6_to_1_7"] = upgraded.schema_version == "1.7.0"
        checks["historical_row_exact_after_upgrade"] = (
            before == PROBE_ROW and _read_historical_probe(historical) == PROBE_ROW
        )

        with closing(sqlite3.connect(historical)) as connection:
            connection.execute(
                '''INSERT INTO "registry.mutation_idempotency" (
                       operation_code, request_id, request_hash,
                       result_object_type, result_object_id
                   ) VALUES (?, ?, ?, ?, ?)''',
                ("ACP216_TEST", "request-1", "a" * 64, "TEST", "result-1"),
            )
            connection.commit()
        downgrade_blocked = False
        try:
            downgrade_sqlite(historical)
        except MigrationError as exc:
            downgrade_blocked = exc.reason == "DOWNGRADE_BLOCKED_NONEMPTY_RELATION"
        checks["nonempty_downgrade_fail_closed"] = downgrade_blocked
        checks["failed_downgrade_preserves_1_7"] = (
            verify_sqlite(historical).schema_version == "1.7.0"
        )

        with closing(sqlite3.connect(historical)) as connection:
            connection.execute('DELETE FROM "registry.mutation_idempotency"')
            connection.commit()
        downgraded = downgrade_sqlite(historical)
        checks["empty_downgrade_to_1_6"] = downgraded.schema_version == "1.6.0"
        checks["historical_row_exact_after_downgrade"] = (
            verify_historical_sqlite(historical).schema_version == "1.6.0"
            and _read_historical_probe(historical) == PROBE_ROW
        )
        reupgraded = upgrade_sqlite(historical)
        checks["forward_reupgrade_to_1_7"] = reupgraded.schema_version == "1.7.0"
        checks["historical_row_exact_after_reupgrade"] = (
            _read_historical_probe(historical) == PROBE_ROW
        )

        fixture = json.loads(FIXTURE_MANIFEST.read_text(encoding="utf-8"))
        replay = fixture.get("replay")
        checks["historical_fixture_hook"] = (
            isinstance(replay, dict)
            and isinstance(replay.get("release_id"), str)
            and isinstance(replay.get("frozen_input_sha256"), str)
        )

    status = "PASS" if all(checks.values()) else "FAIL"
    return {
        "schema": "TPAA_M0_MIGRATION_HARNESS_V2",
        "task": "M0-STO-005",
        "proposal_id": "ACP-216",
        "status": status,
        "schema_target": "1.7.0",
        "schema_transition": "1.6.0->1.7.0",
        "checks": checks,
        "note": (
            "ACP-216 is the first real governed schema transition. Historical 1.6.0 "
            "bytes are preserved as migration-source evidence; 1.7.0 is current authority."
        ),
    }


def main() -> int:
    result = run()
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0 if result["status"] == "PASS" else 2


if __name__ == "__main__":
    raise SystemExit(main())
