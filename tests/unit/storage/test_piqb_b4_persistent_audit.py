from __future__ import annotations

from pathlib import Path

from tpaa_storage import (
    AuditLogWrite,
    SQLiteDesktopUnitOfWork,
    bootstrap_sqlite,
)


def test_b4_audit_log_persists_exact_security_provenance_across_restart(
    tmp_path: Path,
) -> None:
    database = tmp_path / "tpaa.sqlite3"
    bootstrap_sqlite(database)

    with SQLiteDesktopUnitOfWork(database, write=True) as uow:
        uow.audit_log.append(
            AuditLogWrite(
                actor_id="11111111-1111-4111-8111-111111111111",
                principal_key="SUBJECT_SHA256:" + "a" * 64,
                action="P4_APPROVAL_WRITE",
                object_type="M8_SECURITY_EVENT",
                object_id="22222222-2222-4222-8222-222222222222",
                outcome="ALLOW",
                request_id="b4-audit-request-1",
                reason="training approval",
                details={
                    "viewer_role": "INSTRUCTOR_EVALUATOR",
                    "scope_match": True,
                },
            )
        )
        uow.audit_log.append(
            AuditLogWrite(
                actor_id=None,
                principal_key="ROLE:ANALYST",
                action="P4_READ",
                object_type="M8_SECURITY_EVENT",
                object_id="22222222-2222-4222-8222-222222222222",
                outcome="ALLOW",
                reason="P4_READ",
                details={"viewer_role": "ANALYST"},
            )
        )
        uow.commit()

    with SQLiteDesktopUnitOfWork(database) as restarted:
        rows = restarted.audit_log.rows()
        restarted.commit()

    assert len(rows) == 2
    first, second = rows
    assert first.actor_id == "11111111-1111-4111-8111-111111111111"
    assert first.principal_key == "SUBJECT_SHA256:" + "a" * 64
    assert first.request_id == "b4-audit-request-1"
    assert first.reason == "training approval"
    assert first.details == {
        "scope_match": True,
        "viewer_role": "INSTRUCTOR_EVALUATOR",
    }
    assert second.actor_id is None
    assert second.principal_key == "ROLE:ANALYST"
    assert second.request_id is None
    assert second.reason == "P4_READ"
    assert first.audit_id < second.audit_id
    assert first.created_at
    assert second.created_at
