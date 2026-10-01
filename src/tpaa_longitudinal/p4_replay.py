"""M8 Batch 2 P4 longitudinal exact-revision replay without assessment imports."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from typing import Protocol

from tpaa_context import M8GovernanceError, canonical_hash, utc


class P4AssessmentProjection(Protocol):
    @property
    def actor_assessment_id(self) -> str: ...
    @property
    def subject_key(self) -> str: ...
    @property
    def role_code(self) -> str: ...
    @property
    def seat_code(self) -> str | None: ...
    @property
    def function_code(self) -> str | None: ...
    @property
    def session_id(self) -> str: ...
    @property
    def episode_id(self) -> str: ...
    @property
    def aircraft_id(self) -> str | None: ...
    @property
    def twin_revision_id(self) -> str: ...
    @property
    def assessment_spec_id(self) -> str: ...
    @property
    def assessment_spec_version(self) -> str: ...
    @property
    def role_model_version(self) -> str: ...
    @property
    def approval_state(self) -> str: ...
    @property
    def p3_as_of_utc(self) -> str: ...
    @property
    def created_at_utc(self) -> str: ...
    @property
    def supersedes_id(self) -> str | None: ...
    @property
    def logical_content_hash(self) -> str: ...


@dataclass(frozen=True)
class P4ReplayRevision:
    actor_assessment_id: str
    session_id: str
    episode_id: str
    approval_state: str
    p3_as_of_utc: str
    created_at_utc: str
    supersedes_id: str | None
    logical_content_hash: str


@dataclass(frozen=True)
class P4LongitudinalReplay:
    longitudinal_identity: str
    subject_key: str
    comparison_descriptor_hash: str
    replay_as_of_utc: str
    revisions: tuple[P4ReplayRevision, ...]
    active_revision_ids: tuple[str, ...]
    replay_hash: str


def _descriptor(revision: P4AssessmentProjection) -> dict[str, object]:
    return {
        "subject_key": revision.subject_key,
        "role_code": revision.role_code,
        "seat_code": revision.seat_code,
        "function_code": revision.function_code,
        "aircraft_id": revision.aircraft_id,
        "twin_revision_id": revision.twin_revision_id,
        "assessment_spec_id": revision.assessment_spec_id,
        "assessment_spec_version": revision.assessment_spec_version,
        "role_model_version": revision.role_model_version,
    }


def build_p4_longitudinal_replay(
    revisions: Sequence[P4AssessmentProjection],
    *,
    replay_as_of_utc: str,
) -> P4LongitudinalReplay:
    if not revisions:
        raise M8GovernanceError(
            "FAIL_CLOSED_P4_P5_EXACT_IDENTITY_REQUIRED",
            "P4 replay requires at least one revision",
        )
    cutoff = utc(replay_as_of_utc, field="replay_as_of_utc")
    ordered = sorted(
        revisions,
        key=lambda item: (utc(item.created_at_utc, field="created_at_utc"), item.actor_assessment_id),
    )
    visible = [
        item
        for item in ordered
        if utc(item.created_at_utc, field="created_at_utc") <= cutoff
    ]
    if not visible:
        raise M8GovernanceError(
            "FAIL_CLOSED_P4_P5_EXACT_IDENTITY_REQUIRED",
            "no P4 revisions available by replay_as_of_utc",
        )

    descriptor = _descriptor(visible[0])
    descriptor_hash = canonical_hash(descriptor)
    for item in visible[1:]:
        if canonical_hash(_descriptor(item)) != descriptor_hash:
            raise M8GovernanceError(
                "FAIL_CLOSED_P4_P5_EXACT_IDENTITY_REQUIRED",
                "P4 longitudinal comparison identity mismatch",
            )

    ids = {item.actor_assessment_id for item in visible}
    seen: set[str] = set()
    superseded: set[str] = set()
    replay_rows: list[P4ReplayRevision] = []
    for item in visible:
        if item.actor_assessment_id in seen:
            raise M8GovernanceError(
                "FAIL_CLOSED_P4_P5_EXACT_IDENTITY_REQUIRED",
                "duplicate P4 assessment revision identity",
            )
        seen.add(item.actor_assessment_id)
        if item.supersedes_id is not None:
            if item.supersedes_id not in ids or item.supersedes_id == item.actor_assessment_id:
                raise M8GovernanceError(
                    "FAIL_CLOSED_P4_P5_EXACT_IDENTITY_REQUIRED",
                    "invalid P4 supersession reference",
                )
            superseded.add(item.supersedes_id)
        replay_rows.append(
            P4ReplayRevision(
                actor_assessment_id=item.actor_assessment_id,
                session_id=item.session_id,
                episode_id=item.episode_id,
                approval_state=item.approval_state,
                p3_as_of_utc=item.p3_as_of_utc,
                created_at_utc=item.created_at_utc,
                supersedes_id=item.supersedes_id,
                logical_content_hash=item.logical_content_hash,
            )
        )

    active = tuple(sorted(ids - superseded))
    longitudinal_identity = f"P4_LONGITUDINAL_SHA256:{descriptor_hash}"
    replay_payload = {
        "longitudinal_identity": longitudinal_identity,
        "replay_as_of_utc": replay_as_of_utc,
        "revisions": [
            {
                "actor_assessment_id": row.actor_assessment_id,
                "session_id": row.session_id,
                "episode_id": row.episode_id,
                "approval_state": row.approval_state,
                "p3_as_of_utc": row.p3_as_of_utc,
                "created_at_utc": row.created_at_utc,
                "supersedes_id": row.supersedes_id,
                "logical_content_hash": row.logical_content_hash,
            }
            for row in replay_rows
        ],
        "active_revision_ids": list(active),
    }
    return P4LongitudinalReplay(
        longitudinal_identity=longitudinal_identity,
        subject_key=visible[0].subject_key,
        comparison_descriptor_hash=descriptor_hash,
        replay_as_of_utc=replay_as_of_utc,
        revisions=tuple(replay_rows),
        active_revision_ids=active,
        replay_hash=canonical_hash(replay_payload),
    )
