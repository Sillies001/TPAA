"""Generic governed M3 training-profile projection for BVR/Strike closure."""

from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import cast
from uuid import UUID, uuid5

from .m2_reference_time import CoreWorldManifest

FIXTURE_SCHEMA = "TPAA_M3_PROFILE_WORLD_FIXTURE_V1"
CORE_SCHEMA_VERSION = "1.9.0"
STAGE_REGISTRY_VERSION = "1.1.0"
WORLD_REGISTRY_VERSION = "1.0.0"
TAXONOMY_VERSION = "1.0.0"
INTERVAL_SEMANTICS = "half-open"
EPISODE_VERSION = "M3_PROFILE_EPISODE_PROJECTOR_V1"
STAGE_VERSION = "M3_PROFILE_STAGE_PROJECTOR_V1"
EVENT_VERSION = "M3_PROFILE_STAGE_EVENT_PROJECTOR_V1"
WORLD_VERSION = "M3_PROFILE_WORLD_PROJECTOR_V1"
WORLD_KIND_BY_CODE = {
    "A": "ACTION",
    "C": "CONTEXT",
    "J": "ADJUDICATION",
    "M": "MACHINE",
    "P": "PERCEPTION",
    "W": "TRUTH",
}
EPISODE_NAMESPACE = UUID("2511623c-5bd4-4d90-8435-e15cb9375308")
STAGE_NAMESPACE = UUID("c6bb429f-48bc-48dc-a3c2-1e58465a9709")
EVENT_NAMESPACE = UUID("674a339f-e868-45aa-81dd-30cb9f59d360")
WORLD_NAMESPACE = UUID("ae21dd72-3a47-40ca-a809-190cc40dcae7")


class M3ProfileWorldError(RuntimeError):
    """Fail-closed generic M3 profile projection error."""

    def __init__(self, code: str, detail: str) -> None:
        super().__init__(f"{code}: {detail}")
        self.code = code
        self.detail = detail


@dataclass(frozen=True)
class M3ProfileEpisode:
    episode_id: str
    session_id: str
    context_id: str
    primary_aircraft_id: str
    episode_type: str
    stage_profile_id: str
    world_capability_code: str
    start_session_time_us: int
    end_session_time_us: int
    subject_scope: str = "AIRCRAFT"
    episode_status: str = "VALID"
    detector_version: str = EPISODE_VERSION
    coverage: float = 1.0
    confidence: float = 1.0
    data_sufficiency_status: str = "SUFFICIENT"
    supersedes_episode_id: str | None = None


@dataclass(frozen=True)
class M3ProfileStage:
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
class M3ProfileStageEvent:
    """Official Stage-entry evidence; not a Canonical Event persistence schema."""

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
class M3ProfileProjection:
    fixture_id: str
    fixture_sha256: str
    training_type: str
    episode_type: str
    stage_profile_id: str
    world_capability_code: str
    required_world_codes: tuple[str, ...]
    stage_registry_sha256: str
    world_registry_sha256: str
    taxonomy_sha256: str
    core_schema_sha256: str
    interval_semantics: str
    episode: M3ProfileEpisode
    stages: tuple[M3ProfileStage, ...]
    events: tuple[M3ProfileStageEvent, ...]
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
        raise M3ProfileWorldError(code, f"{path.as_posix()}: {exc}") from exc
    if not isinstance(raw, dict) or not all(isinstance(key, str) for key in raw):
        raise M3ProfileWorldError(code, f"{path.as_posix()}: root must be object")
    return cast(dict[str, object], raw)


def _obj(
    value: object,
    field: str,
    code: str = "M3_PROFILE_AUTHORITY_INVALID",
) -> dict[str, object]:
    if not isinstance(value, dict) or not all(isinstance(key, str) for key in value):
        raise M3ProfileWorldError(code, f"{field} must be object")
    return cast(dict[str, object], value)


def _str(
    mapping: dict[str, object],
    key: str,
    code: str = "M3_PROFILE_FIXTURE_INVALID",
) -> str:
    value = mapping.get(key)
    if not isinstance(value, str) or not value:
        raise M3ProfileWorldError(code, f"{key} must be non-empty string")
    return value


def _int(mapping: dict[str, object], key: str) -> int:
    value = _str(mapping, key)
    try:
        parsed = int(value)
    except ValueError as exc:
        raise M3ProfileWorldError(
            "M3_PROFILE_FIXTURE_INVALID",
            f"{key}={value!r}",
        ) from exc
    if str(parsed) != value:
        raise M3ProfileWorldError(
            "M3_PROFILE_FIXTURE_INVALID",
            f"{key} must be canonical decimal",
        )
    return parsed


def _uuid(mapping: dict[str, object], key: str) -> str:
    value = _str(mapping, key)
    try:
        parsed = UUID(value)
    except ValueError as exc:
        raise M3ProfileWorldError(
            "M3_PROFILE_UUID_INVALID",
            f"{key}={value!r}",
        ) from exc
    if parsed.int == 0 or str(parsed) != value:
        raise M3ProfileWorldError(
            "M3_PROFILE_UUID_INVALID",
            f"{key}={value!r}",
        )
    return value


def _sha(path: Path) -> str:
    try:
        return hashlib.sha256(path.read_bytes()).hexdigest()
    except OSError as exc:
        raise M3ProfileWorldError(
            "M3_PROFILE_AUTHORITY_MISSING",
            path.as_posix(),
        ) from exc


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


@dataclass(frozen=True)
class _Authority:
    ordered_stages: tuple[str, ...]
    required_world_codes: tuple[str, ...]
    stage_sha256: str
    world_sha256: str
    taxonomy_sha256: str
    core_sha256: str


def _validate_authority(
    authority_root: Path,
    *,
    training_type: str,
    episode_type: str,
    stage_profile_id: str,
    world_capability_code: str,
) -> _Authority:
    stage_path = authority_root / "STAGE_REGISTRY.json"
    world_path = authority_root / "WORLD_CAPABILITY_REGISTRY.json"
    taxonomy_path = authority_root / "TRAINING_EVALUATION_TAXONOMY.json"
    core_path = authority_root / "CORE_LOGICAL_MODEL.json"
    stage = _load(stage_path, "M3_PROFILE_STAGE_AUTHORITY_INVALID")
    world = _load(world_path, "M3_PROFILE_WORLD_AUTHORITY_INVALID")
    taxonomy = _load(taxonomy_path, "M3_PROFILE_TAXONOMY_AUTHORITY_INVALID")
    core = _load(core_path, "M3_PROFILE_CORE_AUTHORITY_INVALID")

    if (
        stage.get("registry_id") != "STAGE_REGISTRY"
        or stage.get("version") != STAGE_REGISTRY_VERSION
    ):
        raise M3ProfileWorldError(
            "M3_PROFILE_STAGE_AUTHORITY_DRIFT",
            repr(stage.get("version")),
        )
    governance = _obj(stage.get("governance"), "STAGE_REGISTRY.governance")
    if (
        governance.get("time_interval")
        != "half-open [start_session_time_us,end_session_time_us)"
    ):
        raise M3ProfileWorldError(
            "M3_PROFILE_STAGE_INTERVAL_AUTHORITY_DRIFT",
            repr(governance.get("time_interval")),
        )
    profiles = _obj(stage.get("profiles"), "STAGE_REGISTRY.profiles")
    profile = _obj(profiles.get(stage_profile_id), stage_profile_id)
    raw_stages = profile.get("ordered_stages")
    if (
        profile.get("episode_type") != episode_type
        or not isinstance(raw_stages, list)
        or not all(isinstance(item, str) for item in raw_stages)
    ):
        raise M3ProfileWorldError(
            "M3_PROFILE_STAGE_PROFILE_AUTHORITY_DRIFT",
            repr(profile),
        )
    ordered_stages = tuple(cast(list[str], raw_stages))

    if (
        world.get("registry_id") != "WORLD_CAPABILITY_REGISTRY"
        or world.get("version") != WORLD_REGISTRY_VERSION
    ):
        raise M3ProfileWorldError(
            "M3_PROFILE_WORLD_AUTHORITY_DRIFT",
            repr(world.get("version")),
        )
    capabilities = _obj(
        world.get("capabilities"),
        "WORLD_CAPABILITY_REGISTRY.capabilities",
    )
    capability = _obj(
        capabilities.get(world_capability_code),
        world_capability_code,
    )
    raw_required = capability.get("required")
    if (
        not isinstance(raw_required, list)
        or not all(isinstance(item, str) for item in raw_required)
    ):
        raise M3ProfileWorldError(
            "M3_PROFILE_WORLD_REQUIREMENTS_DRIFT",
            repr(raw_required),
        )
    required_world_codes = tuple(sorted(cast(list[str], raw_required)))
    if any(code not in WORLD_KIND_BY_CODE for code in required_world_codes):
        raise M3ProfileWorldError(
            "M3_PROFILE_WORLD_CODE_UNSUPPORTED",
            repr(required_world_codes),
        )

    if (
        taxonomy.get("registry_id") != "TRAINING_EVALUATION_TAXONOMY"
        or taxonomy.get("version") != TAXONOMY_VERSION
    ):
        raise M3ProfileWorldError(
            "M3_PROFILE_TAXONOMY_AUTHORITY_DRIFT",
            repr(taxonomy.get("version")),
        )
    training = _obj(
        taxonomy.get("training_types"),
        "TRAINING_EVALUATION_TAXONOMY.training_types",
    )
    training_record = _obj(training.get(training_type), training_type)
    if (
        training_record.get("episode_type") != episode_type
        or training_record.get("reference_stage_profile") != stage_profile_id
    ):
        raise M3ProfileWorldError(
            "M3_PROFILE_TAXONOMY_MAPPING_DRIFT",
            repr(training_record),
        )

    if core.get("db_schema_version") != CORE_SCHEMA_VERSION:
        raise M3ProfileWorldError(
            "M3_PROFILE_CORE_SCHEMA_DRIFT",
            repr(core.get("db_schema_version")),
        )
    tables = _obj(core.get("tables"), "CORE_LOGICAL_MODEL.tables")
    for name in (
        "episode.training_episode",
        "episode.episode_stage",
        "world.world_product_manifest",
    ):
        if name not in tables:
            raise M3ProfileWorldError("M3_PROFILE_CORE_TABLE_MISSING", name)

    return _Authority(
        ordered_stages=ordered_stages,
        required_world_codes=required_world_codes,
        stage_sha256=_sha(stage_path),
        world_sha256=_sha(world_path),
        taxonomy_sha256=_sha(taxonomy_path),
        core_sha256=_sha(core_path),
    )


def _parse_markers(
    fixture: dict[str, object],
    ordered_stages: tuple[str, ...],
) -> tuple[tuple[str, int], ...]:
    raw_markers = fixture.get("official_stage_markers")
    if not isinstance(raw_markers, list):
        raise M3ProfileWorldError(
            "M3_PROFILE_FIXTURE_INVALID",
            "official_stage_markers must be list",
        )
    markers: list[tuple[str, int]] = []
    for index, raw in enumerate(raw_markers):
        marker = _obj(
            raw,
            f"official_stage_markers[{index}]",
            "M3_PROFILE_FIXTURE_INVALID",
        )
        markers.append((_str(marker, "stage"), _int(marker, "session_time_us")))
    if tuple(stage for stage, _ in markers) != (*ordered_stages, "END"):
        raise M3ProfileWorldError(
            "M3_PROFILE_STAGE_MARKER_ORDER_INVALID",
            repr(markers),
        )
    return tuple(markers)


def _parse_sources(
    fixture: dict[str, object],
    required_world_codes: tuple[str, ...],
) -> tuple[tuple[str, str], ...]:
    raw_sources = fixture.get("world_sources")
    if not isinstance(raw_sources, list):
        raise M3ProfileWorldError(
            "M3_PROFILE_FIXTURE_INVALID",
            "world_sources must be list",
        )
    sources: list[tuple[str, str]] = []
    for index, raw in enumerate(raw_sources):
        source = _obj(
            raw,
            f"world_sources[{index}]",
            "M3_PROFILE_FIXTURE_INVALID",
        )
        sources.append(
            (
                _str(source, "world_code"),
                _str(source, "source_authority_signature"),
            )
        )
    if len({code for code, _ in sources}) != len(sources):
        raise M3ProfileWorldError(
            "M3_PROFILE_WORLD_SOURCE_DUPLICATE",
            repr(sources),
        )
    observed = tuple(sorted(code for code, _ in sources))
    if observed != required_world_codes:
        raise M3ProfileWorldError(
            "M3_PROFILE_REQUIRED_WORLD_MISMATCH",
            f"required={required_world_codes!r} observed={observed!r}",
        )
    return tuple(sorted(sources))


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
    stage_profile_id: str,
) -> CoreWorldManifest:
    kind = WORLD_KIND_BY_CODE[code]
    logical = {
        "session_id": session_id,
        "episode_id": episode_id,
        "stage_profile_id": stage_profile_id,
        "world_code": code,
        "world_kind": kind,
        "aircraft_id": aircraft_id,
        "start_session_time_us": start,
        "end_session_time_us": end,
        "source_authority_signature": signature,
        "world_version": f"{WORLD_VERSION}:{stage_profile_id}:{code}",
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
        world_version=f"{WORLD_VERSION}:{stage_profile_id}:{code}",
        policy_version=WORLD_REGISTRY_VERSION,
        artifact_sha256=fixture_sha256,
        logical_content_hash=logical_hash,
        request_hash=_hash(request),
        supersedes_id=None,
    )


def project_m3_training_profile(
    fixture_path: Path,
    *,
    authority_root: Path,
) -> M3ProfileProjection:
    """Project one frozen M3 Stage profile with exact authority binding."""

    fixture = _load(fixture_path, "M3_PROFILE_FIXTURE_INVALID")
    if fixture.get("schema") != FIXTURE_SCHEMA:
        raise M3ProfileWorldError(
            "M3_PROFILE_FIXTURE_SCHEMA_MISMATCH",
            repr(fixture.get("schema")),
        )
    if fixture.get("data_classification") != "SYNTHETIC":
        raise M3ProfileWorldError(
            "M3_PROFILE_CLASSIFICATION_FORBIDDEN",
            repr(fixture.get("data_classification")),
        )
    training_type = _str(fixture, "training_type")
    episode_type = _str(fixture, "episode_type")
    stage_profile_id = _str(fixture, "stage_profile_id")
    world_capability_code = _str(fixture, "world_capability_code")
    authority = _validate_authority(
        authority_root,
        training_type=training_type,
        episode_type=episode_type,
        stage_profile_id=stage_profile_id,
        world_capability_code=world_capability_code,
    )
    markers = _parse_markers(fixture, authority.ordered_stages)
    sources = _parse_sources(fixture, authority.required_world_codes)

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
        raise M3ProfileWorldError(
            "M3_PROFILE_EPISODE_BOUNDARY_INVALID",
            repr((start, end, times)),
        )
    if any(
        left >= right
        for left, right in zip(times, times[1:], strict=False)
    ):
        raise M3ProfileWorldError(
            "M3_PROFILE_STAGE_MARKER_TIME_INVALID",
            repr(times),
        )

    episode_identity = {
        "session_id": session_id,
        "context_id": context_id,
        "primary_aircraft_id": aircraft_id,
        "episode_type": episode_type,
        "stage_profile_id": stage_profile_id,
        "world_capability_code": world_capability_code,
        "start_session_time_us": start,
        "end_session_time_us": end,
        "detector_version": EPISODE_VERSION,
    }
    episode = M3ProfileEpisode(
        episode_id=_stable_id(EPISODE_NAMESPACE, episode_identity),
        session_id=session_id,
        context_id=context_id,
        primary_aircraft_id=aircraft_id,
        episode_type=episode_type,
        stage_profile_id=stage_profile_id,
        world_capability_code=world_capability_code,
        start_session_time_us=start,
        end_session_time_us=end,
    )

    stages: list[M3ProfileStage] = []
    events: list[M3ProfileStageEvent] = []
    for order, ((stage_type, stage_start), (_, stage_end)) in enumerate(
        zip(markers, markers[1:], strict=False)
    ):
        stage_identity = {
            "episode_id": episode.episode_id,
            "stage_profile_id": stage_profile_id,
            "stage_type": stage_type,
            "stage_order": order,
            "start_session_time_us": stage_start,
            "end_session_time_us": stage_end,
            "detector_version": STAGE_VERSION,
        }
        stage = M3ProfileStage(
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
            M3ProfileStageEvent(
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
                stage_profile_id=stage_profile_id,
            ),
        )
        for code, signature in sources
    )
    logical = {
        "fixture_id": fixture_id,
        "fixture_sha256": fixture_hash,
        "training_type": training_type,
        "episode_type": episode_type,
        "stage_profile_id": stage_profile_id,
        "world_capability_code": world_capability_code,
        "required_world_codes": list(authority.required_world_codes),
        "authority_hashes": [
            authority.stage_sha256,
            authority.world_sha256,
            authority.taxonomy_sha256,
            authority.core_sha256,
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
    return M3ProfileProjection(
        fixture_id=fixture_id,
        fixture_sha256=fixture_hash,
        training_type=training_type,
        episode_type=episode_type,
        stage_profile_id=stage_profile_id,
        world_capability_code=world_capability_code,
        required_world_codes=authority.required_world_codes,
        stage_registry_sha256=authority.stage_sha256,
        world_registry_sha256=authority.world_sha256,
        taxonomy_sha256=authority.taxonomy_sha256,
        core_schema_sha256=authority.core_sha256,
        interval_semantics=INTERVAL_SEMANTICS,
        episode=episode,
        stages=tuple(stages),
        events=tuple(events),
        worlds=worlds,
        logical_hash=_hash(logical),
    )
