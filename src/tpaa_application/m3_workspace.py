"""M3 four-training release-bound workspace projection.

The projector consumes only an immutable M3 Release snapshot. It does not read
current Canonical authority, persistence, Metric engines, or World projectors.
Episode/Stage identity, family applicability, status/reason semantics, and
Release provenance therefore remain exactly the values frozen at publication.
"""

from __future__ import annotations

from collections import Counter
from collections.abc import Mapping
from dataclasses import dataclass
from typing import cast

from tpaa_observation import M3ImmutableReleaseSnapshot

M3_WORKSPACE_EVIDENCE_CONTRACT = "M3_API_002_WORKSPACE_EVIDENCE_V1"
M3_WORKSPACE_METRIC_COUNT = 116
M3_WORKSPACE_TRAINING_KEYS = ("BASIC", "WVR", "BVR", "STRIKE")
M3_WORKSPACE_RESULT_STATUSES = frozenset(
    {"VALID", "N_A", "INSUFFICIENT_DATA", "INVALID", "REVIEW_REQUIRED"}
)


class M3WorkspaceProjectionError(RuntimeError):
    """Fail-closed workspace projection error over immutable Release data."""

    def __init__(self, code: str, detail: str) -> None:
        self.code = code
        self.detail = detail
        super().__init__(f"{code}: {detail}")


@dataclass(frozen=True)
class M3WorkspaceIdentity:
    training_key: str
    episode_type: str
    stage_profile_id: str
    episode_id: str
    stage_id: str
    stage_code: str

    def projection(self) -> dict[str, object]:
        return {
            "training_key": self.training_key,
            "episode_type": self.episode_type,
            "stage_profile_id": self.stage_profile_id,
            "episode_id": self.episode_id,
            "stage_id": self.stage_id,
            "stage_code": self.stage_code,
        }


def _text(value: object, *, field: str) -> str:
    if not isinstance(value, str) or not value:
        raise M3WorkspaceProjectionError(
            "M3_WORKSPACE_FIELD_INVALID",
            field,
        )
    return value


def _string_list(
    value: object,
    *,
    field: str,
    required: bool = False,
) -> tuple[str, ...]:
    if not isinstance(value, list) or not all(
        isinstance(item, str) and item for item in value
    ):
        raise M3WorkspaceProjectionError(
            "M3_WORKSPACE_REASON_CODES_INVALID",
            field,
        )
    result = tuple(cast(list[str], value))
    if required and not result:
        raise M3WorkspaceProjectionError(
            "M3_WORKSPACE_REASON_CODES_REQUIRED",
            field,
        )
    return result


def _mapping(value: object, *, field: str) -> dict[str, object]:
    if not isinstance(value, dict) or not all(
        isinstance(key, str) for key in value
    ):
        raise M3WorkspaceProjectionError(
            "M3_WORKSPACE_PAYLOAD_INVALID",
            field,
        )
    return cast(dict[str, object], value)


def _identity(payload: Mapping[str, object]) -> M3WorkspaceIdentity:
    training_key = _text(payload.get("training_key"), field="training_key")
    if training_key not in M3_WORKSPACE_TRAINING_KEYS:
        raise M3WorkspaceProjectionError(
            "M3_WORKSPACE_TRAINING_KEY_INVALID",
            training_key,
        )
    return M3WorkspaceIdentity(
        training_key=training_key,
        episode_type=_text(payload.get("episode_type"), field="episode_type"),
        stage_profile_id=_text(
            payload.get("stage_profile_id"),
            field="stage_profile_id",
        ),
        episode_id=_text(payload.get("episode_id"), field="episode_id"),
        stage_id=_text(payload.get("stage_id"), field="stage_id"),
        stage_code=_text(payload.get("stage_code"), field="stage_code"),
    )


def _family_code(metric_code: str) -> str:
    parts = metric_code.split("-")
    if len(parts) != 3 or parts[0] != "P1":
        raise M3WorkspaceProjectionError(
            "M3_WORKSPACE_METRIC_CODE_INVALID",
            metric_code,
        )
    return f"P1-{parts[1]}-*"


def _metric_projection(
    release: M3ImmutableReleaseSnapshot,
    metric_code: str,
    payload: Mapping[str, object],
) -> dict[str, object]:
    definition = release.definition(metric_code)
    evidence = release.evidence(metric_code)
    family_code = _text(payload.get("family_code"), field=f"{metric_code}.family_code")
    if family_code != _family_code(metric_code):
        raise M3WorkspaceProjectionError(
            "M3_WORKSPACE_FAMILY_DRIFT",
            f"{metric_code}:{family_code}",
        )

    applicable = payload.get("applicable")
    if not isinstance(applicable, bool):
        raise M3WorkspaceProjectionError(
            "M3_WORKSPACE_APPLICABILITY_INVALID",
            metric_code,
        )
    system_type = payload.get("system_type")
    if system_type is not None and (
        not isinstance(system_type, str) or not system_type
    ):
        raise M3WorkspaceProjectionError(
            "M3_WORKSPACE_SYSTEM_TYPE_INVALID",
            metric_code,
        )
    applicability_reasons = _string_list(
        payload.get("applicability_reason_codes"),
        field=f"{metric_code}.applicability_reason_codes",
        required=not applicable,
    )
    raw_instances = payload.get("instances")
    if not isinstance(raw_instances, list):
        raise M3WorkspaceProjectionError(
            "M3_WORKSPACE_INSTANCES_INVALID",
            metric_code,
        )
    if not applicable and raw_instances:
        raise M3WorkspaceProjectionError(
            "M3_WORKSPACE_NOT_APPLICABLE_INSTANCE_FORBIDDEN",
            metric_code,
        )
    if applicable and not raw_instances:
        raise M3WorkspaceProjectionError(
            "M3_WORKSPACE_APPLICABLE_INSTANCE_REQUIRED",
            metric_code,
        )

    instances: list[dict[str, object]] = []
    for index, raw in enumerate(raw_instances):
        instance = _mapping(raw, field=f"{metric_code}.instances[{index}]")
        status = _text(
            instance.get("status"),
            field=f"{metric_code}.instances[{index}].status",
        )
        if status not in M3_WORKSPACE_RESULT_STATUSES:
            raise M3WorkspaceProjectionError(
                "M3_WORKSPACE_STATUS_INVALID",
                f"{metric_code}:{status}",
            )
        reasons = _string_list(
            instance.get("reason_codes"),
            field=f"{metric_code}.instances[{index}].reason_codes",
            required=status != "VALID",
        )
        instances.append(
            {
                "status": status,
                "reason_codes": list(reasons),
            }
        )

    return {
        "release_id": release.release_id,
        "metric_code": metric_code,
        "family_code": family_code,
        "definition_hash": definition.definition_hash,
        "evidence_hash": evidence.evidence_hash,
        "subject_type": definition.subject_type,
        "observation_lane": definition.observation_lane,
        "publication_route": definition.publication_route,
        "applicability": {
            "applicable": applicable,
            "reason_codes": list(applicability_reasons),
            "system_type": system_type,
        },
        "instances": instances,
    }


def project_m3_workspace(
    release: M3ImmutableReleaseSnapshot,
) -> dict[str, object]:
    """Project one exact four-training workspace from frozen Release Evidence."""

    if (
        len(release.definitions) != M3_WORKSPACE_METRIC_COUNT
        or len(release.evidence_bindings) != M3_WORKSPACE_METRIC_COUNT
    ):
        raise M3WorkspaceProjectionError(
            "M3_WORKSPACE_RELEASE_MEMBERSHIP_INVALID",
            release.release_id,
        )

    identity: M3WorkspaceIdentity | None = None
    metrics: list[dict[str, object]] = []
    family_counts: Counter[str] = Counter()
    applicable_counts: Counter[str] = Counter()
    not_applicable_counts: Counter[str] = Counter()

    for metric_code in release.metric_codes:
        evidence = release.evidence(metric_code)
        payload = _mapping(
            __import__("json").loads(evidence.evidence_json),
            field=f"evidence[{metric_code}]",
        )
        if payload.get("workspace_contract") != M3_WORKSPACE_EVIDENCE_CONTRACT:
            raise M3WorkspaceProjectionError(
                "M3_WORKSPACE_CONTRACT_MISSING",
                metric_code,
            )
        current_identity = _identity(payload)
        if identity is None:
            identity = current_identity
        elif current_identity != identity:
            raise M3WorkspaceProjectionError(
                "M3_WORKSPACE_IDENTITY_DRIFT",
                metric_code,
            )

        metric = _metric_projection(release, metric_code, payload)
        metrics.append(metric)
        family = cast(str, metric["family_code"])
        family_counts[family] += 1
        applicability = cast(dict[str, object], metric["applicability"])
        if applicability["applicable"] is True:
            applicable_counts[family] += 1
        else:
            not_applicable_counts[family] += 1

    if identity is None:
        raise M3WorkspaceProjectionError(
            "M3_WORKSPACE_RELEASE_MEMBERSHIP_INVALID",
            release.release_id,
        )

    families = [
        {
            "family_code": family,
            "metric_count": family_counts[family],
            "applicable_count": applicable_counts[family],
            "not_applicable_count": not_applicable_counts[family],
        }
        for family in sorted(family_counts)
    ]
    return {
        "release_id": release.release_id,
        "manifest_hash": release.manifest_hash,
        "training": identity.projection(),
        "families": families,
        "metrics": metrics,
        "release_provenance": {
            "catalog_id": release.catalog_id,
            "catalog_version": release.catalog_version,
            "catalog_hash": release.catalog_hash,
            "metric_execution_plan_hash": release.metric_execution_plan_hash,
            "publication_routing_plan_hash": release.publication_routing_plan_hash,
            "execution_batch_hash": release.execution_batch_hash,
            "plugin_manifest_hash": release.plugin_manifest_hash,
            "context_hash": release.bindings.context_hash,
            "world_hash": release.bindings.world_hash,
            "identity_hash": release.bindings.identity_hash,
            "provenance_hash": release.bindings.provenance_hash,
        },
    }
