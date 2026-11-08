"""G4 SQLite/PostgreSQL-neutral Batch and context repository."""

from __future__ import annotations

from collections.abc import Sequence
from datetime import UTC, datetime
from uuid import UUID, uuid5

from tpaa_application.batch_import import (
    BatchImportError,
    BatchRegistrationRecord,
    ForceFormationMember,
    ForceFormationRevision,
)
from tpaa_storage.audit_ledger import AuditLogWrite

from .durable_repositories import RuntimeUnitOfWorkFactory

_REVISION_NAMESPACE = UUID("0fc53a5a-a821-48a9-ae7a-ce9ce90955c3")
_BATCH_COLUMNS = (
    "batch_id",
    "session_id",
    "batch_date",
    "batch_training_type",
    "training_type_confirmed",
    "context_id",
    "release_id",
    "qualification_status",
    "source_manifest_sha256",
    "revision_no",
    "created_by",
    "created_at",
)
_CONTEXT_COLUMNS = (
    "context_revision_id",
    "context_id",
    "revision_no",
    "valid_from_session_time_us",
    "valid_to_session_time_us",
    "source",
    "reason",
    "changed_by",
    "created_at",
)


def _iso(value: object) -> str:
    if isinstance(value, datetime):
        current = value if value.tzinfo is not None else value.replace(tzinfo=UTC)
        return current.astimezone(UTC).isoformat().replace("+00:00", "Z")
    if isinstance(value, str) and value:
        return value
    raise BatchImportError("G4_PERSISTED_TIME_INVALID", str(value), http_status=500)


def _boolean(value: object) -> bool:
    if isinstance(value, bool):
        return value
    if value in {0, 1}:
        return bool(value)
    raise BatchImportError("G4_PERSISTED_BOOLEAN_INVALID", str(value), http_status=500)


def _integer(value: object, field: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise BatchImportError("G4_PERSISTED_INTEGER_INVALID", field, http_status=500)
    return value


def _optional(value: object) -> str | None:
    return None if value is None else str(value)


def _batch(row: dict[str, object]) -> BatchRegistrationRecord:
    return BatchRegistrationRecord(
        batch_id=str(row["batch_id"]),
        session_id=str(row["session_id"]),
        batch_date=str(row["batch_date"]),
        batch_training_type=str(row["batch_training_type"]),
        training_type_confirmed=_boolean(row["training_type_confirmed"]),
        context_id=_optional(row["context_id"]),
        release_id=_optional(row["release_id"]),
        qualification_status=str(row["qualification_status"]),
        source_manifest_sha256=str(row["source_manifest_sha256"]),
        revision_no=_integer(row["revision_no"], "revision_no"),
        created_by=str(row["created_by"]),
        created_at=_iso(row["created_at"]),
    )


class DurableBatchRepository:
    """Transactional implementation over the already-admitted DB 1.10 tables."""

    def __init__(
        self,
        read_uow_factory: RuntimeUnitOfWorkFactory,
        write_uow_factory: RuntimeUnitOfWorkFactory,
    ) -> None:
        self._read = read_uow_factory
        self._write = write_uow_factory

    def list_batches(self) -> tuple[BatchRegistrationRecord, ...]:
        with self._read() as uow:
            rows = uow.canonical_rows.many(
                "registry.batch_registration",
                where={},
                columns=_BATCH_COLUMNS,
                order_by=("batch_date", "batch_id"),
            )
        return tuple(_batch(row) for row in rows)

    def get_batch(self, batch_id: str) -> BatchRegistrationRecord | None:
        with self._read() as uow:
            row = uow.canonical_rows.one(
                "registry.batch_registration",
                where={"batch_id": batch_id},
                columns=_BATCH_COLUMNS,
            )
        return None if row is None else _batch(row)

    def create_batch(self, value: BatchRegistrationRecord, *, reason: str) -> None:
        with self._write() as uow:
            session = uow.canonical_rows.one(
                "registry.training_session",
                where={"session_id": value.session_id},
                columns=("session_id",),
            )
            if session is None:
                raise BatchImportError(
                    "G4_SESSION_NOT_FOUND", value.session_id, http_status=404
                )
            existing = uow.canonical_rows.one(
                "registry.batch_registration",
                where={"batch_id": value.batch_id},
                columns=("batch_id",),
            )
            if existing is not None:
                raise BatchImportError(
                    "G4_BATCH_ALREADY_EXISTS", value.batch_id, http_status=409
                )
            uow.canonical_rows.insert(
                "registry.batch_registration",
                {
                    "batch_id": value.batch_id,
                    "session_id": value.session_id,
                    "batch_date": value.batch_date,
                    "batch_training_type": value.batch_training_type,
                    "training_type_confirmed": value.training_type_confirmed,
                    "context_id": value.context_id,
                    "release_id": value.release_id,
                    "qualification_status": value.qualification_status,
                    "source_manifest_sha256": value.source_manifest_sha256,
                    "revision_no": value.revision_no,
                    "created_by": value.created_by,
                },
            )
            uow.audit_log.append(
                AuditLogWrite(
                    actor_id=None,
                    principal_key=value.created_by,
                    action="G4_BATCH_REGISTER",
                    object_type="BatchRegistration",
                    object_id=value.batch_id,
                    outcome="SUCCESS",
                    reason=reason,
                    details={
                        "training_type": value.batch_training_type,
                        "confirmed": value.training_type_confirmed,
                        "qualification_status": value.qualification_status,
                    },
                )
            )
            uow.commit()

    def update_qualification(
        self, batch_id: str, status: str, *, actor: str, reason: str
    ) -> BatchRegistrationRecord:
        with self._write() as uow:
            row = uow.canonical_rows.one(
                "registry.batch_registration",
                where={"batch_id": batch_id},
                columns=_BATCH_COLUMNS,
            )
            if row is None:
                raise BatchImportError("G4_BATCH_NOT_FOUND", batch_id, http_status=404)
            old = str(row["qualification_status"])
            uow.canonical_rows.update_exact(
                "registry.batch_registration",
                where={"batch_id": batch_id},
                values={"qualification_status": status},
            )
            uow.audit_log.append(
                AuditLogWrite(
                    actor_id=None,
                    principal_key=actor,
                    action="G4_BATCH_QUALIFICATION_TRANSITION",
                    object_type="BatchRegistration",
                    object_id=batch_id,
                    outcome="SUCCESS" if status != "FAILED" else "FAILED",
                    reason=reason,
                    details={"from": old, "to": status},
                )
            )
            uow.commit()
        result = self.get_batch(batch_id)
        assert result is not None
        return result

    def revise_training_type(
        self,
        batch_id: str,
        training_type: str,
        *,
        actor: str,
        reason: str,
    ) -> BatchRegistrationRecord:
        with self._write() as uow:
            row = uow.canonical_rows.one(
                "registry.batch_registration",
                where={"batch_id": batch_id},
                columns=_BATCH_COLUMNS,
            )
            if row is None:
                raise BatchImportError("G4_BATCH_NOT_FOUND", batch_id, http_status=404)
            old = str(row["batch_training_type"])
            revision_no = _integer(row["revision_no"], "revision_no") + 1
            if old == training_type and _boolean(row["training_type_confirmed"]):
                raise BatchImportError("G4_TRAINING_TYPE_NO_CHANGE", batch_id, http_status=409)
            revision_id = str(
                uuid5(_REVISION_NAMESPACE, f"training:{batch_id}:{revision_no}:{training_type}")
            )
            uow.canonical_rows.insert(
                "registry.batch_training_type_revision",
                {
                    "revision_id": revision_id,
                    "batch_id": batch_id,
                    "revision_no": revision_no,
                    "old_training_type": old,
                    "new_training_type": training_type,
                    "reason": reason,
                    "changed_by": actor,
                },
            )
            uow.canonical_rows.update_exact(
                "registry.batch_registration",
                where={"batch_id": batch_id},
                values={
                    "batch_training_type": training_type,
                    "training_type_confirmed": True,
                    "revision_no": revision_no,
                },
            )
            uow.audit_log.append(
                AuditLogWrite(
                    actor_id=None,
                    principal_key=actor,
                    action="G4_BATCH_TRAINING_TYPE_REVISE",
                    object_type="BatchTrainingTypeRevision",
                    object_id=revision_id,
                    outcome="SUCCESS",
                    reason=reason,
                    details={"batch_id": batch_id, "old": old, "new": training_type},
                )
            )
            uow.commit()
        result = self.get_batch(batch_id)
        assert result is not None
        return result

    def get_context(self, context_id: str) -> ForceFormationRevision | None:
        with self._read() as uow:
            revisions = uow.canonical_rows.many(
                "context.force_formation_context_revision",
                where={"context_id": context_id},
                columns=_CONTEXT_COLUMNS,
                order_by=("revision_no",),
            )
            if not revisions:
                return None
            row = revisions[-1]
            revision_id = str(row["context_revision_id"])
            members = uow.canonical_rows.many(
                "context.force_formation_member",
                where={"context_revision_id": revision_id},
                columns=(
                    "aircraft_id",
                    "formation_id",
                    "side",
                    "member_role",
                    "independent_target",
                ),
                order_by=("aircraft_id",),
            )
        return ForceFormationRevision(
            context_revision_id=revision_id,
            context_id=str(row["context_id"]),
            revision_no=_integer(row["revision_no"], "revision_no"),
            valid_from_session_time_us=_integer(
                row["valid_from_session_time_us"], "valid_from_session_time_us"
            ),
            valid_to_session_time_us=(
                None
                if row["valid_to_session_time_us"] is None
                else _integer(row["valid_to_session_time_us"], "valid_to_session_time_us")
            ),
            source=str(row["source"]),
            reason=str(row["reason"]),
            changed_by=str(row["changed_by"]),
            created_at=_iso(row["created_at"]),
            members=tuple(
                ForceFormationMember(
                    aircraft_id=str(member["aircraft_id"]),
                    formation_id=_optional(member["formation_id"]),
                    side=str(member["side"]),
                    member_role=str(member["member_role"]),
                    independent_target=_boolean(member["independent_target"]),
                )
                for member in members
            ),
        )

    def revise_context(
        self,
        context_id: str,
        *,
        valid_from_session_time_us: int,
        valid_to_session_time_us: int | None,
        source: str,
        reason: str,
        actor: str,
        members: Sequence[ForceFormationMember],
    ) -> ForceFormationRevision:
        with self._write() as uow:
            prior = uow.canonical_rows.many(
                "context.force_formation_context_revision",
                where={"context_id": context_id},
                columns=("revision_no",),
                order_by=("revision_no",),
            )
            revision_no = 1 if not prior else _integer(prior[-1]["revision_no"], "revision_no") + 1
            revision_id = str(
                uuid5(_REVISION_NAMESPACE, f"context:{context_id}:{revision_no}")
            )
            uow.canonical_rows.insert(
                "context.force_formation_context_revision",
                {
                    "context_revision_id": revision_id,
                    "context_id": context_id,
                    "revision_no": revision_no,
                    "valid_from_session_time_us": valid_from_session_time_us,
                    "valid_to_session_time_us": valid_to_session_time_us,
                    "source": source,
                    "reason": reason,
                    "changed_by": actor,
                },
            )
            for member in members:
                uow.canonical_rows.insert(
                    "context.force_formation_member",
                    {
                        "context_revision_id": revision_id,
                        "aircraft_id": member.aircraft_id,
                        "formation_id": member.formation_id,
                        "side": member.side,
                        "member_role": member.member_role,
                        "independent_target": member.independent_target,
                    },
                )
            uow.audit_log.append(
                AuditLogWrite(
                    actor_id=None,
                    principal_key=actor,
                    action="G4_FORCE_FORMATION_CONTEXT_REVISE",
                    object_type="ForceFormationContextRevision",
                    object_id=revision_id,
                    outcome="SUCCESS",
                    reason=reason,
                    details={
                        "context_id": context_id,
                        "revision_no": revision_no,
                        "member_count": len(members),
                    },
                )
            )
            uow.commit()
        result = self.get_context(context_id)
        assert result is not None
        return result


__all__ = ["DurableBatchRepository"]
