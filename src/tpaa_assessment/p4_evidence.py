"""M8 Batch 2 immutable authority-approved human-machine evidence materialization."""

from __future__ import annotations

from dataclasses import dataclass

from tpaa_context import (
    M8AuthorityPolicy,
    M8GovernanceError,
    canonical_hash,
    exact_text,
)
from tpaa_world import P4InteractionScopeSnapshot

from .p4_subject import P4SubjectContext


@dataclass(frozen=True)
class P4HumanMachineEvidence:
    evidence_id: str
    subject_context_id: str
    subject_key: str
    evidence_family: str
    origin: str
    evidence_set_id: str
    world_refs: tuple[str, ...]
    source_refs: tuple[str, ...]
    capability_projection_refs: tuple[str, ...]
    availability_status: str
    reason_codes: tuple[str, ...]
    numeric_value: float | int | None
    as_of_utc: str
    evidence_hash: str

    def projection(self) -> dict[str, object]:
        return {
            "evidence_id": self.evidence_id,
            "subject_context_id": self.subject_context_id,
            "subject_key": self.subject_key,
            "evidence_family": self.evidence_family,
            "origin": self.origin,
            "evidence_set_id": self.evidence_set_id,
            "world_refs": list(self.world_refs),
            "source_refs": list(self.source_refs),
            "capability_projection_refs": list(self.capability_projection_refs),
            "availability_status": self.availability_status,
            "reason_codes": list(self.reason_codes),
            "evidence_payload": {"numeric_value": self.numeric_value},
            "as_of_utc": self.as_of_utc,
            "evidence_hash": self.evidence_hash,
        }


def materialize_p4_human_machine_evidence(
    subject: P4SubjectContext,
    scope: P4InteractionScopeSnapshot,
    *,
    policy: M8AuthorityPolicy | None = None,
) -> tuple[P4HumanMachineEvidence, ...]:
    p = policy or M8AuthorityPolicy.from_canonical()
    if (
        scope.subject_context_id != subject.subject_context_id
        or scope.episode_id != subject.episode_id
        or scope.as_of_utc != subject.as_of_utc
    ):
        raise M8GovernanceError(
            "FAIL_CLOSED_P4_P5_EXACT_IDENTITY_REQUIRED",
            "subject/scope binding mismatch",
        )
    capability_refs = tuple(
        ref
        for ref in (subject.twin_revision_id, subject.p3_estimate_id)
        if ref is not None
    )
    products: list[P4HumanMachineEvidence] = []
    for source in scope.machine_evidence:
        if source.origin != "MACHINE":
            raise M8GovernanceError(
                "FAIL_CLOSED_P4_P5_MACHINE_HUMAN_EVIDENCE_CONFLATION",
                source.evidence_id,
            )
        if source.evidence_family not in p.approved_evidence_families:
            raise M8GovernanceError(
                "FAIL_CLOSED_P4_P5_EXACT_IDENTITY_REQUIRED",
                source.evidence_family,
            )
        exact_text(source.evidence_id, field="evidence_id", policy=p)
        reason_codes = (
            ()
            if source.availability_status == "AVAILABLE"
            else (f"P4_EVIDENCE_{source.availability_status}",)
        )
        payload = {
            "subject_context_id": subject.subject_context_id,
            "subject_key": subject.subject_key,
            "source_evidence_id": source.evidence_id,
            "evidence_family": source.evidence_family,
            "origin": source.origin,
            "evidence_set_id": source.evidence_set_id,
            "world_refs": list(sorted(source.world_refs)),
            "source_refs": list(sorted(source.source_refs)),
            "capability_projection_refs": list(capability_refs),
            "availability_status": source.availability_status,
            "reason_codes": list(reason_codes),
            "numeric_value": source.numeric_value,
            "as_of_utc": subject.as_of_utc,
        }
        digest = canonical_hash(payload)
        products.append(
            P4HumanMachineEvidence(
                evidence_id=f"P4_HM_EVIDENCE_SHA256:{digest}",
                subject_context_id=subject.subject_context_id,
                subject_key=subject.subject_key,
                evidence_family=source.evidence_family,
                origin="MACHINE",
                evidence_set_id=source.evidence_set_id,
                world_refs=tuple(sorted(source.world_refs)),
                source_refs=tuple(sorted(source.source_refs)),
                capability_projection_refs=capability_refs,
                availability_status=source.availability_status,
                reason_codes=reason_codes,
                numeric_value=source.numeric_value,
                as_of_utc=subject.as_of_utc,
                evidence_hash=digest,
            )
        )
    return tuple(sorted(products, key=lambda item: item.evidence_id))
