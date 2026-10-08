"""Production BASIC_FLIGHT_V1 Stage projection from governed SCENARIO input."""

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import cast
from uuid import UUID, uuid5

PRODUCTION_STAGE_PROFILE_ID = "BASIC_FLIGHT_V1"
PRODUCTION_STAGE_PROJECTOR_VERSION = "ED2_B1_BASIC_FLIGHT_STAGE_PROJECTOR_V1"
PRODUCTION_STAGE_PRECEDENCE_SOURCE = "CONTEXT_OFFICIAL_MARKER"
PRODUCTION_STAGE_DETECTION_METHOD = "CONTEXT"
PRODUCTION_STAGE_TERMINATOR = "END"
PRODUCTION_STAGE_ORDER = (
    "SETUP_ENTRY",
    "EXECUTION",
    "STABILIZATION_RECOVERY",
    "COMPLETION",
)
_STAGE_NAMESPACE = UUID("9b0b5809-e19d-4f94-81ec-647421177570")


class ProductionStageError(RuntimeError):
    """Fail-closed production Stage projection error."""

    def __init__(self, code: str, detail: str) -> None:
        self.code = code
        self.detail = detail
        super().__init__(f"{code}:{detail}")


@dataclass(frozen=True, slots=True)
class ProductionStage:
    episode_id: str
    stage_id: str
    stage_profile_id: str
    stage_type: str
    stage_order: int
    start_session_time_us: int
    end_session_time_us: int
    detection_method: str
    stage_status: str
    coverage: float
    confidence: float
    detector_version: str


@dataclass(frozen=True, slots=True)
class ProductionStageProjection:
    stage_profile_id: str
    projector_version: str
    precedence_source: str
    detection_method: str
    stage_registry_sha256: str
    stages: tuple[ProductionStage, ...]
    status: str
    reason_codes: tuple[str, ...]
    logical_hash: str


def _canonical_hash(value: object) -> str:
    raw = json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
        allow_nan=False,
    ).encode("ascii")
    return hashlib.sha256(raw).hexdigest()


def _mapping(value: object, *, field: str) -> dict[str, object]:
    if not isinstance(value, Mapping) or not all(
        isinstance(key, str) for key in value
    ):
        raise ProductionStageError("ED2_STAGE_PROJECTION_INVALID", field)
    return dict(cast(Mapping[str, object], value))


def _integer(value: object, *, field: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise ProductionStageError("ED2_STAGE_PROJECTION_INVALID", field)
    return value


def _stage_registry(authority_root: Path) -> tuple[dict[str, object], str]:
    path = authority_root / "STAGE_REGISTRY.json"
    try:
        raw_bytes = path.read_bytes()
        raw: object = json.loads(raw_bytes)
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise ProductionStageError(
            "ED2_STAGE_REGISTRY_INVALID",
            path.as_posix(),
        ) from exc
    registry = _mapping(raw, field="STAGE_REGISTRY")
    if (
        registry.get("registry_id") != "STAGE_REGISTRY"
        or registry.get("version") != "1.1.0"
        or registry.get("core_baseline") != "CB-1.4.0"
    ):
        raise ProductionStageError(
            "ED2_STAGE_REGISTRY_DRIFT",
            repr(
                (
                    registry.get("registry_id"),
                    registry.get("version"),
                    registry.get("core_baseline"),
                )
            ),
        )
    profiles = _mapping(registry.get("profiles"), field="STAGE_REGISTRY.profiles")
    profile = _mapping(
        profiles.get(PRODUCTION_STAGE_PROFILE_ID),
        field=f"STAGE_REGISTRY.profiles.{PRODUCTION_STAGE_PROFILE_ID}",
    )
    order = profile.get("ordered_stages")
    if (
        not isinstance(order, list)
        or tuple(order) != PRODUCTION_STAGE_ORDER
    ):
        raise ProductionStageError(
            "ED2_STAGE_PROFILE_DRIFT",
            repr(order),
        )
    governance = _mapping(
        registry.get("governance"),
        field="STAGE_REGISTRY.governance",
    )
    precedence = governance.get("precedence")
    detection = _mapping(
        governance.get("detection_method_mapping"),
        field="STAGE_REGISTRY.governance.detection_method_mapping",
    )
    if (
        not isinstance(precedence, list)
        or not precedence
        or precedence[0] != PRODUCTION_STAGE_PRECEDENCE_SOURCE
        or detection.get(PRODUCTION_STAGE_PRECEDENCE_SOURCE)
        != PRODUCTION_STAGE_DETECTION_METHOD
    ):
        raise ProductionStageError(
            "ED2_STAGE_PRECEDENCE_DRIFT",
            repr((precedence, detection)),
        )
    return registry, hashlib.sha256(raw_bytes).hexdigest()


def _stage_id(
    *,
    episode_id: str,
    stage_type: str,
    stage_order: int,
    start_session_time_us: int,
    end_session_time_us: int,
) -> str:
    return str(
        uuid5(
            _STAGE_NAMESPACE,
            json.dumps(
                {
                    "episode_id": episode_id,
                    "stage_profile_id": PRODUCTION_STAGE_PROFILE_ID,
                    "stage_type": stage_type,
                    "stage_order": stage_order,
                    "start_session_time_us": start_session_time_us,
                    "end_session_time_us": end_session_time_us,
                    "precedence_source": PRODUCTION_STAGE_PRECEDENCE_SOURCE,
                    "detection_method": PRODUCTION_STAGE_DETECTION_METHOD,
                    "projector_version": PRODUCTION_STAGE_PROJECTOR_VERSION,
                },
                sort_keys=True,
                separators=(",", ":"),
                ensure_ascii=True,
                allow_nan=False,
            ),
        )
    )


def project_production_basic_stages(
    scenario_payload: Mapping[str, object] | None,
    *,
    episode_id: str,
    start_session_time_us: int,
    end_session_time_us: int,
    authority_root: Path,
) -> ProductionStageProjection:
    """Project governed Stage rows or return business insufficiency if SCENARIO is absent."""

    _registry, registry_hash = _stage_registry(authority_root)
    if scenario_payload is None:
        logical_hash = _canonical_hash(
            {
                "stage_profile_id": PRODUCTION_STAGE_PROFILE_ID,
                "projector_version": PRODUCTION_STAGE_PROJECTOR_VERSION,
                "stage_registry_sha256": registry_hash,
                "status": "INSUFFICIENT_DATA",
                "reason_codes": ["ED2_SOURCE_FAMILY_MISSING_SCENARIO"],
                "stages": [],
            }
        )
        return ProductionStageProjection(
            stage_profile_id=PRODUCTION_STAGE_PROFILE_ID,
            projector_version=PRODUCTION_STAGE_PROJECTOR_VERSION,
            precedence_source=PRODUCTION_STAGE_PRECEDENCE_SOURCE,
            detection_method=PRODUCTION_STAGE_DETECTION_METHOD,
            stage_registry_sha256=registry_hash,
            stages=(),
            status="INSUFFICIENT_DATA",
            reason_codes=("ED2_SOURCE_FAMILY_MISSING_SCENARIO",),
            logical_hash=logical_hash,
        )

    projection = _mapping(
        scenario_payload.get("stage_projection"),
        field="SCENARIO.stage_projection",
    )
    if set(projection) != {
        "stage_profile_id",
        "precedence_source",
        "detection_method",
        "markers",
    }:
        raise ProductionStageError(
            "ED2_STAGE_PROJECTION_INVALID",
            "stage_projection_fields",
        )
    if (
        projection.get("stage_profile_id") != PRODUCTION_STAGE_PROFILE_ID
        or projection.get("precedence_source")
        != PRODUCTION_STAGE_PRECEDENCE_SOURCE
        or projection.get("detection_method")
        != PRODUCTION_STAGE_DETECTION_METHOD
    ):
        raise ProductionStageError(
            "ED2_STAGE_PROJECTION_AUTHORITY_DRIFT",
            repr(projection),
        )

    raw_markers = projection.get("markers")
    if (
        not isinstance(raw_markers, Sequence)
        or isinstance(raw_markers, (str, bytes))
    ):
        raise ProductionStageError(
            "ED2_STAGE_PROJECTION_INVALID",
            "markers",
        )
    markers = [
        _mapping(item, field=f"markers[{index}]")
        for index, item in enumerate(raw_markers)
    ]
    expected_markers = (*PRODUCTION_STAGE_ORDER, PRODUCTION_STAGE_TERMINATOR)
    if len(markers) != len(expected_markers):
        raise ProductionStageError(
            "ED2_STAGE_MARKER_COUNT_INVALID",
            str(len(markers)),
        )
    marker_names: list[str] = []
    marker_times: list[int] = []
    for index, marker in enumerate(markers):
        if set(marker) != {"marker", "session_time_us"}:
            raise ProductionStageError(
                "ED2_STAGE_PROJECTION_INVALID",
                f"markers[{index}]",
            )
        name = marker.get("marker")
        if not isinstance(name, str) or not name:
            raise ProductionStageError(
                "ED2_STAGE_PROJECTION_INVALID",
                f"markers[{index}].marker",
            )
        marker_names.append(name)
        marker_times.append(
            _integer(
                marker.get("session_time_us"),
                field=f"markers[{index}].session_time_us",
            )
        )
    if tuple(marker_names) != expected_markers:
        raise ProductionStageError(
            "ED2_STAGE_MARKER_ORDER_INVALID",
            repr(marker_names),
        )
    if (
        marker_times[0] != start_session_time_us
        or marker_times[-1] != end_session_time_us
        or any(
            left >= right
            for left, right in zip(marker_times, marker_times[1:], strict=False)
        )
    ):
        raise ProductionStageError(
            "ED2_STAGE_MARKER_INTERVAL_INVALID",
            repr(marker_times),
        )

    stages = tuple(
        ProductionStage(
            episode_id=episode_id,
            stage_id=_stage_id(
                episode_id=episode_id,
                stage_type=stage_type,
                stage_order=index,
                start_session_time_us=marker_times[index],
                end_session_time_us=marker_times[index + 1],
            ),
            stage_profile_id=PRODUCTION_STAGE_PROFILE_ID,
            stage_type=stage_type,
            stage_order=index,
            start_session_time_us=marker_times[index],
            end_session_time_us=marker_times[index + 1],
            detection_method=PRODUCTION_STAGE_DETECTION_METHOD,
            stage_status="VALID",
            coverage=1.0,
            confidence=1.0,
            detector_version=PRODUCTION_STAGE_PROJECTOR_VERSION,
        )
        for index, stage_type in enumerate(PRODUCTION_STAGE_ORDER)
    )
    logical_hash = _canonical_hash(
        {
            "episode_id": episode_id,
            "stage_profile_id": PRODUCTION_STAGE_PROFILE_ID,
            "projector_version": PRODUCTION_STAGE_PROJECTOR_VERSION,
            "precedence_source": PRODUCTION_STAGE_PRECEDENCE_SOURCE,
            "detection_method": PRODUCTION_STAGE_DETECTION_METHOD,
            "stage_registry_sha256": registry_hash,
            "status": "READY",
            "reason_codes": [],
            "stages": [
                {
                    "stage_id": stage.stage_id,
                    "stage_type": stage.stage_type,
                    "stage_order": stage.stage_order,
                    "start_session_time_us": stage.start_session_time_us,
                    "end_session_time_us": stage.end_session_time_us,
                    "stage_status": stage.stage_status,
                    "coverage": stage.coverage,
                    "confidence": stage.confidence,
                    "detector_version": stage.detector_version,
                }
                for stage in stages
            ],
        }
    )
    return ProductionStageProjection(
        stage_profile_id=PRODUCTION_STAGE_PROFILE_ID,
        projector_version=PRODUCTION_STAGE_PROJECTOR_VERSION,
        precedence_source=PRODUCTION_STAGE_PRECEDENCE_SOURCE,
        detection_method=PRODUCTION_STAGE_DETECTION_METHOD,
        stage_registry_sha256=registry_hash,
        stages=stages,
        status="READY",
        reason_codes=(),
        logical_hash=logical_hash,
    )
