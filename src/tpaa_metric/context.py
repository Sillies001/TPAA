"""M1-MET-001 exact MetricContext construction."""

from __future__ import annotations

import hashlib
import json
import math
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import cast
from uuid import UUID, uuid5

from tpaa_context import resolve_evaluation_context
from tpaa_generated.metric_registry import P1_METRICS
from tpaa_world import AircraftObservedWorld, WorldEvidenceRef

REPRESENTATIVE_METRIC_CODES = (
    "P1-AIR-001",
    "P1-AIR-002",
    "P1-AIR-003",
    "P1-AIR-004",
    "P1-AIR-007",
)
REQUIRED_REF_CLASSES = frozenset(
    {"EVALUATION_CONTEXT", "CANONICAL", "EPISODE", "STAGE", "WORLD", "EVIDENCE"}
)
METRIC_CONTEXT_NAMESPACE = UUID("0c47c4c5-0a17-448a-b44a-0f1a7916cb45")
EVIDENCE_NAMESPACE = UUID("fc3b6cf4-b5fd-44b4-921a-36b425c34680")


class MetricContextError(RuntimeError):
    """Deterministic fail-closed MetricContext error."""

    def __init__(self, code: str, detail: str) -> None:
        super().__init__(f"{code}: {detail}")
        self.code = code
        self.detail = detail


@dataclass(frozen=True)
class MetricAuthority:
    metric_code: str
    semantic_id: str
    semantic_version: int
    subject_type: str
    unit: str
    value_kind: str
    algorithm_id: str
    algorithm_version: str
    observation_lane: str
    publication_route: str
    structured_output_schema_id: str | None


@dataclass(frozen=True)
class MetricContext:
    metric_context_id: str
    fixture_id: str
    session_id: str
    context_id: str
    subject_type: str
    subject_id: str
    catalog_id: str
    catalog_version: str
    catalog_sha256: str
    profile_id: str
    profile_sha256: str
    min_coverage: float
    max_gap_us: int
    derivative_window_s: float
    sustain_duration_s: float
    authorities: tuple[MetricAuthority, ...]
    input_refs: tuple[WorldEvidenceRef, ...]
    latest_fallback_used: bool = False
    ui_or_database_inference_used: bool = False

    def authority(self, metric_code: str) -> MetricAuthority:
        for authority in self.authorities:
            if authority.metric_code == metric_code:
                return authority
        raise MetricContextError("M1_METRIC_AUTHORITY_MISSING", metric_code)


def _canonical_bytes(payload: object) -> bytes:
    return json.dumps(
        payload,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
        allow_nan=False,
    ).encode("ascii")


def _sha256(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def _load_object(path: Path) -> dict[str, object]:
    try:
        raw: object = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise MetricContextError("M1_METRIC_CONTEXT_ARTIFACT_INVALID", str(path)) from exc
    if not isinstance(raw, dict) or not all(isinstance(key, str) for key in raw):
        raise MetricContextError("M1_METRIC_CONTEXT_ARTIFACT_INVALID", str(path))
    return cast(dict[str, object], raw)


def _required_number(parameters: dict[str, object], name: str) -> float:
    value = parameters.get(name)
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise MetricContextError("M1_METRIC_PROFILE_PARAMETER_INVALID", name)
    normalized = float(value)
    if not math.isfinite(normalized) or normalized <= 0.0:
        raise MetricContextError("M1_METRIC_PROFILE_PARAMETER_INVALID", name)
    return normalized


def _required_positive_int_text(parameters: dict[str, object], name: str) -> int:
    value = parameters.get(name)
    if not isinstance(value, str) or not value.isdecimal():
        raise MetricContextError("M1_METRIC_PROFILE_PARAMETER_INVALID", name)
    normalized = int(value)
    if normalized <= 0:
        raise MetricContextError("M1_METRIC_PROFILE_PARAMETER_INVALID", name)
    return normalized


def _authority_from_generated(raw: Mapping[str, object]) -> MetricAuthority:
    mapping = raw

    def text(name: str) -> str:
        value = mapping.get(name)
        if not isinstance(value, str) or not value:
            raise MetricContextError("M1_METRIC_GENERATED_AUTHORITY_INVALID", name)
        return value

    semantic_version = mapping.get("semantic_version")
    if isinstance(semantic_version, bool) or not isinstance(semantic_version, int):
        raise MetricContextError("M1_METRIC_GENERATED_AUTHORITY_INVALID", "semantic_version")
    schema_id = mapping.get("structured_output_schema_id")
    if schema_id is not None and not isinstance(schema_id, str):
        raise MetricContextError(
            "M1_METRIC_GENERATED_AUTHORITY_INVALID",
            "structured_output_schema_id",
        )
    return MetricAuthority(
        metric_code=text("metric_code"),
        semantic_id=text("semantic_id"),
        semantic_version=semantic_version,
        subject_type=text("subject_type"),
        unit=text("unit"),
        value_kind=text("value_kind"),
        algorithm_id=text("algorithm_id"),
        algorithm_version=text("algorithm_version"),
        observation_lane=text("observation_lane"),
        publication_route=text("publication_route"),
        structured_output_schema_id=schema_id,
    )


def _metric_authorities() -> tuple[MetricAuthority, ...]:
    selected = tuple(
        _authority_from_generated(raw)
        for raw in P1_METRICS
        if raw.get("metric_code") in REPRESENTATIVE_METRIC_CODES
    )
    if tuple(item.metric_code for item in selected) != REPRESENTATIVE_METRIC_CODES:
        raise MetricContextError(
            "M1_METRIC_REPRESENTATIVE_SET_DRIFT",
            repr(tuple(item.metric_code for item in selected)),
        )
    for item in selected:
        if item.subject_type != "AIRCRAFT" or item.publication_route != "CAPABILITY_OBSERVATION":
            raise MetricContextError("M1_METRIC_APPLICABILITY_DRIFT", item.metric_code)
        expected_kind = "STRUCTURED" if item.metric_code == "P1-AIR-007" else "NUMERIC"
        if item.value_kind != expected_kind:
            raise MetricContextError("M1_METRIC_VALUE_KIND_DRIFT", item.metric_code)
    return selected


def build_metric_context(
    bundle_path: Path,
    *,
    authority_root: Path,
    world: AircraftObservedWorld,
) -> MetricContext:
    """Bind frozen catalog/profile authority and exact immutable input refs."""

    resolved = resolve_evaluation_context(bundle_path, authority_root=authority_root)
    if world.fixture_id != resolved.fixture_id or world.session_id != resolved.session_id:
        raise MetricContextError("M1_METRIC_WORLD_CONTEXT_DRIFT", world.world_product_id)

    context_path = bundle_path / "context" / "evaluation-context.json"
    context_bytes = context_path.read_bytes()
    if _sha256(context_bytes) != resolved.context_file_sha256:
        raise MetricContextError("M1_METRIC_PROFILE_CONTEXT_HASH_DRIFT", resolved.context_id)
    context_doc = _load_object(context_path)
    metric_profile_raw = context_doc.get("metric_profile")
    if not isinstance(metric_profile_raw, dict):
        raise MetricContextError("M1_METRIC_PROFILE_INVALID", "metric_profile")
    metric_profile = cast(dict[str, object], metric_profile_raw)
    profile_id = metric_profile.get("profile_id")
    parameters_raw = metric_profile.get("parameters")
    if profile_id != resolved.metric_profile_version or not isinstance(parameters_raw, dict):
        raise MetricContextError("M1_METRIC_PROFILE_INVALID", repr(profile_id))
    parameters = cast(dict[str, object], parameters_raw)

    catalog_path = authority_root / "P1_METRIC_CATALOG.json"
    catalog_bytes = catalog_path.read_bytes()
    catalog = _load_object(catalog_path)
    catalog_version = catalog.get("catalog_version")
    if not isinstance(catalog_version, str) or not catalog_version:
        raise MetricContextError("M1_METRIC_CATALOG_INVALID", "catalog_version")

    refs = [*world.evidence_refs, world.world_evidence_ref]
    aggregate_hash = _sha256(
        _canonical_bytes(
            [{"class": ref.ref_class, "id": ref.ref_id, "hash": ref.logical_hash} for ref in refs]
        )
    )
    evidence_id = str(uuid5(EVIDENCE_NAMESPACE, aggregate_hash))
    refs.append(WorldEvidenceRef("EVIDENCE", evidence_id, aggregate_hash))
    present = {ref.ref_class for ref in refs}
    if not REQUIRED_REF_CLASSES.issubset(present):
        raise MetricContextError(
            "M1_METRIC_INPUT_REF_CLASS_MISSING",
            repr(sorted(REQUIRED_REF_CLASSES - present)),
        )

    profile_sha256 = _sha256(_canonical_bytes(metric_profile))
    identity = {
        "fixture_id": resolved.fixture_id,
        "session_id": resolved.session_id,
        "context_id": resolved.context_id,
        "subject_type": "AIRCRAFT",
        "subject_id": world.aircraft_id,
        "catalog_version": catalog_version,
        "catalog_sha256": _sha256(catalog_bytes),
        "profile_id": profile_id,
        "profile_sha256": profile_sha256,
        "world_product_id": world.world_product_id,
        "input_refs": [
            {"class": ref.ref_class, "id": ref.ref_id, "hash": ref.logical_hash} for ref in refs
        ],
    }
    metric_context_id = str(
        uuid5(METRIC_CONTEXT_NAMESPACE, _canonical_bytes(identity).decode("ascii"))
    )
    return MetricContext(
        metric_context_id=metric_context_id,
        fixture_id=resolved.fixture_id,
        session_id=resolved.session_id,
        context_id=resolved.context_id,
        subject_type="AIRCRAFT",
        subject_id=world.aircraft_id,
        catalog_id="P1_METRIC_CATALOG",
        catalog_version=catalog_version,
        catalog_sha256=_sha256(catalog_bytes),
        profile_id=profile_id,
        profile_sha256=profile_sha256,
        min_coverage=_required_number(parameters, "min_coverage"),
        max_gap_us=_required_positive_int_text(parameters, "max_gap_us"),
        derivative_window_s=_required_number(parameters, "derivative_window_s"),
        sustain_duration_s=_required_number(parameters, "sustain_duration_s"),
        authorities=_metric_authorities(),
        input_refs=tuple(refs),
    )
