"""Qt-independent W6 semantic projections for P04-P10.

The presentation layer validates immutable identities and semantic boundaries.  It
does not calculate assessment scores, attribution, twin values, cohort aggregates,
or longitudinal statistics.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import cast


class W6ProjectionError(ValueError):
    """Fail-closed W6 presentation contract error."""


@dataclass(frozen=True, slots=True)
class AssessmentProjection:
    product_id: str
    layer: str
    subject_key: str
    scope_id: str
    approval_state: str
    validity_status: str
    claim_level: str
    as_of_utc: str
    evidence_refs: tuple[str, ...]
    participant_subject_keys: tuple[str, ...]
    supersedes_id: str | None


@dataclass(frozen=True, slots=True)
class TrendSegment:
    start_order: str
    end_order: str
    configuration_key: str
    reason: str


def _mapping(value: object, field: str) -> Mapping[str, object]:
    if not isinstance(value, Mapping):
        raise W6ProjectionError(f"W6_MAPPING_INVALID:{field}")
    return cast(Mapping[str, object], value)


def _text(value: object, field: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise W6ProjectionError(f"W6_TEXT_INVALID:{field}")
    return value


def _optional_text(value: object, field: str) -> str | None:
    if value is None:
        return None
    return _text(value, field)


def _strings(value: object, field: str) -> tuple[str, ...]:
    if not isinstance(value, Sequence) or isinstance(value, (str, bytes)):
        raise W6ProjectionError(f"W6_STRINGS_INVALID:{field}")
    if not all(isinstance(item, str) and item for item in value):
        raise W6ProjectionError(f"W6_STRINGS_INVALID:{field}")
    return tuple(cast(Sequence[str], value))


def assert_exact_id(value: object, field: str) -> str:
    exact_id = _text(value, field)
    if exact_id.casefold() in {"current", "latest"}:
        raise W6ProjectionError(f"W6_MUTABLE_ALIAS_FORBIDDEN:{field}")
    return exact_id


def build_individual_assessment(
    payload: Mapping[str, object], *, expected_id: str
) -> AssessmentProjection:
    product_id = assert_exact_id(payload.get("actor_assessment_id"), "p4.id")
    if product_id != assert_exact_id(expected_id, "expected_p4_id"):
        raise W6ProjectionError("W6_P4_IDENTITY_DRIFT")
    if _text(payload.get("layer"), "p4.layer") != "P4_INDIVIDUAL_HUMAN_MACHINE":
        raise W6ProjectionError("W6_P4_LAYER_INVALID")
    # Team output must never appear as an individual score by presentation default.
    if payload.get("team_id") is not None or payload.get("overall_score") is not None:
        raise W6ProjectionError("W6_TEAM_TO_INDIVIDUAL_FORBIDDEN")
    evidence = list(_strings(payload.get("world_refs"), "p4.world_refs"))
    evidence.extend(_strings(payload.get("machine_evidence_ids"), "p4.machine_evidence_ids"))
    raw_evidence = payload.get("evidence_set_id")
    if isinstance(raw_evidence, str) and raw_evidence:
        evidence.append(raw_evidence)
    return AssessmentProjection(
        product_id=product_id,
        layer="P4_INDIVIDUAL_HUMAN_MACHINE",
        subject_key=_text(payload.get("subject_key"), "p4.subject_key"),
        scope_id=_text(payload.get("episode_id"), "p4.episode_id"),
        approval_state=_text(payload.get("approval_state"), "p4.approval_state"),
        validity_status=_text(payload.get("p3_validity_status"), "p4.validity"),
        claim_level=_text(payload.get("p3_claim_level"), "p4.claim"),
        as_of_utc=_text(payload.get("p3_as_of_utc"), "p4.as_of"),
        evidence_refs=tuple(dict.fromkeys(evidence)),
        participant_subject_keys=(),
        supersedes_id=_optional_text(payload.get("supersedes_id"), "p4.supersedes_id"),
    )


def build_team_assessment(
    payload: Mapping[str, object], *, expected_id: str
) -> AssessmentProjection:
    product_id = assert_exact_id(payload.get("mission_assessment_id"), "p5.id")
    if product_id != assert_exact_id(expected_id, "expected_p5_id"):
        raise W6ProjectionError("W6_P5_IDENTITY_DRIFT")
    if _text(payload.get("layer"), "p5.layer") != "P5_TEAM_MISSION":
        raise W6ProjectionError("W6_P5_LAYER_INVALID")
    participants = _strings(
        payload.get("participant_subject_keys"), "p5.participant_subject_keys"
    )
    evidence = list(_strings(payload.get("world_snapshot_refs"), "p5.world_refs"))
    evidence.extend(_strings(payload.get("objective_result_refs"), "p5.objective_refs"))
    team_evidence = payload.get("team_performance_evidence_id")
    if isinstance(team_evidence, str) and team_evidence:
        evidence.append(team_evidence)
    return AssessmentProjection(
        product_id=product_id,
        layer="P5_TEAM_MISSION",
        subject_key=_text(payload.get("composition_id"), "p5.composition_id"),
        scope_id=_text(payload.get("mission_episode_id"), "p5.mission_episode_id"),
        approval_state=_text(payload.get("approval_state"), "p5.approval_state"),
        validity_status=_text(payload.get("validity_status"), "p5.validity"),
        claim_level=_text(payload.get("claim_level"), "p5.claim"),
        as_of_utc=_text(payload.get("as_of_utc"), "p5.as_of"),
        evidence_refs=tuple(dict.fromkeys(evidence)),
        participant_subject_keys=participants,
        supersedes_id=_optional_text(payload.get("supersedes_id"), "p5.supersedes_id"),
    )


def attribution_display_rows(
    *, status: str, factor_effects: Sequence[tuple[str, float]], reason_codes: Sequence[str]
) -> tuple[dict[str, object], ...]:
    """Return association-only rows and suppress deterministic values when unknown."""

    normalized = _text(status, "p2.status").upper()
    if normalized == "NOT_IDENTIFIABLE":
        if factor_effects:
            raise W6ProjectionError("W6_NOT_IDENTIFIABLE_EFFECT_FORBIDDEN")
        return tuple(
            {"factor": "Not identifiable", "association_effect": None, "reason": reason}
            for reason in reason_codes
        )
    if normalized != "IDENTIFIABLE":
        raise W6ProjectionError("W6_P2_STATUS_INVALID")
    return tuple(
        {"factor": factor, "association_effect": effect, "reason": None}
        for factor, effect in factor_effects
    )


def validate_model_profile(payload: Mapping[str, object], *, expected_id: str) -> None:
    """Validate a server-published profile; never synthesize a cohort in the GUI."""

    if assert_exact_id(payload.get("profile_id"), "profile.id") != assert_exact_id(
        expected_id, "expected_profile_id"
    ):
        raise W6ProjectionError("W6_PROFILE_IDENTITY_DRIFT")
    for field in ("aircraft_model_id", "configuration_key", "profile_version", "as_of_utc"):
        _text(payload.get(field), f"profile.{field}")
    for field in ("aircraft_count", "independent_episode_count"):
        value = payload.get(field)
        if isinstance(value, bool) or not isinstance(value, int) or value < 1:
            raise W6ProjectionError(f"W6_PROFILE_COUNT_INVALID:{field}")
    if payload.get("frontend_aggregate") is True:
        raise W6ProjectionError("W6_FRONTEND_PROFILE_AGGREGATION_FORBIDDEN")


def trend_segments(points: Sequence[Mapping[str, object]]) -> tuple[TrendSegment, ...]:
    """Expose immutable configuration breaks without calculating a business trend."""

    if not points:
        return ()
    result: list[TrendSegment] = []
    start = 0
    current = _text(points[0].get("configuration_key"), "points[0].configuration_key")
    for index in range(1, len(points) + 1):
        changed = index == len(points)
        if not changed:
            candidate = _text(
                points[index].get("configuration_key"),
                f"points[{index}].configuration_key",
            )
            changed = candidate != current
        if changed:
            result.append(
                TrendSegment(
                    start_order=str(points[start].get("session_order", "")),
                    end_order=str(points[index - 1].get("session_order", "")),
                    configuration_key=current,
                    reason="CONFIG_CHANGE" if index < len(points) else "SERIES_END",
                )
            )
            if index < len(points):
                start = index
                current = candidate
    return tuple(result)


def validate_subject_lane(subject_type: object) -> str:
    lane = _text(subject_type, "subject_type")
    if lane not in {"AIRCRAFT", "MISSION_SYSTEM_INSTANCE", "HUMAN", "TEAM"}:
        raise W6ProjectionError("W6_SUBJECT_LANE_INVALID")
    return lane


__all__ = [
    "AssessmentProjection",
    "TrendSegment",
    "W6ProjectionError",
    "assert_exact_id",
    "attribution_display_rows",
    "build_individual_assessment",
    "build_team_assessment",
    "trend_segments",
    "validate_model_profile",
    "validate_subject_lane",
]
