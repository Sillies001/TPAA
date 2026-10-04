from __future__ import annotations

from pathlib import Path

from tpaa_application import SecurityAuditRecord
from tpaa_runtime import DesktopPersistenceConfig, build_desktop_persistence
from tpaa_storage import SQLiteDesktopUnitOfWork, bootstrap_sqlite

ROOT = Path(__file__).resolve().parents[2]


def test_b4_desktop_persistence_exposes_db19_security_audit_sink(
    tmp_path: Path,
) -> None:
    database = tmp_path / "tpaa.sqlite3"
    bootstrap_sqlite(database)
    runtime = build_desktop_persistence(
        DesktopPersistenceConfig(
            database_path=database,
            object_root=tmp_path / "objects",
        )
    )

    runtime.security_audit_sink.record(
        SecurityAuditRecord(
            actor_id="11111111-1111-4111-8111-111111111111",
            principal_key="SUBJECT_SHA256:" + "b" * 64,
            action="P6_MODEL_RELEASE",
            object_type="P6_SECURITY_EVENT",
            object_id="22222222-2222-4222-8222-222222222222",
            outcome="ALLOW",
            request_id="b4-runtime-audit-1",
            reason="MODEL_RELEASE",
            details={"viewer_role": "MODEL_REVIEWER"},
        )
    )

    with SQLiteDesktopUnitOfWork(database) as restarted:
        rows = restarted.audit_log.rows()
        restarted.commit()
    assert len(rows) == 1
    assert rows[0].request_id == "b4-runtime-audit-1"
    assert rows[0].principal_key == "SUBJECT_SHA256:" + "b" * 64
    assert rows[0].details == {"viewer_role": "MODEL_REVIEWER"}


def test_b4_m8_and_p6_emit_through_injected_security_audit_port() -> None:
    m8 = (ROOT / "src" / "tpaa_application" / "m8_workspace.py").read_text(
        encoding="utf-8"
    )
    m9 = (ROOT / "src" / "tpaa_application" / "m9_workspace.py").read_text(
        encoding="utf-8"
    )
    composition = (
        ROOT / "src" / "tpaa_runtime" / "composition.py"
    ).read_text(encoding="utf-8")

    assert "security_audit_sink: SecurityAuditSink | None = None" in m8
    assert "self._security_audit_sink.record(" in m8
    assert "P4_APPROVAL_WRITE" in m8
    assert "P5_APPROVAL_WRITE" in m8
    assert "security_audit_sink: SecurityAuditSink | None = None" in m9
    assert "self._security_audit_sink.record(" in m9
    assert '"P6_SECURITY_EVENT"' in m9
    assert "security_audit_sink=security_audit_sink" in composition


def test_b4_runtime_exposes_qualification_and_secret_safe_observability() -> None:
    runtime = (ROOT / "src" / "tpaa_api" / "runtime.py").read_text(
        encoding="utf-8"
    )
    observability = (
        ROOT / "src" / "tpaa_runtime" / "observability.py"
    ).read_text(encoding="utf-8")

    assert '@app.get("/runtime/qualification")' in runtime
    assert '@app.get("/runtime/observability")' in runtime
    assert "application.qualification_status()" in runtime
    assert "application.operational_status()" in runtime
    assert "PIQB_B3_QUALIFIED" in observability
    assert "structured_record(" in observability
    for forbidden in (
        "authorization",
        "cookie",
        "password",
        "private_key",
        "credential",
    ):
        assert f'"{forbidden}"' not in observability.lower()


def test_b4_audit_authority_remains_existing_db19_relation() -> None:
    import json

    model = json.loads(
        (
            ROOT
            / "baseline"
            / "CB-1.4.0"
            / "canonical"
            / "CORE_LOGICAL_MODEL.json"
        ).read_text(encoding="utf-8")
    )
    table = model["tables"]["audit.audit_log"]
    assert table["schema_version"] == "1.9.0"
    fields = {row["name"] for row in table["fields"]}
    assert {
        "audit_id",
        "actor_id",
        "action",
        "object_type",
        "object_id",
        "old_value",
        "new_value",
        "reason",
        "request_id",
        "created_at",
    } == fields
