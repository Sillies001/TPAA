from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

from tpaa_runtime.approval_repository import PersistentApprovalEventRepository
from tpaa_security import (
    ApprovalService,
    ApprovalStatus,
    AuthorizationPrincipal,
    AuthorizationService,
    Permission,
    SecurityRole,
    load_security_policy,
)
from tpaa_storage import SQLiteDesktopUnitOfWork, bootstrap_sqlite


def _principal(subject: str, role: SecurityRole) -> AuthorizationPrincipal:
    return AuthorizationPrincipal(
        subject=subject,
        roles=frozenset({role}),
        scopes=frozenset({"*"}),
        authentication_method="TEST",
        credential_id=f"credential-{subject}",
    )


def _service(database: Path) -> ApprovalService:
    repository = PersistentApprovalEventRepository(
        lambda: SQLiteDesktopUnitOfWork(database),
        lambda: SQLiteDesktopUnitOfWork(database, write=True),
    )
    return ApprovalService(AuthorizationService(load_security_policy()), repository)


def test_approval_inbox_and_consumption_survive_process_restart(tmp_path: Path) -> None:
    database = tmp_path / "tpaa.db"
    bootstrap_sqlite(database)
    now = datetime(2026, 10, 21, 8, 0, tzinfo=UTC)
    maker = _principal("manager", SecurityRole.TRAINING_MANAGER)
    checker = _principal("administrator", SecurityRole.ADMINISTRATOR)
    target = {"path": "/api/v1/releases/publish"}

    requested = _service(database).request(
        maker,
        Permission.PRODUCT_PUBLISH,
        target_type="API_PATH",
        target_id=str(target["path"]),
        target=target,
        reason="publish reviewed product release",
        now=now,
    )
    restarted = _service(database)
    assert restarted.inbox(checker, now=now) == (requested,)
    assert restarted.decide(
        checker,
        requested.approval_id,
        approve=True,
        reason="release evidence reviewed",
        now=now,
    ).status is ApprovalStatus.APPROVED

    consumed = _service(database).consume(
        maker,
        requested.approval_id,
        permission=Permission.PRODUCT_PUBLISH,
        target_type="API_PATH",
        target_id=str(target["path"]),
        target=target,
        now=now,
    )
    assert consumed.status is ApprovalStatus.CONSUMED
