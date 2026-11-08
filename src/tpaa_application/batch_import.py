"""G4 Batch registration, governed import tickets and context revisions.

The browser never receives a local path.  Native/Desktop or Service adapters
upload bounded immutable bytes into a short-lived ticket and the Application
layer owns validation, qualification and auditable state transitions.
"""

from __future__ import annotations

import hashlib
import io
import re
import zipfile
from collections.abc import Callable, Sequence
from dataclasses import asdict, dataclass
from datetime import UTC, date, datetime, timedelta
from enum import StrEnum
from threading import RLock
from typing import Protocol
from uuid import UUID, uuid4, uuid5

from .source_workflow import SOURCE_MAX_ARTIFACT_BYTES, SourceWorkflowError, SourceWorkflowService

_BATCH_NAMESPACE = UUID("02d70d75-47a2-4dfa-b3df-42a610e47a5a")
_SOURCE_NAMESPACE = UUID("b79908de-a715-45d5-ae4f-7850f66ec812")
_SAFE_NAME = re.compile(r"^[^/\\\x00]{1,255}$")
_MAX_DIRECTORY_MEMBERS = 32


class BatchTrainingType(StrEnum):
    SIMPLE_OPPOSITION = "SIMPLE_OPPOSITION"
    MIXED_OPPOSITION = "MIXED_OPPOSITION"
    COMPREHENSIVE_OPPOSITION = "COMPREHENSIVE_OPPOSITION"
    UNCLASSIFIED = "UNCLASSIFIED"


class BatchQualificationStatus(StrEnum):
    PENDING_CONFIRMATION = "PENDING_CONFIRMATION"
    PARSING = "PARSING"
    QUALIFIED = "QUALIFIED"
    FAILED = "FAILED"


class BatchImportError(RuntimeError):
    """Transport-safe, fail-closed G4 error."""

    def __init__(self, code: str, detail: str, *, http_status: int = 422) -> None:
        self.code = code
        self.detail = detail
        self.http_status = http_status
        super().__init__(f"{code}:{detail}")


@dataclass(frozen=True, slots=True)
class ImportTicketEntry:
    name: str
    data: bytes
    sha256: str


@dataclass(frozen=True, slots=True)
class ImportTicket:
    ticket_id: str
    kind: str
    entries: tuple[ImportTicketEntry, ...]
    manifest_sha256: str
    size_bytes: int
    expires_at: datetime


@dataclass(frozen=True, slots=True)
class BatchRegistrationRecord:
    batch_id: str
    session_id: str
    batch_date: str
    batch_training_type: str
    training_type_confirmed: bool
    context_id: str | None
    release_id: str | None
    qualification_status: str
    source_manifest_sha256: str
    revision_no: int
    created_by: str
    created_at: str


@dataclass(frozen=True, slots=True)
class ForceFormationMember:
    aircraft_id: str
    formation_id: str | None
    side: str
    member_role: str
    independent_target: bool


@dataclass(frozen=True, slots=True)
class ForceFormationRevision:
    context_revision_id: str
    context_id: str
    revision_no: int
    valid_from_session_time_us: int
    valid_to_session_time_us: int | None
    source: str
    reason: str
    changed_by: str
    created_at: str
    members: tuple[ForceFormationMember, ...]


class BatchRepository(Protocol):
    def list_batches(self) -> tuple[BatchRegistrationRecord, ...]: ...

    def get_batch(self, batch_id: str) -> BatchRegistrationRecord | None: ...

    def create_batch(self, value: BatchRegistrationRecord, *, reason: str) -> None: ...

    def update_qualification(
        self, batch_id: str, status: str, *, actor: str, reason: str
    ) -> BatchRegistrationRecord: ...

    def revise_training_type(
        self,
        batch_id: str,
        training_type: str,
        *,
        actor: str,
        reason: str,
    ) -> BatchRegistrationRecord: ...

    def get_context(self, context_id: str) -> ForceFormationRevision | None: ...

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
    ) -> ForceFormationRevision: ...


class ImportTicketStore:
    """Process-local, bounded and expiring byte tickets; no filesystem paths."""

    def __init__(
        self,
        *,
        ttl: timedelta = timedelta(minutes=10),
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        if ttl <= timedelta(0) or ttl > timedelta(hours=1):
            raise ValueError("ticket ttl must be in (0, 1 hour]")
        self._ttl = ttl
        self._clock = clock or (lambda: datetime.now(UTC))
        self._items: dict[str, ImportTicket] = {}
        self._lock = RLock()

    @staticmethod
    def _entry(name: str, data: bytes) -> ImportTicketEntry:
        if not _SAFE_NAME.fullmatch(name) or name in {".", ".."}:
            raise BatchImportError("G4_IMPORT_NAME_INVALID", name)
        if not name.lower().endswith(".csv"):
            raise BatchImportError("G4_IMPORT_MEDIA_TYPE_INVALID", name)
        if not data or len(data) > SOURCE_MAX_ARTIFACT_BYTES:
            raise BatchImportError("G4_IMPORT_SIZE_INVALID", str(len(data)), http_status=413)
        return ImportTicketEntry(name=name, data=data, sha256=hashlib.sha256(data).hexdigest())

    def issue_file(self, name: str, data: bytes) -> ImportTicket:
        return self._issue("FILE", (self._entry(name, data),))

    def issue_directory_archive(self, data: bytes) -> ImportTicket:
        if not data or len(data) > SOURCE_MAX_ARTIFACT_BYTES:
            raise BatchImportError("G4_IMPORT_SIZE_INVALID", str(len(data)), http_status=413)
        entries: list[ImportTicketEntry] = []
        try:
            with zipfile.ZipFile(io.BytesIO(data)) as archive:
                members = [item for item in archive.infolist() if not item.is_dir()]
                if not members or len(members) > _MAX_DIRECTORY_MEMBERS:
                    raise BatchImportError("G4_DIRECTORY_MEMBER_COUNT_INVALID", str(len(members)))
                total = 0
                for member in members:
                    path = member.filename.replace("\\", "/")
                    if path.startswith("/") or ".." in path.split("/"):
                        raise BatchImportError("G4_DIRECTORY_PATH_INVALID", path)
                    name = path.rsplit("/", 1)[-1]
                    payload = archive.read(member)
                    total += len(payload)
                    if total > SOURCE_MAX_ARTIFACT_BYTES:
                        raise BatchImportError(
                            "G4_IMPORT_SIZE_INVALID", str(total), http_status=413
                        )
                    entries.append(self._entry(name, payload))
        except zipfile.BadZipFile as exc:
            raise BatchImportError("G4_DIRECTORY_ARCHIVE_INVALID", "bad zip") from exc
        names = [item.name for item in entries]
        if len(names) != len(set(names)):
            raise BatchImportError("G4_DIRECTORY_DUPLICATE_NAME", "duplicate basename")
        return self._issue("DIRECTORY", tuple(sorted(entries, key=lambda item: item.name)))

    def _issue(self, kind: str, entries: tuple[ImportTicketEntry, ...]) -> ImportTicket:
        manifest = "\n".join(f"{item.name}\0{item.sha256}" for item in entries).encode("utf-8")
        now = self._clock().astimezone(UTC)
        ticket = ImportTicket(
            ticket_id=f"g4-{uuid4().hex}",
            kind=kind,
            entries=entries,
            manifest_sha256=hashlib.sha256(manifest).hexdigest(),
            size_bytes=sum(len(item.data) for item in entries),
            expires_at=now + self._ttl,
        )
        with self._lock:
            self._purge(now)
            self._items[ticket.ticket_id] = ticket
        return ticket

    def require(self, ticket_id: str) -> ImportTicket:
        now = self._clock().astimezone(UTC)
        with self._lock:
            self._purge(now)
            ticket = self._items.get(ticket_id)
        if ticket is None:
            raise BatchImportError("G4_IMPORT_TICKET_INVALID", ticket_id, http_status=404)
        return ticket

    def _purge(self, now: datetime) -> None:
        expired = [key for key, value in self._items.items() if value.expires_at <= now]
        for key in expired:
            del self._items[key]


def _uuid(value: str, field: str) -> str:
    try:
        parsed = UUID(value)
    except (ValueError, TypeError) as exc:
        raise BatchImportError("G4_ID_INVALID", field) from exc
    if parsed.int == 0 or str(parsed) != value:
        raise BatchImportError("G4_ID_INVALID", field)
    return value


def _text(value: str, field: str, *, limit: int = 512) -> str:
    if not value or value.strip() != value or len(value) > limit:
        raise BatchImportError("G4_TEXT_INVALID", field)
    return value


def _record_payload(record: BatchRegistrationRecord, *, reason_code: str | None = None) -> dict[str, object]:
    payload = asdict(record)
    payload.update(
        {
            "schema": "TPAA_G4_BATCH_REGISTRATION_V1",
            "reason_code": reason_code,
            "v01_eligible": record.qualification_status == BatchQualificationStatus.QUALIFIED,
            "provenance": {
                "authority_id": "GUI_BATCH_IMPORT_AUTHORITY",
                "authority_version": "1.0.0",
                "core_baseline": "CB-1.9.0",
            },
        }
    )
    return payload


class BatchImportService:
    """G4 Application owner for ticket, registration, qualification and context."""

    def __init__(
        self,
        repository: BatchRepository,
        source_workflow: SourceWorkflowService,
        *,
        tickets: ImportTicketStore | None = None,
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        self._repository = repository
        self._source = source_workflow
        self._tickets = tickets or ImportTicketStore()
        self._clock = clock or (lambda: datetime.now(UTC))

    def issue_ticket(self, *, kind: str, name: str, data: bytes) -> dict[str, object]:
        ticket = (
            self._tickets.issue_file(name, data)
            if kind == "FILE"
            else self._tickets.issue_directory_archive(data)
            if kind == "DIRECTORY"
            else None
        )
        if ticket is None:
            raise BatchImportError("G4_IMPORT_KIND_INVALID", kind)
        return {
            "schema": "TPAA_G4_IMPORT_TICKET_V1",
            "ticket_id": ticket.ticket_id,
            "kind": ticket.kind,
            "entry_count": len(ticket.entries),
            "size_bytes": ticket.size_bytes,
            "manifest_sha256": ticket.manifest_sha256,
            "expires_at": ticket.expires_at.isoformat().replace("+00:00", "Z"),
            "local_path": None,
        }

    def list_batches(self) -> dict[str, object]:
        records = self._repository.list_batches()
        return {
            "schema": "TPAA_G4_BATCH_LIST_V1",
            "items": [_record_payload(item) for item in records],
            "total_count": len(records),
        }

    def get_batch(self, batch_id: str) -> dict[str, object]:
        _uuid(batch_id, "batch_id")
        record = self._repository.get_batch(batch_id)
        if record is None:
            raise BatchImportError("G4_BATCH_NOT_FOUND", batch_id, http_status=404)
        return _record_payload(record)

    def register_batch(
        self,
        *,
        idempotency_key: str,
        actor: str,
        ticket_id: str,
        session_id: str,
        aircraft_id: str,
        batch_date: str,
        batch_training_type: str,
        training_type_confirmed: bool,
        producer_system: str,
        session_code: str,
        session_type: str,
        context_id: str | None = None,
        release_id: str | None = None,
    ) -> dict[str, object]:
        _text(idempotency_key, "idempotency_key", limit=128)
        _text(actor, "actor")
        _uuid(session_id, "session_id")
        _uuid(aircraft_id, "aircraft_id")
        if context_id is not None:
            _uuid(context_id, "context_id")
        if release_id is not None:
            _uuid(release_id, "release_id")
        try:
            parsed_date = date.fromisoformat(batch_date)
        except ValueError as exc:
            raise BatchImportError("G4_BATCH_DATE_INVALID", batch_date) from exc
        try:
            training_type = BatchTrainingType(batch_training_type)
        except ValueError as exc:
            raise BatchImportError("G4_TRAINING_TYPE_INVALID", batch_training_type) from exc
        if training_type_confirmed and training_type is BatchTrainingType.UNCLASSIFIED:
            raise BatchImportError("G4_EXPLICIT_TRAINING_TYPE_REQUIRED", training_type.value)
        if not training_type_confirmed and training_type is not BatchTrainingType.UNCLASSIFIED:
            raise BatchImportError("G4_TRAINING_TYPE_CONFIRMATION_REQUIRED", training_type.value)
        if session_type not in {"LIVE", "SIM", "LVC"}:
            raise BatchImportError("G4_SESSION_TYPE_INVALID", session_type)
        _text(producer_system, "producer_system")
        _text(session_code, "session_code")
        ticket = self._tickets.require(ticket_id)
        identity = f"{actor}\0{idempotency_key}"
        batch_id = str(uuid5(_BATCH_NAMESPACE, identity))
        existing = self._repository.get_batch(batch_id)
        status = (
            BatchQualificationStatus.PARSING
            if training_type_confirmed
            else BatchQualificationStatus.PENDING_CONFIRMATION
        )
        if existing is None:
            record = BatchRegistrationRecord(
                batch_id=batch_id,
                session_id=session_id,
                batch_date=parsed_date.isoformat(),
                batch_training_type=training_type.value,
                training_type_confirmed=training_type_confirmed,
                context_id=context_id,
                release_id=release_id,
                qualification_status=status.value,
                source_manifest_sha256=ticket.manifest_sha256,
                revision_no=1,
                created_by=actor,
                created_at=self._clock().astimezone(UTC).isoformat().replace("+00:00", "Z"),
            )
            self._repository.create_batch(record, reason="G4_BATCH_REGISTERED")
        else:
            invariant = (
                existing.session_id,
                existing.batch_date,
                existing.source_manifest_sha256,
                existing.created_by,
            )
            supplied = (session_id, parsed_date.isoformat(), ticket.manifest_sha256, actor)
            if invariant != supplied:
                raise BatchImportError("G4_IDEMPOTENCY_CONFLICT", batch_id, http_status=409)
            if existing.qualification_status == BatchQualificationStatus.QUALIFIED:
                return _record_payload(existing, reason_code="IDEMPOTENT_REPLAY")
            record = existing
            if training_type_confirmed and not existing.training_type_confirmed:
                record = self._repository.revise_training_type(
                    batch_id,
                    training_type.value,
                    actor=actor,
                    reason="EXPLICIT_CONFIRMATION_AFTER_REGISTRATION",
                )
                record = self._repository.update_qualification(
                    batch_id,
                    BatchQualificationStatus.PARSING.value,
                    actor=actor,
                    reason="G4_IMPORT_RETRY",
                )
            elif (
                training_type_confirmed
                and existing.qualification_status == BatchQualificationStatus.FAILED
            ):
                record = self._repository.update_qualification(
                    batch_id,
                    BatchQualificationStatus.PARSING.value,
                    actor=actor,
                    reason="G4_IMPORT_RETRY",
                )
        if not training_type_confirmed:
            return _record_payload(record, reason_code="TRAINING_TYPE_CONFIRMATION_REQUIRED")
        try:
            for index, entry in enumerate(ticket.entries):
                base = f"{batch_id}:{index}:{entry.name}"
                self._source.stage_flight_csv(
                    entry.data,
                    session_id=session_id,
                    aircraft_id=aircraft_id,
                    source_ref=f"ticket://{ticket.ticket_id}/{entry.name}",
                    raw_artifact_id=str(uuid5(_SOURCE_NAMESPACE, f"raw:{base}")),
                    canonical_artifact_id=str(uuid5(_SOURCE_NAMESPACE, f"canonical:{base}")),
                    source_id=str(uuid5(_SOURCE_NAMESPACE, f"source:{base}")),
                    source_stream_id=str(uuid5(_SOURCE_NAMESPACE, f"stream:{base}")),
                    producer_system=producer_system,
                    session_code=session_code,
                    session_type=session_type,
                )
        except SourceWorkflowError as exc:
            failed = self._repository.update_qualification(
                batch_id,
                BatchQualificationStatus.FAILED.value,
                actor=actor,
                reason=exc.code,
            )
            return _record_payload(failed, reason_code=exc.code)
        qualified = self._repository.update_qualification(
            batch_id,
            BatchQualificationStatus.QUALIFIED.value,
            actor=actor,
            reason="G4_SOURCE_PARSE_AND_QUALIFICATION_PASS",
        )
        return _record_payload(qualified)

    def revise_training_type(
        self, batch_id: str, *, training_type: str, actor: str, reason: str
    ) -> dict[str, object]:
        _uuid(batch_id, "batch_id")
        _text(actor, "actor")
        _text(reason, "reason")
        try:
            parsed = BatchTrainingType(training_type)
        except ValueError as exc:
            raise BatchImportError("G4_TRAINING_TYPE_INVALID", training_type) from exc
        if parsed is BatchTrainingType.UNCLASSIFIED:
            raise BatchImportError("G4_EXPLICIT_TRAINING_TYPE_REQUIRED", training_type)
        return _record_payload(
            self._repository.revise_training_type(
                batch_id, parsed.value, actor=actor, reason=reason
            )
        )

    def get_context(self, context_id: str) -> dict[str, object]:
        _uuid(context_id, "context_id")
        value = self._repository.get_context(context_id)
        if value is None:
            raise BatchImportError("G4_CONTEXT_NOT_FOUND", context_id, http_status=404)
        return self._context_payload(value)

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
    ) -> dict[str, object]:
        _uuid(context_id, "context_id")
        _text(source, "source")
        _text(reason, "reason")
        _text(actor, "actor")
        if isinstance(valid_from_session_time_us, bool) or valid_from_session_time_us < 0:
            raise BatchImportError("G4_CONTEXT_INTERVAL_INVALID", "valid_from")
        if valid_to_session_time_us is not None and (
            isinstance(valid_to_session_time_us, bool)
            or valid_to_session_time_us <= valid_from_session_time_us
        ):
            raise BatchImportError("G4_CONTEXT_INTERVAL_INVALID", "valid_to")
        if not members:
            raise BatchImportError("G4_CONTEXT_MEMBERS_REQUIRED", context_id)
        seen: set[str] = set()
        normalized: list[ForceFormationMember] = []
        for member in members:
            _uuid(member.aircraft_id, "aircraft_id")
            if member.aircraft_id in seen:
                raise BatchImportError("G4_CONTEXT_AIRCRAFT_DUPLICATE", member.aircraft_id)
            seen.add(member.aircraft_id)
            if member.side not in {"RED", "BLUE", "NEUTRAL", "UNASSIGNED", "CONFLICT"}:
                raise BatchImportError("G4_CONTEXT_SIDE_INVALID", member.side)
            _text(member.member_role, "member_role")
            if member.formation_id is not None:
                _text(member.formation_id, "formation_id")
            normalized.append(member)
        return self._context_payload(
            self._repository.revise_context(
                context_id,
                valid_from_session_time_us=valid_from_session_time_us,
                valid_to_session_time_us=valid_to_session_time_us,
                source=source,
                reason=reason,
                actor=actor,
                members=tuple(normalized),
            )
        )

    @staticmethod
    def _context_payload(value: ForceFormationRevision) -> dict[str, object]:
        payload = asdict(value)
        payload.update(
            {
                "schema": "TPAA_G4_FORCE_FORMATION_CONTEXT_V1",
                "provenance": {
                    "authority_id": "GUI_BATCH_IMPORT_AUTHORITY",
                    "authority_version": "1.0.0",
                    "core_baseline": "CB-1.9.0",
                },
            }
        )
        return payload


__all__ = [
    "BatchImportError",
    "BatchImportService",
    "BatchQualificationStatus",
    "BatchRegistrationRecord",
    "BatchRepository",
    "BatchTrainingType",
    "ForceFormationMember",
    "ForceFormationRevision",
    "ImportTicketStore",
]
