"""M3-WORLD-001 deterministic WVR Episode/Stage/Event/World projection."""

from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import cast
from uuid import UUID, uuid5

from .m2_reference_time import CoreWorldManifest

FIXTURE_SCHEMA = "TPAA_M3_WVR_WORLD_FIXTURE_V1"
STAGE_PROFILE_ID = "WVR_ENGAGEMENT_V1"
EPISODE_TYPE = "WVR_ENGAGEMENT"
WORLD_CAPABILITY_CODE = "WVR_CORE"
EXPECTED_STAGE_ORDER = (
    "MERGE",
    "POSITION_ADVANTAGE",
    "MANEUVER",
    "WEAPON_ENVELOPE",
    "LAUNCH",
    "KILL_ASSESSMENT",
)
EXPECTED_WORLD_CODES = ("A", "C", "M", "W")
WORLD_KIND_BY_CODE = {"A": "ACTION", "C": "CONTEXT", "M": "MACHINE", "W": "TRUTH"}
CORE_SCHEMA_VERSION = "1.6.0"
STAGE_REGISTRY_VERSION = "1.1.0"
WORLD_REGISTRY_VERSION = "1.0.0"
TAXONOMY_VERSION = "1.0.0"
INTERVAL_SEMANTICS = "half-open"
EPISODE_VERSION = "M3_WVR_EPISODE_PROJECTOR_V1"
STAGE_VERSION = "M3_WVR_STAGE_PROJECTOR_V1"
EVENT_VERSION = "M3_WVR_STAGE_EVENT_PROJECTOR_V1"
WORLD_VERSION = "M3_WVR_WORLD_PROJECTOR_V1"
EPISODE_NAMESPACE = UUID("1a66cff0-e835-4940-9062-fdca9f672178")
STAGE_NAMESPACE = UUID("aeac21ab-67b6-4fd7-a71d-a7d74e34cf10")
EVENT_NAMESPACE = UUID("9f32b84d-f50a-42d4-9d05-012096f7d2c9")
WORLD_NAMESPACE = UUID("8dd44d47-59a7-4b64-a386-2173611775a1")


class M3WVRWorldError(RuntimeError):
    """Fail-closed M3-WORLD-001 error with stable reason code."""

    def __init__(self, code: str, detail: str) -> None:
        super().__init__(f"{code}: {detail}")
        self.code = code
        self.detail = detail


@dataclass(frozen=True)
class M3WVREpisode:
    episode_id: str
    session_id: str
    context_id: str
    primary_aircraft_id: str
    start_session_time_us: int
    end_session_time_us: int
    episode_type: str = EPISODE_TYPE
    subject_scope: str = "AIRCRAFT"
    world_capability_code: str = WORLD_CAPABILITY_CODE
    episode_status: str = "VALID"
    detector_version: str = EPISODE_VERSION
    coverage: float = 1.0
    confidence: float = 1.0
    data_sufficiency_status: str = "SUFFICIENT"
    supersedes_episode_id: str | None = None


@dataclass(frozen=True)
class M3WVRStage:
    stage_id: str
    episode_id: str
    stage_type: str
    stage_order: int
    start_session_time_us: int
    end_session_time_us: int
    detection_method: str = "CONTEXT"
    stage_status: str = "VALID"
    coverage: float = 1.0
    confidence: float = 1.0
    detector_version: str = STAGE_VERSION
    supersedes_stage_id: str | None = None


@dataclass(frozen=True)
class M3WVRStageEvent:
    """Official Stage-entry marker evidence; not a persistence schema."""

    event_id: str
    episode_id: str
    stage_id: str
    stage_type: str
    session_time_us: int
    logical_hash: str
    event_type: str = "STAGE_ENTRY_MARKER"
    authority_source: str = "CONTEXT_OFFICIAL_MARKER"
    projector_version: str = EVENT_VERSION


@dataclass(frozen=True)
class M3WVRProjection:
    fixture_id: str
    fixture_sha256: str
    stage_registry_sha256: str
    world_registry_sha256: str
    taxonomy_sha256: str
    core_schema_sha256: str
    stage_profile_id: str
    interval_semantics: str
    episode: M3WVREpisode
    stages: tuple[M3WVRStage, ...]
    events: tuple[M3WVRStageEvent, ...]
    worlds: tuple[tuple[str, CoreWorldManifest], ...]
    logical_hash: str
    shadow_stage_schema_created: bool = False
    event_persistence_schema_created: bool = False
    canonical_authority_mutated: bool = False
    persistence_executed: bool = False
    metric_logic_executed: bool = False
    observation_projection_executed: bool = False
    release_publication_executed: bool = False


def _load(path: Path, code: str) -> dict[str, object]:
    try:
        raw: object = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise M3WVRWorldError(code, f"{path.as_posix()}: {exc}") from exc
    if not isinstance(raw, dict) or not all(isinstance(key, str) for key in raw):
        raise M3WVRWorldError(code, f"{path.as_posix()}: root must be object")
    return cast(dict[str, object], raw)


def _obj(
    value: object,
    field: str,
    code: str = "M3_WVR_AUTHORITY_INVALID",
) -> dict[str, object]:
    if not isinstance(value, dict) or not all(isinstance(key, str) for key in value):
        raise M3WVRWorldError(code, f"{field} must be object")
    return cast(dict[str, object], value)


def _str(
    mapping: dict[str, object],
    key: str,
    code: str = "M3_WVR_FIXTURE_INVALID",
) -> str:
    value = mapping.get(key)
    if not isinstance(value, str) or not value:
        raise M3WVRWorldError(code, f"{key} must be non-empty string")
    return value


def _int(mapping: dict[str, object], key: str) -> int:
    value = _str(mapping, key)
    try:
        parsed = int(value)
    except ValueError as exc:
        raise M3WVRWorldError("M3_WVR_FIXTURE_INVALID", f"{key}={value!r}") from exc
    if str(parsed) != value:
        raise M3WVRWorldError(
            "M3_WVR_FIXTURE_INVALID",
            f"{key} must be canonical decimal",
        )
    return parsed


def _uuid(mapping: dict[str, object], key: str) -> str:
    value = _str(mapping, key)
    try:
        parsed = UUID(value)
    except ValueError as exc:
        raise M3WVRWorldError("M3_WVR_UUID_INVALID", f"{key}={value!r}") from exc
    if parsed.int == 0 or str(parsed) != value:
        raise M3WVRWorldError("M3_WVR_UUID_INVALID", f"{key}={value!r}")
    return value


def _sha(path: Path) -> str:
    try:
        return hashlib.sha256(path.read_bytes()).hexdigest()
    except OSError as exc:
        raise M3WVRWorldError("M3_WVR_AUTHORITY_MISSING", path.as_posix()) from exc


def _hash(value: object) -> str:
    return hashlib.sha256(
        json.dumps(
            value,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=True,
            allow_nan=False,
        ).encode("ascii")
    ).hexdigest()


def _stable_id(namespace: UUID, payload: object) -> str:
    return str(
        uuid5(
            namespace,
            json.dumps(
                payload,
                sort_keys=True,
                separators=(",", ":"),
                ensure_ascii=True,
            ),
        )
    )


def _validate_authority(authority_root: Path) -> tuple[str, str, str, str]:
    stage_path = authority_root / "STAGE_REGISTRY.json"
    world_path = authority_root / "WORLD_CAPABILITY_REGISTRY.json"
    taxonomy_path = authority_root / "TRAINING_EVALUATION_TAXONOMY.json"
    core_path = authority_root / "CORE_LOGICAL_MODEL.json"
    stage = _load(stage_path, "M3_WVR_STAGE_AUTHORITY_INVALID")
    world = _load(world_path, "M3_WVR_WORLD_AUTHORITY_INVALID")
    taxonomy = _load(taxonomy_path, "M3_WVR_TAXONOMY_AUTHORITY_INVALID")
    core = _load(core_path, "M3_WVR_CORE_AUTHORITY_INVALID")

    if (
        stage.get("registry_id") != "STAGE_REGISTRY"
        or stage.get("version") != STAGE_REGISTRY_VERSION
    ):
        raise M3WVRWorldError(
            "M3_WVR_STAGE_AUTHORITY_DRIFT",
            repr(stage.get("version")),
        )
    governance = _obj(stage.get("governance"), "STAGE_REGISTRY.governance")
    if (
        governance.get("time_interval")
        != "half-open [start_session_time_us,end_session_time_us)"
    ):
        raise M3WVRWorldError(
            "M3_WVR_STAGE_INTERVAL_AUTHORITY_DRIFT",
            repr(governance.get("time_interval")),
        )
    profiles = _obj(stage.get("profiles"), "STAGE_REGISTRY.profiles")
    profile = _obj(profiles.get(STAGE_PROFILE_ID), STAGE_PROFILE_ID)
    if (
        profile.get("episode_type") != EPISODE_TYPE
        or profile.get("ordered_stages") != list(EXPECTED_STAGE_ORDER)
    ):
        raise M3WVRWorldError(
            "M3_WVR_STAGE_PROFILE_AUTHORITY_DRIFT",
            repr(profile),
        )

    if (
        world.get("registry_id") != "WORLD_CAPABILITY_REGISTRY"
        or world.get("version") != WORLD_REGISTRY_VERSION
    ):
        raise M3WVRWorldError(
            "M3_WVR_WORLD_AUTHORITY_DRIFT",
            repr(world.get("version")),
        )
    capabilities = _obj(
        world.get("capabilities"),
        "WORLD_CAPABILITY_REGISTRY.capabilities",
    )
    capability = _obj(capabilities.get(WORLD_CAPABILITY_CODE), WORLD_CAPABILITY_CODE)
    required = capability.get("required")
    if (
        not isinstance(required, list)
        or not all(isinstance(item, str) for item in required)
        or tuple(sorted(cast(list[str], required))) != EXPECTED_WORLD_CODES
    ):
        raise M3WVRWorldError(
            "M3_WVR_WORLD_REQUIREMENTS_DRIFT",
            repr(required),
        )

    if (
        taxonomy.get("registry_id") != "TRAINING_EVALUATION_TAXONOMY"
        or taxonomy.get("version") != TAXONOMY_VERSION
    ):
        raise M3WVRWorldError(
            "M3_WVR_TAXONOMY_AUTHORITY_DRIFT",
            repr(taxonomy.get("version")),
        )
    training = _obj(
        taxonomy.get("training_types"),
        "TRAINING_EVALUATION_TAXONOMY.training_types",
    )
    wvr = _obj(training.get("WVR"), "WVR")
    if (
        wvr.get("episode_type") != EPISODE_TYPE
        or wvr.get("reference_stage_profile") != STAGE_PROFILE_ID
    ):
        raise M3WVRWorldError("M3_WVR_TAXONOMY_MAPPING_DRIFT", repr(wvr))

    if core.get("db_schema_version") != CORE_SCHEMA_VERSION:
        raise M3WVRWorldError(
            "M3_WVR_CORE_SCHEMA_DRIFT",
            repr(core.get("db_schema_version")),
        )
    tables = _obj(core.get("tables"), "CORE_LOGICAL_MODEL.tables")
    for name in (
        "episode.training_episode",
        "episode.episode_stage",
        "world.world_product_manifest",
    ):
        if name not in tables:
            raise M3WVRWorldError("M3_WVR_CORE_TABLE_MISSING", name)

    return _sha(stage_path), _sha(world_path), _sha(taxonomy_path), _sha(core_path)


def _parse_fixture(
    path: Path,
) -> tuple[
    dict[str, object],
    tuple[tuple[str, int], ...],
    tuple[tuple[str, str], ...],
]:
    fixture = _load(path, "M3_WVR_FIXTURE_INVALID")
    if fixture.get("schema") != FIXTURE_SCHEMA:
        raise M3WVRWorldError(
            "M3_WVR_FIXTURE_SCHEMA_MISMATCH",
            repr(fixture.get("schema")),
        )
    if fixture.get("data_classification") != "SYNTHETIC":
        raise M3WVRWorldError(
            "M3_WVR_CLASSIFICATION_FORBIDDEN",
            repr(fixture.get("data_classification")),
        )
    if fixture.get("stage_profile_id") != STAGE_PROFILE_ID:
        raise M3WVRWorldError(
            "M3_WVR_STAGE_PROFILE_MISMATCH",
            repr(fixture.get("stage_profile_id")),
        )
    if fixture.get("world_capability_code") != WORLD_CAPABILITY_CODE:
        raise M3WVRWorldError(
            "M3_WVR_WORLD_CAPABILITY_MISMATCH",
            repr(fixture.get("world_capability_code")),
        )

    raw_markers = fixture.get("official_stage_markers")
    if not isinstance(raw_markers, list):
        raise M3WVRWorldError(
            "M3_WVR_FIXTURE_INVALID",
            "official_stage_markers must be list",
        )
    markers: list[tuple[str, int]] = []
    for index, raw in enumerate(raw_markers):
        marker = _obj(
            raw,
            f"official_stage_markers[{index}]",
            "M3_WVR_FIXTURE_INVALID",
        )
        markers.append((_str(marker, "stage"), _int(marker, "session_time_us")))
    if tuple(stage for stage, _ in markers) != (*EXPECTED_STAGE_ORDER, "END"):
        raise M3WVRWorldError(
            "M3_WVR_STAGE_MARKER_ORDER_INVALID",
            repr(markers),
        )

    raw_sources = fixture.get("world_sources")
    if not isinstance(raw_sources, list):
        raise M3WVRWorldError(
            "M3_WVR_FIXTURE_INVALID",
            "world_sources must be list",
        )
    sources: list[tuple[str, str]] = []
    for index, raw in enumerate(raw_sources):
        source = _obj(
            raw,
            f"world_sources[{index}]",
            "M3_WVR_FIXTURE_INVALID",
        )
        sources.append(
            (
                _str(source, "world_code"),
                _str(source, "source_authority_signature"),
            )
        )
    if len({code for code, _ in sources}) != len(sources):
        raise M3WVRWorldError("M3_WVR_WORLD_SOURCE_DUPLICATE", repr(sources))
    if tuple(sorted(code for code, _ in sources)) != EXPECTED_WORLD_CODES:
        raise M3WVRWorldError(
            "M3_WVR_REQUIRED_WORLD_MISSING",
            repr(sorted(code for code, _ in sources)),
        )
    return fixture, tuple(markers), tuple(sorted(sources))


def _world(
    *,
    code: str,
    signature: str,
    release_id: str,
    session_id: str,
    episode_id: str,
    aircraft_id: str,
    start: int,
    end: int,
    fixture_sha256: str,
) -> CoreWorldManifest:
    kind = WORLD_KIND_BY_CODE[code]
    logical = {
        "session_id": session_id,
        "episode_id": episode_id,
        "world_code": code,
        "world_kind": kind,
        "aircraft_id": aircraft_id,
        "start_session_time_us": start,
        "end_session_time_us": end,
        "source_authority_signature": signature,
        "world_version": f"{WORLD_VERSION}:{code}",
        "policy_version": WORLD_REGISTRY_VERSION,
        "artifact_sha256": fixture_sha256,
    }
    logical_hash = _hash(logical)
    request = {
        "release_id": release_id,
        "world_code": code,
        "logical_content_hash": logical_hash,
    }
    return CoreWorldManifest(
        world_product_id=_stable_id(WORLD_NAMESPACE, request),
        release_id=release_id,
        session_id=session_id,
        episode_id=episode_id,
        stage_id=None,
        world_kind=kind,
        subject_id=None,
        observer_id=None,
        actor_id=None,
        aircraft_id=aircraft_id,
        aircraft_instance_id=None,
        dataset_id=None,
        start_session_time_us=start,
        end_session_time_us=end,
        status="READY",
        coverage=1.0,
        confidence=1.0,
        reason_codes=(),
        source_authority_signature=signature,
        world_version=f"{WORLD_VERSION}:{code}",
        policy_version=WORLD_REGISTRY_VERSION,
        artifact_sha256=fixture_sha256,
        logical_content_hash=logical_hash,
        request_hash=_hash(request),
        supersedes_id=None,
    )


def project_m3_wvr_world(
    fixture_path: Path,
    *,
    authority_root: Path,
) -> M3WVRProjection:
    """Project WVR products using only frozen Canonical authority and fixture input."""

    stage_hash, world_hash, taxonomy_hash, core_hash = _validate_authority(
        authority_root
    )
    fixture, markers, sources = _parse_fixture(fixture_path)
    fixture_hash = _sha(fixture_path)
    fixture_id = _str(fixture, "fixture_id")
    session_id = _uuid(fixture, "session_id")
    context_id = _uuid(fixture, "context_id")
    aircraft_id = _uuid(fixture, "primary_aircraft_id")
    release_id = _uuid(fixture, "release_id")
    start = _int(fixture, "start_session_time_us")
    end = _int(fixture, "end_session_time_us")
    times = tuple(value for _, value in markers)
    if start >= end or times[0] != start or times[-1] != end:
        raise M3WVRWorldError(
            "M3_WVR_EPISODE_BOUNDARY_INVALID",
            repr((start, end, times)),
        )
    if any(
        left >= right
        for left, right in zip(times, times[1:], strict=False)
    ):
        raise M3WVRWorldError("M3_WVR_STAGE_MARKER_TIME_INVALID", repr(times))

    episode_identity = {
        "session_id": session_id,
        "context_id": context_id,
        "primary_aircraft_id": aircraft_id,
        "episode_type": EPISODE_TYPE,
        "world_capability_code": WORLD_CAPABILITY_CODE,
        "start_session_time_us": start,
        "end_session_time_us": end,
        "detector_version": EPISODE_VERSION,
    }
    episode = M3WVREpisode(
        episode_id=_stable_id(EPISODE_NAMESPACE, episode_identity),
        session_id=session_id,
        context_id=context_id,
        primary_aircraft_id=aircraft_id,
        start_session_time_us=start,
        end_session_time_us=end,
    )

    stages: list[M3WVRStage] = []
    events: list[M3WVRStageEvent] = []
    for order, ((stage_type, stage_start), (_, stage_end)) in enumerate(
        zip(markers, markers[1:], strict=False)
    ):
        stage_identity = {
            "episode_id": episode.episode_id,
            "stage_profile_id": STAGE_PROFILE_ID,
            "stage_type": stage_type,
            "stage_order": order,
            "start_session_time_us": stage_start,
            "end_session_time_us": stage_end,
            "detector_version": STAGE_VERSION,
        }
        stage = M3WVRStage(
            stage_id=_stable_id(STAGE_NAMESPACE, stage_identity),
            episode_id=episode.episode_id,
            stage_type=stage_type,
            stage_order=order,
            start_session_time_us=stage_start,
            end_session_time_us=stage_end,
        )
        stages.append(stage)
        event_identity = {
            "episode_id": episode.episode_id,
            "stage_id": stage.stage_id,
            "stage_type": stage_type,
            "session_time_us": stage_start,
            "event_type": "STAGE_ENTRY_MARKER",
            "authority_source": "CONTEXT_OFFICIAL_MARKER",
            "projector_version": EVENT_VERSION,
        }
        events.append(
            M3WVRStageEvent(
                event_id=_stable_id(EVENT_NAMESPACE, event_identity),
                episode_id=episode.episode_id,
                stage_id=stage.stage_id,
                stage_type=stage_type,
                session_time_us=stage_start,
                logical_hash=_hash(event_identity),
            )
        )

    worlds = tuple(
        (
            code,
            _world(
                code=code,
                signature=signature,
                release_id=release_id,
                session_id=session_id,
                episode_id=episode.episode_id,
                aircraft_id=aircraft_id,
                start=start,
                end=end,
                fixture_sha256=fixture_hash,
            ),
        )
        for code, signature in sources
    )
    logical = {
        "fixture_id": fixture_id,
        "fixture_sha256": fixture_hash,
        "authority_hashes": [
            stage_hash,
            world_hash,
            taxonomy_hash,
            core_hash,
        ],
        "episode": asdict(episode),
        "stages": [asdict(stage) for stage in stages],
        "events": [asdict(event) for event in events],
        "worlds": [
            {
                "world_code": code,
                "world_kind": manifest.world_kind,
                "world_version": manifest.world_version,
                "logical_content_hash": manifest.logical_content_hash,
            }
            for code, manifest in worlds
        ],
    }
    return M3WVRProjection(
        fixture_id=fixture_id,
        fixture_sha256=fixture_hash,
        stage_registry_sha256=stage_hash,
        world_registry_sha256=world_hash,
        taxonomy_sha256=taxonomy_hash,
        core_schema_sha256=core_hash,
        stage_profile_id=STAGE_PROFILE_ID,
        interval_semantics=INTERVAL_SEMANTICS,
        episode=episode,
        stages=tuple(stages),
        events=tuple(events),
        worlds=worlds,
        logical_hash=_hash(logical),
    )
