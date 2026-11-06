from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

from tools.storage.g1_v33_migration import (
    MigrationError,
    bootstrap_source_sqlite,
    downgrade_sqlite,
    new_relation_names,
    upgrade_sqlite,
    verify_source_sqlite,
    verify_target_sqlite,
)


def test_g1_v33_sqlite_upgrade_and_empty_rollback(tmp_path: Path) -> None:
    database = tmp_path / "g1.sqlite3"

    assert bootstrap_source_sqlite(database).schema_version == "1.9.0"
    assert new_relation_names() == (
        "registry.batch_registration",
        "registry.batch_training_type_revision",
        "context.force_formation_context_revision",
        "context.force_formation_member",
    )
    assert upgrade_sqlite(database).schema_version == "1.10.0"
    assert verify_target_sqlite(database).core_baseline == "CB-1.6.0"
    assert downgrade_sqlite(database).schema_version == "1.9.0"
    assert verify_source_sqlite(database).core_baseline == "CB-1.5.0"


def test_g1_v33_sqlite_nonempty_rollback_fails_closed(tmp_path: Path) -> None:
    database = tmp_path / "g1-nonempty.sqlite3"
    bootstrap_source_sqlite(database)
    upgrade_sqlite(database)
    connection = sqlite3.connect(database)
    try:
        connection.execute(
            '''INSERT INTO "context.force_formation_context_revision" (
               context_revision_id, context_id, revision_no,
               valid_from_session_time_us, source, reason, changed_by)
               VALUES (?, ?, ?, ?, ?, ?, ?)''',
            (
                "00000000-0000-0000-0000-000000000901",
                "00000000-0000-0000-0000-000000000902",
                1,
                0,
                "TEST",
                "rollback gate",
                "test",
            ),
        )
        connection.commit()
    finally:
        connection.close()

    with pytest.raises(MigrationError, match="DOWNGRADE_NONEMPTY"):
        downgrade_sqlite(database)
    assert verify_target_sqlite(database).schema_version == "1.10.0"
