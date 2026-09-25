"""M2-DATA-003 mission-system ingest, identity, and SNS applicability.

The adapter projects one governed synthetic mission-system fixture into the
frozen Core 1.6.0 master.mission_system_instance identity shape. It enforces
the P1-SNS-* family applicability contract (MISSION_SYSTEM_INSTANCE,
SYSTEM_TYPE_EXACT, RADAR) before returning a projection. Non-RADAR fixtures
fail closed and no Metric, Stage, persistence, or publication logic executes.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path
from typing import cast
from uuid import UUID

EXPECTED_MANIFEST_SCHEMA = "TPAA_M2_MISSION_SYSTEM_FIXTURE_V1"
EXPECTED_SOURCE_SCHEMA = "TPAA_M2_MISSION_SYSTEM_SOURCE_V1"
EXPECTED_FIXTURE_VERSION = "1.0.0"
EXPECTED_CLASSIFICATION = "SYNTHETIC"
EXPECTED_HASH_ALGORITHM = "SHA256_FILE_V1"
EXPECTED_SOURCE_RELATIVE_PATH = "source/mission-system.json"
EXPECTED_CORE_BASELINE = "CB-1.4.0"
EXPECTED_CORE_TABLE = "master.mission_system_instance"
EXPECTED_CORE_LOGICAL_MODEL_SHA256 = (
    "cfde6638e6899167267375c899bff2f04a490ce12f32e0005be4e15dda956245"
)
EXPECTED_P1_METRIC_CATALOG_SHA256 = (
    "24ab6d06ced0b768ff16e4c945e778cc8fd2d3838be3ca30051ec8f8e0d7277d"
)
EXPECTED_METRIC_FAMILY = "P1-SNS-*"
EXPECTED_SUBJECT_TYPE = "MISSION_SYSTEM_INSTANCE"
EXPECTED_APPLICABILITY_MODE = "SYSTEM_TYPE_EXACT"
EXPECTED_ALLOWED_SYSTEM_TYPES = ("RADAR",)
CORE_SYSTEM_TYPES = (
    "RADAR",
    "IRST",
    "EO",
    "RWR",
    "ESM",
    "DATALINK",
    "FUSION",
    "MISSION_COMPUTER",
    "OTHER",
)
CORE_STATUSES = ("ACTIVE", "INACTIVE", "RETIRED")
GOVERNED_FIXTURE_IDS = ("MSI_M2_RADAR_V1", "MSI_M2_IRST_NEGATIVE_V1")


class M2MissionSystemError(RuntimeError):
    """Deterministic fail-closed M2 mission-system adapter error."""

    def __init__(self, code: str, detail: str) -> None:
        super().__init__(f"{code}: {detail}")
        self.code = code
        self.detail = detail


@dataclass(frozen=True)
class MissionSystemIdentity:
    identity_ref: str
    source_entity_key: str


@dataclass(frozen=True)
class MissionSystemInstance:
    mission_system_instance_id: str
    aircraft_id: str
    system_type: str
    system_code: str
    hardware_version: str | None
    software_version: str | None
    installation_id: str | None
    alignment_profile_version: str | None
    status: str
    configuration_hash: str


@dataclass(frozen=True)
class M2MissionSystemProjection:
    fixture_id: str
    fixture_version: str
    input_sha256: str
    source_sha256: str
    identity: MissionSystemIdentity
    instance: MissionSystemInstance
    subject_type: str
    metric_family: str
    applicability_mode: str
    allowed_system_types: tuple[str, ...]
    sns_applicable: bool
    logical_hash: str
    metric_logic_executed: bool = False
    stage_projection_executed: bool = False
    persistence_executed: bool = False
    publication_executed: bool = False


def _load_json(path: Path, *, code: str) -> dict[str, object]:
    try:
        raw: object = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise M2MissionSystemError(code, path.as_posix()) from exc
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise M2MissionSystemError(code, f"{path.as_posix()}: {exc}") from exc
    if not isinstance(raw, dict) or not all(isinstance(key, str) for key in raw):
        raise M2MissionSystemError(code, f"{path.as_posix()}: root must be object")
    return cast(dict[str, object], raw)


def _object(value: object, *, field: str) -> dict[str, object]:
    if not isinstance(value, dict) or not all(isinstance(key, str) for key in value):
        raise M2MissionSystemError(
            "M2_MISSION_SYSTEM_SOURCE_INVALID",
            f"{field} must be string-keyed object",
        )
    return cast(dict[str, object], value)


def _required_str(mapping: dict[str, object], key: str) -> str:
    value = mapping.get(key)
    if not isinstance(value, str) or not value:
        raise M2MissionSystemError(
            "M2_MISSION_SYSTEM_SOURCE_INVALID",
            f"{key} must be non-empty string",
        )
    return value


def _optional_str(mapping: dict[str, object], key: str) -> str | None:
    value = mapping.get(key)
    if value is None:
        return None
    if not isinstance(value, str) or not value:
        raise M2MissionSystemError(
            "M2_MISSION_SYSTEM_SOURCE_INVALID",
            f"{key} must be non-empty string or null",
        )
    return value


def _sha256_file(path: Path) -> str:
    try:
        return hashlib.sha256(path.read_bytes()).hexdigest()
    except FileNotFoundError as exc:
        raise M2MissionSystemError(
            "M2_MISSION_SYSTEM_SOURCE_MISSING",
            path.as_posix(),
        ) from exc


def _canonical_hash(value: object) -> str:
    payload = json.dumps(
        value,
        ensure_ascii=True,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("ascii")
    return hashlib.sha256(payload).hexdigest()


def _uuid(value: str, *, field: str) -> str:
    try:
        parsed = UUID(value)
    except ValueError as exc:
        raise M2MissionSystemError(
            "M2_MISSION_SYSTEM_SOURCE_INVALID",
            f"{field} must be UUID",
        ) from exc
    if str(parsed) != value.lower():
        raise M2MissionSystemError(
            "M2_MISSION_SYSTEM_SOURCE_INVALID",
            f"{field} must be canonical UUID",
        )
    return value


def _configuration_hash(value: str) -> str:
    if len(value) != 64 or any(char not in "0123456789abcdef" for char in value):
        raise M2MissionSystemError(
            "M2_MISSION_SYSTEM_SOURCE_INVALID",
            "configuration_hash must be lowercase SHA-256 hex",
        )
    return value


def _authority_expected() -> dict[str, object]:
    return {
        "allowed_system_types": list(EXPECTED_ALLOWED_SYSTEM_TYPES),
        "applicability_mode": EXPECTED_APPLICABILITY_MODE,
        "core_baseline": EXPECTED_CORE_BASELINE,
        "core_logical_model_sha256": EXPECTED_CORE_LOGICAL_MODEL_SHA256,
        "core_table": EXPECTED_CORE_TABLE,
        "metric_family": EXPECTED_METRIC_FAMILY,
        "p1_metric_catalog_sha256": EXPECTED_P1_METRIC_CATALOG_SHA256,
        "subject_type": EXPECTED_SUBJECT_TYPE,
    }


def load_m2_mission_system(bundle: Path) -> M2MissionSystemProjection:
    """Validate one governed M2 mission-system fixture and enforce SNS applicability."""

    manifest = _load_json(
        bundle / "manifest.json",
        code="M2_MISSION_SYSTEM_MANIFEST_INVALID",
    )
    if manifest.get("schema") != EXPECTED_MANIFEST_SCHEMA:
        raise M2MissionSystemError(
            "M2_MISSION_SYSTEM_MANIFEST_SCHEMA_MISMATCH",
            repr(manifest.get("schema")),
        )
    fixture_id = manifest.get("fixture_id")
    if fixture_id not in GOVERNED_FIXTURE_IDS or bundle.name != fixture_id:
        raise M2MissionSystemError(
            "M2_MISSION_SYSTEM_FIXTURE_NOT_GOVERNED",
            f"manifest={fixture_id!r} directory={bundle.name!r}",
        )
    if manifest.get("fixture_version") != EXPECTED_FIXTURE_VERSION:
        raise M2MissionSystemError(
            "M2_MISSION_SYSTEM_VERSION_UNSUPPORTED",
            repr(manifest.get("fixture_version")),
        )
    if manifest.get("data_classification") != EXPECTED_CLASSIFICATION:
        raise M2MissionSystemError(
            "M2_MISSION_SYSTEM_CLASSIFICATION_FORBIDDEN",
            repr(manifest.get("data_classification")),
        )
    if manifest.get("input_hash_algorithm") != EXPECTED_HASH_ALGORITHM:
        raise M2MissionSystemError(
            "M2_MISSION_SYSTEM_HASH_ALGORITHM_MISMATCH",
            repr(manifest.get("input_hash_algorithm")),
        )
    if manifest.get("input_hash_basis") != [EXPECTED_SOURCE_RELATIVE_PATH]:
        raise M2MissionSystemError(
            "M2_MISSION_SYSTEM_HASH_BASIS_MISMATCH",
            repr(manifest.get("input_hash_basis")),
        )
    authority = _object(manifest.get("authority_refs"), field="authority_refs")
    if authority != _authority_expected():
        raise M2MissionSystemError(
            "M2_MISSION_SYSTEM_AUTHORITY_MISMATCH",
            repr(authority),
        )

    files = _object(manifest.get("files"), field="files")
    source_ref = _object(files.get("source"), field="files.source")
    if source_ref.get("path") != EXPECTED_SOURCE_RELATIVE_PATH:
        raise M2MissionSystemError(
            "M2_MISSION_SYSTEM_SOURCE_PATH_MISMATCH",
            repr(source_ref.get("path")),
        )
    source_path = bundle / EXPECTED_SOURCE_RELATIVE_PATH
    source_sha256 = _sha256_file(source_path)
    if source_ref.get("sha256") != source_sha256:
        raise M2MissionSystemError(
            "M2_MISSION_SYSTEM_SOURCE_HASH_MISMATCH",
            f"expected={source_ref.get('sha256')} actual={source_sha256}",
        )
    if manifest.get("input_sha256") != source_sha256:
        raise M2MissionSystemError(
            "M2_MISSION_SYSTEM_INPUT_HASH_MISMATCH",
            f"expected={manifest.get('input_sha256')} actual={source_sha256}",
        )

    source = _load_json(source_path, code="M2_MISSION_SYSTEM_SOURCE_INVALID")
    if source.get("schema") != EXPECTED_SOURCE_SCHEMA:
        raise M2MissionSystemError(
            "M2_MISSION_SYSTEM_SOURCE_SCHEMA_MISMATCH",
            repr(source.get("schema")),
        )
    if source.get("fixture_id") != fixture_id:
        raise M2MissionSystemError(
            "M2_MISSION_SYSTEM_SOURCE_FIXTURE_MISMATCH",
            repr(source.get("fixture_id")),
        )
    if source.get("data_classification") != EXPECTED_CLASSIFICATION:
        raise M2MissionSystemError(
            "M2_MISSION_SYSTEM_CLASSIFICATION_FORBIDDEN",
            repr(source.get("data_classification")),
        )

    identity_raw = _object(source.get("identity_provenance"), field="identity_provenance")
    identity = MissionSystemIdentity(
        identity_ref=_required_str(identity_raw, "identity_ref"),
        source_entity_key=_required_str(identity_raw, "source_entity_key"),
    )
    instance_raw = _object(
        source.get("mission_system_instance"),
        field="mission_system_instance",
    )
    system_type = _required_str(instance_raw, "system_type")
    if system_type not in CORE_SYSTEM_TYPES:
        raise M2MissionSystemError(
            "M2_MISSION_SYSTEM_CORE_SYSTEM_TYPE_INVALID",
            system_type,
        )
    status = _required_str(instance_raw, "status")
    if status not in CORE_STATUSES:
        raise M2MissionSystemError(
            "M2_MISSION_SYSTEM_CORE_STATUS_INVALID",
            status,
        )
    instance = MissionSystemInstance(
        mission_system_instance_id=_uuid(
            _required_str(instance_raw, "mission_system_instance_id"),
            field="mission_system_instance_id",
        ),
        aircraft_id=_uuid(
            _required_str(instance_raw, "aircraft_id"),
            field="aircraft_id",
        ),
        system_type=system_type,
        system_code=_required_str(instance_raw, "system_code"),
        hardware_version=_optional_str(instance_raw, "hardware_version"),
        software_version=_optional_str(instance_raw, "software_version"),
        installation_id=_optional_str(instance_raw, "installation_id"),
        alignment_profile_version=_optional_str(
            instance_raw,
            "alignment_profile_version",
        ),
        status=status,
        configuration_hash=_configuration_hash(
            _required_str(instance_raw, "configuration_hash")
        ),
    )

    if system_type not in EXPECTED_ALLOWED_SYSTEM_TYPES:
        raise M2MissionSystemError(
            "M2_MISSION_SYSTEM_NOT_APPLICABLE",
            (
                f"family={EXPECTED_METRIC_FAMILY} system_type={system_type} "
                f"allowed={EXPECTED_ALLOWED_SYSTEM_TYPES}"
            ),
        )

    logical_hash = _canonical_hash(
        {
            "fixture_id": fixture_id,
            "identity": {
                "identity_ref": identity.identity_ref,
                "source_entity_key": identity.source_entity_key,
            },
            "instance": {
                "mission_system_instance_id": instance.mission_system_instance_id,
                "aircraft_id": instance.aircraft_id,
                "system_type": instance.system_type,
                "system_code": instance.system_code,
                "hardware_version": instance.hardware_version,
                "software_version": instance.software_version,
                "installation_id": instance.installation_id,
                "alignment_profile_version": instance.alignment_profile_version,
                "status": instance.status,
                "configuration_hash": instance.configuration_hash,
            },
            "subject_type": EXPECTED_SUBJECT_TYPE,
            "metric_family": EXPECTED_METRIC_FAMILY,
            "applicability_mode": EXPECTED_APPLICABILITY_MODE,
            "allowed_system_types": EXPECTED_ALLOWED_SYSTEM_TYPES,
        }
    )
    return M2MissionSystemProjection(
        fixture_id=fixture_id,
        fixture_version=EXPECTED_FIXTURE_VERSION,
        input_sha256=source_sha256,
        source_sha256=source_sha256,
        identity=identity,
        instance=instance,
        subject_type=EXPECTED_SUBJECT_TYPE,
        metric_family=EXPECTED_METRIC_FAMILY,
        applicability_mode=EXPECTED_APPLICABILITY_MODE,
        allowed_system_types=EXPECTED_ALLOWED_SYSTEM_TYPES,
        sns_applicable=True,
        logical_hash=logical_hash,
    )
