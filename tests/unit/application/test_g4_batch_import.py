from __future__ import annotations

from dataclasses import replace
from pathlib import Path
from uuid import UUID, uuid5

import pytest

from tpaa_application import (
    BatchImportError,
    BatchImportService,
    BatchRegistrationRecord,
    ForceFormationMember,
    ForceFormationRevision,
    SourceWorkflowService,
)
from tpaa_storage import LocalObjectStore

SESSION_ID = "d4100000-0000-4000-8000-000000000001"
AIRCRAFT_ID = "d4100000-0000-4000-8000-000000000002"
CONTEXT_ID = "d4100000-0000-4000-8000-000000000003"
_REVISION_NAMESPACE = UUID("7c9539a3-9d78-413e-a3dd-a1288baf54e7")


def _csv() -> bytes:
    return (
        b"source_time_us,session_time_us,p_deg_s,nz_g,heading_deg_true,"
        b"tas_kt,mach,quality_mask\n"
        b"0,0,0,1.0,0,200,0.60,0\n"
        b"100000,100000,5,1.1,10,201,0.61,0\n"
    )


class _Repository:
    def __init__(self) -> None:
        self.batches: dict[str, BatchRegistrationRecord] = {}
        self.contexts: dict[str, ForceFormationRevision] = {}
        self.audit: list[tuple[str, str]] = []

    def list_batches(self) -> tuple[BatchRegistrationRecord, ...]:
        return tuple(self.batches.values())

    def get_batch(self, batch_id: str) -> BatchRegistrationRecord | None:
        return self.batches.get(batch_id)

    def create_batch(self, value: BatchRegistrationRecord, *, reason: str) -> None:
        self.batches[value.batch_id] = value
        self.audit.append(("create", reason))

    def update_qualification(
        self, batch_id: str, status: str, *, actor: str, reason: str
    ) -> BatchRegistrationRecord:
        value = replace(self.batches[batch_id], qualification_status=status)
        self.batches[batch_id] = value
        self.audit.append((f"qualification:{actor}", reason))
        return value

    def revise_training_type(
        self, batch_id: str, training_type: str, *, actor: str, reason: str
    ) -> BatchRegistrationRecord:
        current = self.batches[batch_id]
        value = replace(
            current,
            batch_training_type=training_type,
            training_type_confirmed=True,
            revision_no=current.revision_no + 1,
        )
        self.batches[batch_id] = value
        self.audit.append((f"training:{actor}", reason))
        return value

    def get_context(self, context_id: str) -> ForceFormationRevision | None:
        return self.contexts.get(context_id)

    def revise_context(
        self,
        context_id: str,
        *,
        valid_from_session_time_us: int,
        valid_to_session_time_us: int | None,
        source: str,
        reason: str,
        actor: str,
        members: tuple[ForceFormationMember, ...],
    ) -> ForceFormationRevision:
        number = 1 if context_id not in self.contexts else self.contexts[context_id].revision_no + 1
        value = ForceFormationRevision(
            context_revision_id=str(uuid5(_REVISION_NAMESPACE, f"{context_id}:{number}")),
            context_id=context_id,
            revision_no=number,
            valid_from_session_time_us=valid_from_session_time_us,
            valid_to_session_time_us=valid_to_session_time_us,
            source=source,
            reason=reason,
            changed_by=actor,
            created_at="2026-11-06T00:00:00Z",
            members=tuple(members),
        )
        self.contexts[context_id] = value
        self.audit.append((f"context:{actor}", reason))
        return value


def _service(tmp_path: Path) -> tuple[BatchImportService, _Repository]:
    repository = _Repository()
    return (
        BatchImportService(
            repository,
            SourceWorkflowService(LocalObjectStore(tmp_path / "objects")),
        ),
        repository,
    )


def _register(service: BatchImportService, ticket_id: str, **overrides: object) -> dict[str, object]:
    values: dict[str, object] = {
        "idempotency_key": "batch-import-001",
        "actor": "g4-test-user",
        "ticket_id": ticket_id,
        "session_id": SESSION_ID,
        "aircraft_id": AIRCRAFT_ID,
        "batch_date": "2026-11-06",
        "batch_training_type": "SIMPLE_OPPOSITION",
        "training_type_confirmed": True,
        "producer_system": "RECORDER_EXPORT",
        "session_code": "G4-001",
        "session_type": "LIVE",
    }
    values.update(overrides)
    return service.register_batch(**values)  # type: ignore[arg-type]


def test_explicit_confirmation_qualifies_and_v01_lists_real_batch(tmp_path: Path) -> None:
    service, repository = _service(tmp_path)
    ticket = service.issue_ticket(kind="FILE", name="flight.csv", data=_csv())
    result = _register(service, str(ticket["ticket_id"]))

    assert result["qualification_status"] == "QUALIFIED"
    assert result["v01_eligible"] is True
    assert result["batch_training_type"] == "SIMPLE_OPPOSITION"
    assert service.list_batches()["items"] == [result]
    assert repository.audit[-1] == (
        "qualification:g4-test-user",
        "G4_SOURCE_PARSE_AND_QUALIFICATION_PASS",
    )


def test_unconfirmed_type_stays_unclassified_and_never_parses(tmp_path: Path) -> None:
    service, _repository = _service(tmp_path)
    ticket = service.issue_ticket(kind="FILE", name="flight.csv", data=_csv())
    result = _register(
        service,
        str(ticket["ticket_id"]),
        batch_training_type="UNCLASSIFIED",
        training_type_confirmed=False,
    )

    assert result["qualification_status"] == "PENDING_CONFIRMATION"
    assert result["v01_eligible"] is False
    assert result["reason_code"] == "TRAINING_TYPE_CONFIRMATION_REQUIRED"
    with pytest.raises(BatchImportError, match="G4_TRAINING_TYPE_CONFIRMATION_REQUIRED"):
        _register(
            service,
            str(ticket["ticket_id"]),
            idempotency_key="invalid-default",
            batch_training_type="COMPREHENSIVE_OPPOSITION",
            training_type_confirmed=False,
        )


def test_unclassified_batch_can_be_explicitly_confirmed_with_same_identity(
    tmp_path: Path,
) -> None:
    service, repository = _service(tmp_path)
    ticket = service.issue_ticket(kind="FILE", name="flight.csv", data=_csv())
    pending = _register(
        service,
        str(ticket["ticket_id"]),
        batch_training_type="UNCLASSIFIED",
        training_type_confirmed=False,
    )

    qualified = _register(
        service,
        str(ticket["ticket_id"]),
        batch_training_type="COMPREHENSIVE_OPPOSITION",
        training_type_confirmed=True,
    )

    assert qualified["batch_id"] == pending["batch_id"]
    assert qualified["revision_no"] == 2
    assert qualified["batch_training_type"] == "COMPREHENSIVE_OPPOSITION"
    assert qualified["qualification_status"] == "QUALIFIED"
    assert any(
        reason == "EXPLICIT_CONFIRMATION_AFTER_REGISTRATION"
        for _event, reason in repository.audit
    )


def test_invalid_csv_records_failure_and_same_identity_can_retry(tmp_path: Path) -> None:
    service, repository = _service(tmp_path)
    bad = service.issue_ticket(kind="FILE", name="flight.csv", data=b"wrong,header\n1,2\n")
    failed = _register(service, str(bad["ticket_id"]))
    assert failed["qualification_status"] == "FAILED"
    assert failed["reason_code"] == "W2_FLIGHT_CSV_SCHEMA_UNSUPPORTED"

    # The immutable manifest participates in idempotency, so changing bytes must
    # use a new key; retrying the same failed import retains one stable Batch ID.
    retried = _register(service, str(bad["ticket_id"]))
    assert retried["batch_id"] == failed["batch_id"]
    assert retried["qualification_status"] == "FAILED"
    assert any(event[1] == "G4_IMPORT_RETRY" for event in repository.audit)


def test_training_type_and_force_formation_changes_are_revisioned(tmp_path: Path) -> None:
    service, _repository = _service(tmp_path)
    ticket = service.issue_ticket(kind="FILE", name="flight.csv", data=_csv())
    batch = _register(service, str(ticket["ticket_id"]))
    revised = service.revise_training_type(
        str(batch["batch_id"]),
        training_type="MIXED_OPPOSITION",
        actor="reviewer",
        reason="复核训练构成",
    )
    assert revised["revision_no"] == 2
    assert revised["batch_training_type"] == "MIXED_OPPOSITION"

    first = service.revise_context(
        CONTEXT_ID,
        valid_from_session_time_us=0,
        valid_to_session_time_us=1_000_000,
        source="MANUAL_REVIEWED",
        reason="初始编队确认",
        actor="reviewer",
        members=(
            ForceFormationMember(
                aircraft_id=AIRCRAFT_ID,
                formation_id="BLUE-1",
                side="BLUE",
                member_role="LEAD",
                independent_target=False,
            ),
        ),
    )
    assert first["revision_no"] == 1
    assert service.get_context(CONTEXT_ID) == first


def test_directory_ticket_rejects_path_traversal(tmp_path: Path) -> None:
    import io
    import zipfile

    service, _repository = _service(tmp_path)
    stream = io.BytesIO()
    with zipfile.ZipFile(stream, "w") as archive:
        archive.writestr("../flight.csv", _csv())
    with pytest.raises(BatchImportError, match="G4_DIRECTORY_PATH_INVALID"):
        service.issue_ticket(kind="DIRECTORY", name="ignored.zip", data=stream.getvalue())
