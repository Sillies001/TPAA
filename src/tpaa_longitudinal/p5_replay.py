"""M8 Batch 3 composition-aware P5 longitudinal exact-revision replay."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from typing import Protocol

from tpaa_context import M8GovernanceError, canonical_hash, utc


class P5AssessmentProjection(Protocol):
    @property
    def mission_assessment_id(self) -> str: ...
    @property
    def composition_id(self) -> str: ...
    @property
    def team_id(self) -> str | None: ...
    @property
    def assessment_spec_id(self) -> str: ...
    @property
    def assessment_spec_version(self) -> str: ...
    @property
    def approval_state(self) -> str: ...
    @property
    def as_of_utc(self) -> str: ...
    @property
    def created_at_utc(self) -> str: ...
    @property
    def supersedes_id(self) -> str | None: ...
    @property
    def logical_content_hash(self) -> str: ...


@dataclass(frozen=True)
class P5ReplayRevision:
    mission_assessment_id: str
    composition_id: str
    approval_state: str
    as_of_utc: str
    created_at_utc: str
    supersedes_id: str | None
    logical_content_hash: str


@dataclass(frozen=True)
class P5CompositionReplaySeries:
    composition_id: str
    revisions: tuple[P5ReplayRevision, ...]
    active_revision_ids: tuple[str, ...]
    series_hash: str


@dataclass(frozen=True)
class P5LongitudinalReplay:
    longitudinal_identity: str
    team_id: str | None
    comparison_descriptor_hash: str
    replay_as_of_utc: str
    composition_series: tuple[P5CompositionReplaySeries, ...]
    changed_composition: bool
    replay_hash: str


def _descriptor(revision: P5AssessmentProjection) -> dict[str, object]:
    return {
        "team_id": revision.team_id,
        "assessment_spec_id": revision.assessment_spec_id,
        "assessment_spec_version": revision.assessment_spec_version,
    }


def build_p5_longitudinal_replay(
    revisions: Sequence[P5AssessmentProjection],
    *,
    replay_as_of_utc: str,
) -> P5LongitudinalReplay:
    if not revisions:
        raise M8GovernanceError(
            "FAIL_CLOSED_P4_P5_EXACT_IDENTITY_REQUIRED",
            "P5 replay requires at least one revision",
        )
    cutoff = utc(replay_as_of_utc, field="replay_as_of_utc")
    visible = sorted(
        (
            item
            for item in revisions
            if utc(item.created_at_utc, field="created_at_utc") <= cutoff
        ),
        key=lambda item: (
            utc(item.created_at_utc, field="created_at_utc"),
            item.mission_assessment_id,
        ),
    )
    if not visible:
        raise M8GovernanceError(
            "FAIL_CLOSED_P4_P5_EXACT_IDENTITY_REQUIRED",
            "no P5 revisions available by replay_as_of_utc",
        )

    descriptor_hash = canonical_hash(_descriptor(visible[0]))
    for item in visible[1:]:
        if canonical_hash(_descriptor(item)) != descriptor_hash:
            raise M8GovernanceError(
                "FAIL_CLOSED_P4_P5_EXACT_IDENTITY_REQUIRED",
                "P5 longitudinal comparison identity mismatch",
            )

    by_id = {item.mission_assessment_id: item for item in visible}
    if len(by_id) != len(visible):
        raise M8GovernanceError(
            "FAIL_CLOSED_P4_P5_EXACT_IDENTITY_REQUIRED",
            "duplicate P5 revision identity",
        )
    for item in visible:
        if item.supersedes_id is None:
            continue
        previous = by_id.get(item.supersedes_id)
        if previous is None:
            raise M8GovernanceError(
                "FAIL_CLOSED_P4_P5_EXACT_IDENTITY_REQUIRED",
                "invalid P5 supersession reference",
            )
        if previous.composition_id != item.composition_id:
            raise M8GovernanceError(
                "FAIL_CLOSED_P4_P5_COMPOSITION_DRIFT",
                "P5 supersession cannot cross composition identity",
            )

    grouped: dict[str, list[P5AssessmentProjection]] = {}
    for item in visible:
        grouped.setdefault(item.composition_id, []).append(item)

    series: list[P5CompositionReplaySeries] = []
    for composition_id in sorted(grouped):
        rows = grouped[composition_id]
        row_ids = {item.mission_assessment_id for item in rows}
        superseded = {
            item.supersedes_id
            for item in rows
            if item.supersedes_id is not None
        }
        replay_rows = tuple(
            P5ReplayRevision(
                mission_assessment_id=item.mission_assessment_id,
                composition_id=item.composition_id,
                approval_state=item.approval_state,
                as_of_utc=item.as_of_utc,
                created_at_utc=item.created_at_utc,
                supersedes_id=item.supersedes_id,
                logical_content_hash=item.logical_content_hash,
            )
            for item in rows
        )
        active = tuple(sorted(row_ids - superseded))
        series_payload = {
            "composition_id": composition_id,
            "revisions": [
                {
                    "mission_assessment_id": row.mission_assessment_id,
                    "approval_state": row.approval_state,
                    "as_of_utc": row.as_of_utc,
                    "created_at_utc": row.created_at_utc,
                    "supersedes_id": row.supersedes_id,
                    "logical_content_hash": row.logical_content_hash,
                }
                for row in replay_rows
            ],
            "active_revision_ids": list(active),
        }
        series.append(
            P5CompositionReplaySeries(
                composition_id=composition_id,
                revisions=replay_rows,
                active_revision_ids=active,
                series_hash=canonical_hash(series_payload),
            )
        )

    identity = f"P5_LONGITUDINAL_SHA256:{descriptor_hash}"
    replay_payload = {
        "longitudinal_identity": identity,
        "replay_as_of_utc": replay_as_of_utc,
        "composition_series": [
            {
                "composition_id": item.composition_id,
                "series_hash": item.series_hash,
                "active_revision_ids": list(item.active_revision_ids),
            }
            for item in series
        ],
    }
    return P5LongitudinalReplay(
        longitudinal_identity=identity,
        team_id=visible[0].team_id,
        comparison_descriptor_hash=descriptor_hash,
        replay_as_of_utc=replay_as_of_utc,
        composition_series=tuple(series),
        changed_composition=len(series) > 1,
        replay_hash=canonical_hash(replay_payload),
    )
