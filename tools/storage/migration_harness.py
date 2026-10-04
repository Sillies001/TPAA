#!/usr/bin/env python3
"""M0-STO-005 sequential governed schema-transition migration harness."""

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
    bootstrap_historical_sqlite as bootstrap_1_6,
)
from tools.storage.acp216_migration import (  # noqa: E402
    downgrade_sqlite as downgrade_1_7_to_1_6,
)
from tools.storage.acp216_migration import (  # noqa: E402
    upgrade_sqlite as upgrade_1_6_to_1_7,
)
from tools.storage.acp216_migration import (  # noqa: E402
    verify_historical_sqlite as verify_1_6,
)
from tools.storage.acp219_migration import (  # noqa: E402
    MigrationError as ACP219MigrationError,
)
from tools.storage.acp219_migration import (  # noqa: E402
    downgrade_sqlite as downgrade_1_8_to_1_7,
)
from tools.storage.acp219_migration import (  # noqa: E402
    upgrade_sqlite as upgrade_1_7_to_1_8,
)
from tools.storage.acp219_migration import (  # noqa: E402
    verify_historical_sqlite as verify_1_7,
)
from tools.storage.acp221_migration import (  # noqa: E402
    downgrade_sqlite as downgrade_1_9_to_1_8,
)
from tools.storage.acp221_migration import (  # noqa: E402
    upgrade_sqlite as upgrade_1_8_to_1_9,
)
from tools.storage.acp221_migration import (  # noqa: E402
    verify_historical_sqlite as verify_1_8,
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
    "ACP219-HISTORY-PROBE",
    "BLUE",
)
ACP219_ACTOR_ID = "95000000-0000-4000-8000-000000000001"


def _backup_database(source: Path, destination: Path) -> None:
    with closing(sqlite3.connect(source)) as src, closing(sqlite3.connect(destination)) as dst:
        src.backup(dst)


def _restore_database(source: Path, destination: Path) -> None:
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
    return str(row[0]), str(row[1]), str(row[2]), str(row[3])


def _insert_acp219_nonempty_probe(database: Path) -> None:
    with closing(sqlite3.connect(database)) as connection:
        connection.execute(
            '''INSERT INTO "assessment.actor_assessment" (
                   actor_assessment_id, session_id, episode_id, actor_id,
                   aircraft_id, assessment_spec_id, assessment_spec_version,
                   world_refs, metric_refs, capability_projection_refs,
                   score, grade, status, confidence, evidence_set_id,
                   created_at, supersedes_id
               ) VALUES (?, ?, ?, ?, NULL, ?, ?, ?, ?, ?, NULL, NULL, ?, ?, ?, ?, NULL)''',
            (
                ACP219_ACTOR_ID,
                "95000000-0000-4000-8000-000000000002",
                "95000000-0000-4000-8000-000000000003",
                "95000000-0000-4000-8000-000000000004",
                "ACP219_TEST",
                "1.0.0",
                "[]",
                "[]",
                "[]",
                "DRAFT",
                1.0,
                "95000000-0000-4000-8000-000000000005",
                "2026-10-03T00:00:00Z",
            ),
        )
        connection.execute(
            '''INSERT INTO "assessment.actor_assessment_machine_evidence_ref" (
                   actor_assessment_id, ref_order, evidence_ref
               ) VALUES (?, ?, ?)''',
            (ACP219_ACTOR_ID, 0, "machine:acp219:ordered-text-probe"),
        )
        connection.commit()


def run() -> dict[str, object]:
    checks: dict[str, bool] = {}
    with tempfile.TemporaryDirectory(prefix="tpaa-migration-") as raw:
        root = Path(raw)
        current = root / "current.sqlite3"
        recovery = root / "recovery.sqlite3"
        historical = root / "historical.sqlite3"

        clean = bootstrap_sqlite(current)
        checks["clean_bootstrap"] = clean.schema_version == "1.9.0"
        checks["readiness_verify"] = verify_sqlite(current) == clean

        _backup_database(current, recovery)
        with closing(sqlite3.connect(current)) as connection:
            connection.execute("BEGIN")
            connection.execute(
                f'UPDATE "{BOOTSTRAP_MANIFEST_TABLE}" SET schema_version=? WHERE singleton=1',
                ("rollback-probe",),
            )
            connection.rollback()
        checks["rollback"] = verify_sqlite(current).schema_version == "1.9.0"

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
        checks["forward_recovery"] = verify_sqlite(current).schema_version == "1.9.0"
        checks["repository_conformance"] = (
            sqlite_repository_smoke(current)["schema_version"] == "1.9.0"
        )

        source_1_6 = bootstrap_1_6(historical)
        checks["historical_1_6_bootstrap"] = source_1_6.schema_version == "1.6.0"
        _write_historical_probe(historical)
        before = _read_historical_probe(historical)

        step_1_7 = upgrade_1_6_to_1_7(historical)
        checks["upgrade_1_6_to_1_7"] = step_1_7.schema_version == "1.7.0"
        checks["historical_row_exact_at_1_7"] = (
            before == PROBE_ROW
            and verify_1_7(historical).schema_version == "1.7.0"
            and _read_historical_probe(historical) == PROBE_ROW
        )

        step_1_8 = upgrade_1_7_to_1_8(historical)
        checks["upgrade_1_7_to_1_8"] = step_1_8.schema_version == "1.8.0"
        checks["historical_row_exact_at_1_8"] = (
            verify_1_8(historical).schema_version == "1.8.0"
            and _read_historical_probe(historical) == PROBE_ROW
        )

        step_1_9 = upgrade_1_8_to_1_9(historical)
        checks["upgrade_1_8_to_1_9"] = step_1_9.schema_version == "1.9.0"
        checks["historical_row_exact_at_1_9"] = (
            _read_historical_probe(historical) == PROBE_ROW
        )

        back_1_8 = downgrade_1_9_to_1_8(historical)
        checks["empty_downgrade_to_1_8"] = back_1_8.schema_version == "1.8.0"
        checks["historical_row_exact_after_1_9_downgrade"] = (
            verify_1_8(historical).schema_version == "1.8.0"
            and _read_historical_probe(historical) == PROBE_ROW
        )

        _insert_acp219_nonempty_probe(historical)
        downgrade_blocked = False
        try:
            downgrade_1_8_to_1_7(historical)
        except ACP219MigrationError as exc:
            downgrade_blocked = exc.reason == "DOWNGRADE_BLOCKED_NONEMPTY_RELATION"
        checks["acp219_nonempty_downgrade_fail_closed"] = downgrade_blocked
        checks["failed_downgrade_preserves_1_8"] = (
            verify_1_8(historical).schema_version == "1.8.0"
        )

        with closing(sqlite3.connect(historical)) as connection:
            connection.execute(
                'DELETE FROM "assessment.actor_assessment_machine_evidence_ref"'
            )
            connection.commit()
        back_1_7 = downgrade_1_8_to_1_7(historical)
        checks["empty_downgrade_to_1_7"] = back_1_7.schema_version == "1.7.0"
        checks["historical_row_exact_after_1_8_downgrade"] = (
            verify_1_7(historical).schema_version == "1.7.0"
            and _read_historical_probe(historical) == PROBE_ROW
        )

        back_1_6 = downgrade_1_7_to_1_6(historical)
        checks["empty_downgrade_to_1_6"] = back_1_6.schema_version == "1.6.0"
        checks["historical_row_exact_after_full_downgrade"] = (
            verify_1_6(historical).schema_version == "1.6.0"
            and _read_historical_probe(historical) == PROBE_ROW
        )

        re_1_7 = upgrade_1_6_to_1_7(historical)
        re_1_8 = upgrade_1_7_to_1_8(historical)
        re_1_9 = upgrade_1_8_to_1_9(historical)
        checks["forward_reupgrade_to_1_9"] = (
            re_1_7.schema_version == "1.7.0"
            and re_1_8.schema_version == "1.8.0"
            and re_1_9.schema_version == "1.9.0"
        )
        checks["historical_row_exact_after_reupgrade"] = (
            _read_historical_probe(historical) == PROBE_ROW
        )

        fixture = json.loads(FIXTURE_MANIFEST.read_text(encoding="utf-8"))
        replay = fixture.get("replay")
        expected = fixture.get("expected")
        input_spec = fixture.get("input")
        checks["historical_fixture_hook"] = (
            fixture.get("fixture_id") == "M0_BASIC_TRANSPORT_V1"
            and isinstance(replay, dict)
            and isinstance(expected, dict)
            and isinstance(input_spec, dict)
            and replay.get("frozen_expected_sha256") == expected.get("sha256")
            and replay.get("frozen_input_sha256") == input_spec.get("sha256")
        )

    status = "PASS" if all(checks.values()) else "FAIL"
    return {
        "schema": "TPAA_M0_MIGRATION_HARNESS_V4",
        "task": "M0-STO-005",
        "proposal_chain": ["ACP-216", "ACP-219", "ACP-221"],
        "status": status,
        "schema_target": "1.9.0",
        "schema_transition": "1.6.0->1.7.0->1.8.0->1.9.0",
        "checks": checks,
        "note": (
            "Historical DB authority snapshots remain immutable migration sources; "
            "DB 1.9.0 is the current physical authority candidate."
        ),
    }


def main() -> int:
    payload = run()
    print(json.dumps(payload, sort_keys=True))
    return 0 if payload["status"] == "PASS" else 2


if __name__ == "__main__":
    raise SystemExit(main())
