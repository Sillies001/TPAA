"""M1-DATA-001 synthetic fixture source adapter.

The adapter validates the governed M1 fixture envelope and exposes immutable
source records plus lineage. It deliberately stops before Session Time,
Canonical projection, Episode/Stage, World, or Metric semantics.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path
from types import MappingProxyType
from typing import TypeAlias

EXPECTED_MANIFEST_SCHEMA = "TPAA_M1_FIXTURE_BUNDLE_V1"
EXPECTED_MANIFEST_VERSION = "1.0.0"
EXPECTED_SOURCE_SCHEMA = "TPAA_M1_SYNTHETIC_SOURCE_V1"
EXPECTED_CLASSIFICATION = "SYNTHETIC"
EXPECTED_INPUT_HASH_ALGORITHM = "SHA256_PATH_SHA256_V1"
EXPECTED_CORE_BASELINE = "CB-1.4.0"
EXPECTED_CONTEXT_SCHEMA = "TPAA_M1_SYNTHETIC_CONTEXT_V1"
EXPECTED_STAGE_PROFILE = "BASIC_FLIGHT_V1"
EXPECTED_MAPPING_VERSION = "M1_BASIC_FLIGHT_SOURCE_MAP_V1"
EXPECTED_STAGE_REGISTRY_SHA256 = (
    "52377c097342fd52ad7b10e771a85420f3dca24f0446d171ff285306b8245691"
)
EXPECTED_P1_METRIC_CATALOG_SHA256 = (
    "24ab6d06ced0b768ff16e4c945e778cc8fd2d3838be3ca30051ec8f8e0d7277d"
)
EXPECTED_DTO_CONTRACTS_SHA256 = (
    "be9e83d18427c0a71d80df6ba2a56f7f611a059c749e1e163d9b5c0140b90e1c"
)
EXPECTED_METRIC_CODES = frozenset(
    {"P1-AIR-001", "P1-AIR-002", "P1-AIR-003", "P1-AIR-004", "P1-AIR-007"}
)

GOVERNED_FIXTURE_IDS = frozenset(
    {
        "BF_M1_NOMINAL_V1",
        "BF_M1_GAP_V1",
        "BF_M1_ANGLE_WRAP_V1",
        "BF_M1_STRUCTURED_PARTIAL_V1",
        "BF_M1_STAGE_BOUNDARY_V1",
        "BF_M1_REPLAY_V1",
        "BF_M1_CROSS_PLATFORM_V1",
        "BF_M1_FAILURE_V1",
    }
)

EXPECTED_PHYSICAL_TO_CANONICAL_MAPPING = MappingProxyType(
    {
        "source_time_us": "session_time_us via context.source_time_transform",
        "p": "body_p_rad_s",
        "nz": "nz_g",
        "heading": "heading_true_rad",
        "tas": "tas_mps",
        "mach": "mach",
        "quality": "quality_mask",
    }
)
REQUIRED_PHYSICAL_MAPPING = frozenset(EXPECTED_PHYSICAL_TO_CANONICAL_MAPPING)

SourceScalar: TypeAlias = str | int | float | bool | None


class SyntheticSourceAdapterError(RuntimeError):
    """Deterministic fail-closed source-adapter error."""

    def __init__(self, code: str, detail: str) -> None:
        super().__init__(f"{code}: {detail}")
        self.code = code
        self.detail = detail


@dataclass(frozen=True)
class SourceArtifactIdentity:
    """Immutable fixture/source identity carried into later lineage stages."""

    fixture_id: str
    fixture_version: str
    input_sha256: str
    source_sha256: str
    context_sha256: str

    @property
    def stable_source_ref(self) -> str:
        return (
            f"M1_FIXTURE:{self.fixture_id}:{self.fixture_version}:"
            f"{self.source_sha256}"
        )


@dataclass(frozen=True)
class SyntheticSessionSource:
    session_id: str
    session_code: str
    session_type: str
    source_time_basis: str
    end_source_time_us: str


@dataclass(frozen=True)
class SyntheticAircraftSource:
    source_aircraft_key: str
    aircraft_id: str


@dataclass(frozen=True)
class SyntheticSourceRow:
    """One source-clock record before Session-Time/Canonical projection."""

    source_time_us: str
    values: MappingProxyType[str, SourceScalar]


@dataclass(frozen=True)
class SyntheticSourceMarker:
    """Opaque source marker preserved for later governed Stage processing."""

    source_time_us: str
    marker_value: str


@dataclass(frozen=True)
class SyntheticSourceBundle:
    identity: SourceArtifactIdentity
    session: SyntheticSessionSource
    aircraft: SyntheticAircraftSource
    mapping_version: str
    physical_to_canonical_mapping: MappingProxyType[str, str]
    rows: tuple[SyntheticSourceRow, ...]
    source_markers: tuple[SyntheticSourceMarker, ...]
    data_classification: str


def _load_json(path: Path, *, missing: str, corrupt: str) -> dict[str, object]:
    try:
        raw: object = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise SyntheticSourceAdapterError(missing, path.as_posix()) from exc
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise SyntheticSourceAdapterError(
            corrupt,
            f"{path.as_posix()}: {exc}",
        ) from exc
    if not isinstance(raw, dict) or not all(isinstance(key, str) for key in raw):
        raise SyntheticSourceAdapterError(
            corrupt,
            f"{path.as_posix()}: JSON root must be string-keyed object",
        )
    return dict(raw)


def _object(value: object, *, field: str) -> dict[str, object]:
    if not isinstance(value, dict) or not all(isinstance(key, str) for key in value):
        raise SyntheticSourceAdapterError(
            "M1_SOURCE_ADAPTER_MANIFEST_INVALID",
            f"{field} must be string-keyed object",
        )
    return dict(value)


def _required_str(
    mapping: dict[str, object],
    key: str,
    *,
    code: str = "M1_SOURCE_ADAPTER_MANIFEST_INVALID",
) -> str:
    value = mapping.get(key)
    if not isinstance(value, str) or not value:
        raise SyntheticSourceAdapterError(code, f"{key} must be non-empty string")
    return value


def _safe_path(bundle: Path, relative: str) -> Path:
    candidate = Path(relative)
    if candidate.is_absolute() or ".." in candidate.parts:
        raise SyntheticSourceAdapterError(
            "M1_SOURCE_ADAPTER_PATH_INVALID",
            relative,
        )
    root = bundle.resolve()
    resolved = (bundle / candidate).resolve()
    if resolved != root and root not in resolved.parents:
        raise SyntheticSourceAdapterError(
            "M1_SOURCE_ADAPTER_PATH_INVALID",
            relative,
        )
    return resolved


def _sha256_file(path: Path) -> str:
    try:
        return hashlib.sha256(path.read_bytes()).hexdigest()
    except FileNotFoundError as exc:
        raise SyntheticSourceAdapterError(
            "M1_SOURCE_ADAPTER_ARTIFACT_MISSING",
            path.as_posix(),
        ) from exc


def _input_digest(source_sha256: str, context_sha256: str) -> str:
    payload = (
        f"source/flight.json={source_sha256}\n"
        f"context/evaluation-context.json={context_sha256}\n"
    ).encode("ascii")
    return hashlib.sha256(payload).hexdigest()


def _validate_digest(value: str, *, field: str) -> str:
    if len(value) != 64 or any(char not in "0123456789abcdef" for char in value):
        raise SyntheticSourceAdapterError(
            "M1_SOURCE_ADAPTER_MANIFEST_INVALID",
            f"{field} must be lower-case SHA-256 hex",
        )
    return value


def _parse_row(raw: object, *, index: int) -> SyntheticSourceRow:
    row = _object(raw, field=f"rows[{index}]")
    source_time = _required_str(
        row,
        "source_time_us",
        code="M1_SOURCE_ADAPTER_SOURCE_INVALID",
    )
    values: dict[str, SourceScalar] = {}
    for key in REQUIRED_PHYSICAL_MAPPING - {"source_time_us"}:
        if key not in row:
            raise SyntheticSourceAdapterError(
                "M1_SOURCE_ADAPTER_SOURCE_INVALID",
                f"rows[{index}].{key} is missing",
            )
        value = row[key]
        if value is not None and not isinstance(value, (str, int, float, bool)):
            raise SyntheticSourceAdapterError(
                "M1_SOURCE_ADAPTER_SOURCE_INVALID",
                f"rows[{index}].{key} has unsupported type",
            )
        values[key] = value
    return SyntheticSourceRow(
        source_time_us=source_time,
        values=MappingProxyType(dict(sorted(values.items()))),
    )


def _parse_marker(raw: object, *, index: int) -> SyntheticSourceMarker:
    marker = _object(raw, field=f"official_stage_markers[{index}]")
    return SyntheticSourceMarker(
        source_time_us=_required_str(
            marker,
            "source_time_us",
            code="M1_SOURCE_ADAPTER_SOURCE_INVALID",
        ),
        marker_value=_required_str(
            marker,
            "stage",
            code="M1_SOURCE_ADAPTER_SOURCE_INVALID",
        ),
    )


def load_synthetic_fixture_bundle(bundle: Path) -> SyntheticSourceBundle:
    """Load one governed M1 synthetic source bundle, failing closed on drift."""

    manifest = _load_json(
        bundle / "manifest.json",
        missing="M1_SOURCE_ADAPTER_MANIFEST_MISSING",
        corrupt="M1_SOURCE_ADAPTER_MANIFEST_CORRUPT",
    )
    if manifest.get("schema") != EXPECTED_MANIFEST_SCHEMA:
        raise SyntheticSourceAdapterError(
            "M1_SOURCE_ADAPTER_SCHEMA_MISMATCH",
            repr(manifest.get("schema")),
        )

    fixture_id = _required_str(manifest, "fixture_id")
    fixture_version = _required_str(manifest, "fixture_version")
    if fixture_id != bundle.name or fixture_id not in GOVERNED_FIXTURE_IDS:
        raise SyntheticSourceAdapterError(
            "M1_SOURCE_ADAPTER_FIXTURE_NOT_GOVERNED",
            f"manifest={fixture_id!r} directory={bundle.name!r}",
        )
    if fixture_version != EXPECTED_MANIFEST_VERSION:
        raise SyntheticSourceAdapterError(
            "M1_SOURCE_ADAPTER_VERSION_UNSUPPORTED",
            fixture_version,
        )
    if manifest.get("data_classification") != EXPECTED_CLASSIFICATION:
        raise SyntheticSourceAdapterError(
            "M1_SOURCE_ADAPTER_CLASSIFICATION_FORBIDDEN",
            repr(manifest.get("data_classification")),
        )
    if manifest.get("input_hash_algorithm") != EXPECTED_INPUT_HASH_ALGORITHM:
        raise SyntheticSourceAdapterError(
            "M1_SOURCE_ADAPTER_HASH_ALGORITHM_MISMATCH",
            repr(manifest.get("input_hash_algorithm")),
        )
    if manifest.get("input_hash_basis") != [
        "source/flight.json",
        "context/evaluation-context.json",
    ]:
        raise SyntheticSourceAdapterError(
            "M1_SOURCE_ADAPTER_HASH_BASIS_MISMATCH",
            repr(manifest.get("input_hash_basis")),
        )

    authority = _object(manifest.get("authority_refs"), field="authority_refs")
    expected_authority = {
        "core_baseline": EXPECTED_CORE_BASELINE,
        "stage_profile": EXPECTED_STAGE_PROFILE,
        "stage_registry_sha256": EXPECTED_STAGE_REGISTRY_SHA256,
        "p1_metric_catalog_sha256": EXPECTED_P1_METRIC_CATALOG_SHA256,
        "dto_contracts_sha256": EXPECTED_DTO_CONTRACTS_SHA256,
    }
    for key, expected in expected_authority.items():
        if authority.get(key) != expected:
            raise SyntheticSourceAdapterError(
                "M1_SOURCE_ADAPTER_AUTHORITY_MISMATCH",
                f"{key}={authority.get(key)!r}",
            )
    metric_codes = authority.get("metric_codes")
    if not isinstance(metric_codes, list) or {
        value for value in metric_codes if isinstance(value, str)
    } != EXPECTED_METRIC_CODES:
        raise SyntheticSourceAdapterError(
            "M1_SOURCE_ADAPTER_AUTHORITY_MISMATCH",
            f"metric_codes={metric_codes!r}",
        )

    files = _object(manifest.get("files"), field="files")
    source_ref = _object(files.get("source"), field="files.source")
    context_ref = _object(files.get("context"), field="files.context")
    source_path = _safe_path(
        bundle,
        _required_str(source_ref, "path"),
    )
    context_path = _safe_path(
        bundle,
        _required_str(context_ref, "path"),
    )
    source_expected = _validate_digest(
        _required_str(source_ref, "sha256"),
        field="files.source.sha256",
    )
    context_expected = _validate_digest(
        _required_str(context_ref, "sha256"),
        field="files.context.sha256",
    )
    input_expected = _validate_digest(
        _required_str(manifest, "input_sha256"),
        field="input_sha256",
    )

    source_actual = _sha256_file(source_path)
    context_actual = _sha256_file(context_path)
    if source_actual != source_expected:
        raise SyntheticSourceAdapterError(
            "M1_SOURCE_ADAPTER_SOURCE_HASH_MISMATCH",
            f"expected={source_expected} actual={source_actual}",
        )
    if context_actual != context_expected:
        raise SyntheticSourceAdapterError(
            "M1_SOURCE_ADAPTER_CONTEXT_HASH_MISMATCH",
            f"expected={context_expected} actual={context_actual}",
        )
    input_actual = _input_digest(source_actual, context_actual)
    if input_actual != input_expected:
        raise SyntheticSourceAdapterError(
            "M1_SOURCE_ADAPTER_INPUT_HASH_MISMATCH",
            f"expected={input_expected} actual={input_actual}",
        )

    context = _load_json(
        context_path,
        missing="M1_SOURCE_ADAPTER_CONTEXT_MISSING",
        corrupt="M1_SOURCE_ADAPTER_CONTEXT_CORRUPT",
    )
    if context.get("schema") != EXPECTED_CONTEXT_SCHEMA:
        raise SyntheticSourceAdapterError(
            "M1_SOURCE_ADAPTER_CONTEXT_SCHEMA_MISMATCH",
            repr(context.get("schema")),
        )
    if context.get("fixture_id") != fixture_id:
        raise SyntheticSourceAdapterError(
            "M1_SOURCE_ADAPTER_CONTEXT_ID_MISMATCH",
            repr(context.get("fixture_id")),
        )
    if context.get("classification") != EXPECTED_CLASSIFICATION:
        raise SyntheticSourceAdapterError(
            "M1_SOURCE_ADAPTER_CLASSIFICATION_FORBIDDEN",
            repr(context.get("classification")),
        )

    source = _load_json(
        source_path,
        missing="M1_SOURCE_ADAPTER_SOURCE_MISSING",
        corrupt="M1_SOURCE_ADAPTER_SOURCE_CORRUPT",
    )
    if source.get("schema") != EXPECTED_SOURCE_SCHEMA:
        raise SyntheticSourceAdapterError(
            "M1_SOURCE_ADAPTER_SOURCE_SCHEMA_MISMATCH",
            repr(source.get("schema")),
        )
    if source.get("fixture_id") != fixture_id:
        raise SyntheticSourceAdapterError(
            "M1_SOURCE_ADAPTER_SOURCE_ID_MISMATCH",
            repr(source.get("fixture_id")),
        )
    if source.get("data_classification") != EXPECTED_CLASSIFICATION:
        raise SyntheticSourceAdapterError(
            "M1_SOURCE_ADAPTER_CLASSIFICATION_FORBIDDEN",
            repr(source.get("data_classification")),
        )

    session_raw = _object(source.get("session"), field="session")
    aircraft_raw = _object(source.get("aircraft"), field="aircraft")
    mapping_raw = _object(source.get("mapping"), field="mapping")
    if mapping_raw != dict(EXPECTED_PHYSICAL_TO_CANONICAL_MAPPING):
        raise SyntheticSourceAdapterError(
            "M1_SOURCE_ADAPTER_MAPPING_MISMATCH",
            repr(mapping_raw),
        )
    mapping = dict(EXPECTED_PHYSICAL_TO_CANONICAL_MAPPING)

    rows_raw = source.get("rows")
    if not isinstance(rows_raw, list) or not rows_raw:
        raise SyntheticSourceAdapterError(
            "M1_SOURCE_ADAPTER_SOURCE_INVALID",
            "rows must be a non-empty array",
        )
    rows = tuple(_parse_row(item, index=index) for index, item in enumerate(rows_raw))

    markers_raw = source.get("official_stage_markers")
    if not isinstance(markers_raw, list):
        raise SyntheticSourceAdapterError(
            "M1_SOURCE_ADAPTER_SOURCE_INVALID",
            "official_stage_markers must be an array",
        )
    markers = tuple(
        _parse_marker(item, index=index)
        for index, item in enumerate(markers_raw)
    )

    return SyntheticSourceBundle(
        identity=SourceArtifactIdentity(
            fixture_id=fixture_id,
            fixture_version=fixture_version,
            input_sha256=input_actual,
            source_sha256=source_actual,
            context_sha256=context_actual,
        ),
        session=SyntheticSessionSource(
            session_id=_required_str(
                session_raw,
                "session_id",
                code="M1_SOURCE_ADAPTER_SOURCE_INVALID",
            ),
            session_code=_required_str(
                session_raw,
                "session_code",
                code="M1_SOURCE_ADAPTER_SOURCE_INVALID",
            ),
            session_type=_required_str(
                session_raw,
                "session_type",
                code="M1_SOURCE_ADAPTER_SOURCE_INVALID",
            ),
            source_time_basis=_required_str(
                session_raw,
                "source_time_basis",
                code="M1_SOURCE_ADAPTER_SOURCE_INVALID",
            ),
            end_source_time_us=_required_str(
                session_raw,
                "end_source_time_us",
                code="M1_SOURCE_ADAPTER_SOURCE_INVALID",
            ),
        ),
        aircraft=SyntheticAircraftSource(
            source_aircraft_key=_required_str(
                aircraft_raw,
                "source_aircraft_key",
                code="M1_SOURCE_ADAPTER_SOURCE_INVALID",
            ),
            aircraft_id=_required_str(
                aircraft_raw,
                "aircraft_id",
                code="M1_SOURCE_ADAPTER_SOURCE_INVALID",
            ),
        ),
        mapping_version=EXPECTED_MAPPING_VERSION,
        physical_to_canonical_mapping=MappingProxyType(mapping),
        rows=rows,
        source_markers=markers,
        data_classification=EXPECTED_CLASSIFICATION,
    )
