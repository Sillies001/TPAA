"""M1-DATA-006 immutable Evaluation Context resolution.

The resolver consumes the governed synthetic context document and projects the
minimum immutable M1 context required by the Basic Flight path. It binds the
existing RULE_SET and METRIC_PROFILE artifact roles and selects the authoritative
BASIC_FLIGHT_V1 Stage profile without inventing a STAGE_PROFILE persistence
binding role.

Historical replay never resolves "current" or "latest" references. The explicit
context content, and frozen_refs when supplied by the replay fixture, determine
the immutable selection.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path
from uuid import UUID, uuid5

from tpaa_generated.stage_registry import StageProfileId
from tpaa_ingest import GOVERNED_FIXTURE_IDS, load_synthetic_fixture_bundle
from tpaa_ingest.source_adapter import EXPECTED_STAGE_REGISTRY_SHA256
from tpaa_registry import register_synthetic_fixture

EXPECTED_CONTEXT_SCHEMA = "TPAA_M1_SYNTHETIC_CONTEXT_V1"
EXPECTED_CLASSIFICATION = "SYNTHETIC"
EXPECTED_BASIC_PROFILE_ID = "M1-BASIC-CONTEXT-1.0.0"
EXPECTED_RULE_SET_VERSION = "CB-1.4.0"
EXPECTED_METRIC_PROFILE_ID = "M1_BASIC_AIR_PROFILE_V1"
EXPECTED_STAGE_PROFILE_ID = StageProfileId.BASIC_FLIGHT_V1.value
EXPECTED_STAGE_PROFILE_AUTHORITY = "STAGE_REGISTRY:1.1.0"
EXPECTED_BINDING_ROLES = ("METRIC_PROFILE", "RULE_SET")
CONTEXT_NAMESPACE = UUID("b73b8a68-10f5-4ad4-8c91-40ac76f8d35c")


class EvaluationContextError(RuntimeError):
    """Deterministic fail-closed Evaluation Context resolution error."""

    def __init__(self, code: str, detail: str) -> None:
        super().__init__(f"{code}: {detail}")
        self.code = code
        self.detail = detail


@dataclass(frozen=True)
class ContextArtifactRef:
    """Exact ContextArtifactRefDTO-compatible immutable artifact reference."""

    binding_role: str
    context_artifact_id: str
    artifact_kind: str
    logical_key: str
    artifact_version: str
    object_ref_id: str
    artifact_sha256: str
    schema_version: str


@dataclass(frozen=True)
class ResolvedEvaluationContext:
    """Resolved M1 Basic Flight context without persistence side effects."""

    fixture_id: str
    fixture_version: str
    context_id: str
    session_id: str
    context_version: str
    revision_no: int
    supersedes_context_id: str | None
    rule_set_version: str
    metric_profile_version: str
    status: str
    basic_profile_id: str
    stage_profile_id: str
    stage_profile_authority: str
    stage_registry_sha256: str
    context_file_sha256: str
    artifact_refs: tuple[ContextArtifactRef, ...]
    logical_hash: str
    frozen_refs_used: bool
    current_refs_differ_from_frozen: bool
    current_latest_fallback_used: bool = False
    stage_profile_persistence_binding_created: bool = False
    database_persistence_executed: bool = False
    stage_projection_executed: bool = False
    world_projection_executed: bool = False
    metric_logic_executed: bool = False


def _load_json(path: Path, *, code: str) -> dict[str, object]:
    try:
        raw: object = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise EvaluationContextError(code, path.as_posix()) from exc
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise EvaluationContextError(code, f"{path.as_posix()}: {exc}") from exc
    if not isinstance(raw, dict) or not all(isinstance(key, str) for key in raw):
        raise EvaluationContextError(code, f"{path.as_posix()}: root must be object")
    return dict(raw)


def _required_str(mapping: dict[str, object], key: str, *, code: str) -> str:
    value = mapping.get(key)
    if not isinstance(value, str) or not value:
        raise EvaluationContextError(code, f"{key} must be non-empty string")
    return value


def _object(mapping: dict[str, object], key: str, *, code: str) -> dict[str, object]:
    value = mapping.get(key)
    if not isinstance(value, dict) or not all(isinstance(name, str) for name in value):
        raise EvaluationContextError(code, f"{key} must be string-keyed object")
    return dict(value)


def _canonical_uuid(value: str, *, field: str) -> str:
    try:
        parsed = UUID(value)
    except ValueError as exc:
        raise EvaluationContextError(
            "M1_EVALUATION_CONTEXT_UUID_INVALID",
            f"{field}={value!r}",
        ) from exc
    canonical = str(parsed)
    if parsed.int == 0 or canonical != value:
        raise EvaluationContextError(
            "M1_EVALUATION_CONTEXT_UUID_INVALID",
            f"{field}={value!r}",
        )
    return canonical


def _sha256_bytes(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def _canonical_json_bytes(payload: object) -> bytes:
    return json.dumps(
        payload,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
        allow_nan=False,
    ).encode("ascii")


def _stable_uuid(label: str) -> str:
    return str(uuid5(CONTEXT_NAMESPACE, label))


def _artifact_ref(
    *,
    binding_role: str,
    logical_key: str,
    artifact_version: str,
    artifact_sha256: str,
    schema_version: str,
) -> ContextArtifactRef:
    identity = (
        f"{binding_role}|{logical_key}|{artifact_version}|"
        f"{artifact_sha256}|{schema_version}"
    )
    return ContextArtifactRef(
        binding_role=binding_role,
        context_artifact_id=_stable_uuid(f"context-artifact|{identity}"),
        artifact_kind=binding_role,
        logical_key=logical_key,
        artifact_version=artifact_version,
        object_ref_id=_stable_uuid(f"object-ref|{identity}"),
        artifact_sha256=artifact_sha256,
        schema_version=schema_version,
    )


def _selected_refs(
    context: dict[str, object],
    *,
    rule_set_version: str,
    metric_profile_id: str,
    stage_profile_id: str,
) -> tuple[dict[str, str], bool, bool]:
    explicit = {
        "rule_set_version": rule_set_version,
        "metric_profile_id": metric_profile_id,
        "stage_profile_id": stage_profile_id,
    }
    frozen_raw = context.get("frozen_refs")
    frozen_used = frozen_raw is not None
    selected = explicit
    if frozen_raw is not None:
        if not isinstance(frozen_raw, dict) or not all(
            isinstance(key, str) and isinstance(value, str)
            for key, value in frozen_raw.items()
        ):
            raise EvaluationContextError(
                "M1_EVALUATION_CONTEXT_FROZEN_REFS_INVALID",
                repr(frozen_raw),
            )
        frozen = {str(key): str(value) for key, value in frozen_raw.items()}
        if frozen != explicit:
            raise EvaluationContextError(
                "M1_EVALUATION_CONTEXT_FROZEN_REFS_MISMATCH",
                f"expected={explicit!r} actual={frozen!r}",
            )
        selected = frozen

    current_raw = context.get("current_refs")
    current_differs = False
    if current_raw is not None:
        if not isinstance(current_raw, dict) or not all(
            isinstance(key, str) and isinstance(value, str)
            for key, value in current_raw.items()
        ):
            raise EvaluationContextError(
                "M1_EVALUATION_CONTEXT_CURRENT_REFS_INVALID",
                repr(current_raw),
            )
        current = {str(key): str(value) for key, value in current_raw.items()}
        current_differs = current != selected

    return selected, frozen_used, current_differs


def resolve_evaluation_context(
    bundle_path: Path,
    *,
    authority_root: Path,
) -> ResolvedEvaluationContext:
    """Resolve one governed fixture context and exact immutable artifact refs."""

    bundle = load_synthetic_fixture_bundle(bundle_path)
    registration = register_synthetic_fixture(bundle_path)
    context_path = bundle_path / "context" / "evaluation-context.json"
    try:
        context_bytes = context_path.read_bytes()
    except OSError as exc:
        raise EvaluationContextError(
            "M1_EVALUATION_CONTEXT_DOCUMENT_INVALID",
            f"{context_path.as_posix()}: {exc}",
        ) from exc
    context_sha256 = _sha256_bytes(context_bytes)
    if context_sha256 != registration.context_artifact.sha256:
        raise EvaluationContextError(
            "M1_EVALUATION_CONTEXT_FILE_HASH_MISMATCH",
            (
                f"expected={registration.context_artifact.sha256} "
                f"actual={context_sha256}"
            ),
        )

    context = _load_json(
        context_path,
        code="M1_EVALUATION_CONTEXT_DOCUMENT_INVALID",
    )
    if context.get("schema") != EXPECTED_CONTEXT_SCHEMA:
        raise EvaluationContextError(
            "M1_EVALUATION_CONTEXT_SCHEMA_MISMATCH",
            repr(context.get("schema")),
        )
    if context.get("fixture_id") != bundle.identity.fixture_id:
        raise EvaluationContextError(
            "M1_EVALUATION_CONTEXT_FIXTURE_MISMATCH",
            repr(context.get("fixture_id")),
        )
    if context.get("classification") != EXPECTED_CLASSIFICATION:
        raise EvaluationContextError(
            "M1_EVALUATION_CONTEXT_CLASSIFICATION_FORBIDDEN",
            repr(context.get("classification")),
        )

    context_id = _canonical_uuid(
        _required_str(
            context,
            "context_id",
            code="M1_EVALUATION_CONTEXT_DOCUMENT_INVALID",
        ),
        field="context_id",
    )
    context_version = _required_str(
        context,
        "context_version",
        code="M1_EVALUATION_CONTEXT_DOCUMENT_INVALID",
    )
    if context_version != EXPECTED_BASIC_PROFILE_ID:
        raise EvaluationContextError(
            "M1_EVALUATION_CONTEXT_BASIC_PROFILE_MISMATCH",
            context_version,
        )
    if context_version != registration.context_version:
        raise EvaluationContextError(
            "M1_EVALUATION_CONTEXT_REGISTRY_VERSION_MISMATCH",
            (
                f"registration={registration.context_version!r} "
                f"context={context_version!r}"
            ),
        )

    rule_set_version = _required_str(
        context,
        "rule_set_version",
        code="M1_EVALUATION_CONTEXT_DOCUMENT_INVALID",
    )
    if rule_set_version != EXPECTED_RULE_SET_VERSION:
        raise EvaluationContextError(
            "M1_EVALUATION_CONTEXT_RULE_SET_MISMATCH",
            rule_set_version,
        )

    metric_profile = _object(
        context,
        "metric_profile",
        code="M1_EVALUATION_CONTEXT_METRIC_PROFILE_INVALID",
    )
    metric_profile_id = _required_str(
        metric_profile,
        "profile_id",
        code="M1_EVALUATION_CONTEXT_METRIC_PROFILE_INVALID",
    )
    if metric_profile_id != EXPECTED_METRIC_PROFILE_ID:
        raise EvaluationContextError(
            "M1_EVALUATION_CONTEXT_METRIC_PROFILE_MISMATCH",
            metric_profile_id,
        )
    _object(
        metric_profile,
        "parameters",
        code="M1_EVALUATION_CONTEXT_METRIC_PROFILE_INVALID",
    )

    stage_profile = _object(
        context,
        "stage_profile",
        code="M1_EVALUATION_CONTEXT_STAGE_PROFILE_INVALID",
    )
    stage_profile_id = _required_str(
        stage_profile,
        "profile_id",
        code="M1_EVALUATION_CONTEXT_STAGE_PROFILE_INVALID",
    )
    stage_authority = _required_str(
        stage_profile,
        "authority",
        code="M1_EVALUATION_CONTEXT_STAGE_PROFILE_INVALID",
    )
    if stage_profile_id != EXPECTED_STAGE_PROFILE_ID:
        raise EvaluationContextError(
            "M1_EVALUATION_CONTEXT_STAGE_PROFILE_MISMATCH",
            stage_profile_id,
        )
    if stage_authority != EXPECTED_STAGE_PROFILE_AUTHORITY:
        raise EvaluationContextError(
            "M1_EVALUATION_CONTEXT_STAGE_AUTHORITY_MISMATCH",
            stage_authority,
        )
    try:
        StageProfileId(stage_profile_id)
    except ValueError as exc:
        raise EvaluationContextError(
            "M1_EVALUATION_CONTEXT_STAGE_PROFILE_UNGENERATED",
            stage_profile_id,
        ) from exc

    selected_refs, frozen_refs_used, current_refs_differ = _selected_refs(
        context,
        rule_set_version=rule_set_version,
        metric_profile_id=metric_profile_id,
        stage_profile_id=stage_profile_id,
    )
    if selected_refs != {
        "rule_set_version": EXPECTED_RULE_SET_VERSION,
        "metric_profile_id": EXPECTED_METRIC_PROFILE_ID,
        "stage_profile_id": EXPECTED_STAGE_PROFILE_ID,
    }:
        raise EvaluationContextError(
            "M1_EVALUATION_CONTEXT_SELECTED_REFS_INVALID",
            repr(selected_refs),
        )

    core_rules_path = authority_root / "CORE_RULES.json"
    try:
        core_rules_bytes = core_rules_path.read_bytes()
    except OSError as exc:
        raise EvaluationContextError(
            "M1_EVALUATION_CONTEXT_RULE_SET_ARTIFACT_INVALID",
            f"{core_rules_path.as_posix()}: {exc}",
        ) from exc
    core_rules = _load_json(
        core_rules_path,
        code="M1_EVALUATION_CONTEXT_RULE_SET_ARTIFACT_INVALID",
    )
    if (
        core_rules.get("authority_id") != "CORE_RULES"
        or core_rules.get("core_baseline") != rule_set_version
    ):
        raise EvaluationContextError(
            "M1_EVALUATION_CONTEXT_RULE_SET_ARTIFACT_MISMATCH",
            repr(
                {
                    "authority_id": core_rules.get("authority_id"),
                    "core_baseline": core_rules.get("core_baseline"),
                }
            ),
        )
    core_rules_schema_version = _required_str(
        core_rules,
        "version",
        code="M1_EVALUATION_CONTEXT_RULE_SET_ARTIFACT_INVALID",
    )

    stage_registry_path = authority_root / "STAGE_REGISTRY.json"
    try:
        stage_registry_bytes = stage_registry_path.read_bytes()
    except OSError as exc:
        raise EvaluationContextError(
            "M1_EVALUATION_CONTEXT_STAGE_REGISTRY_INVALID",
            f"{stage_registry_path.as_posix()}: {exc}",
        ) from exc
    stage_registry_sha256 = _sha256_bytes(stage_registry_bytes)
    if stage_registry_sha256 != EXPECTED_STAGE_REGISTRY_SHA256:
        raise EvaluationContextError(
            "M1_EVALUATION_CONTEXT_STAGE_REGISTRY_HASH_MISMATCH",
            (
                f"expected={EXPECTED_STAGE_REGISTRY_SHA256} "
                f"actual={stage_registry_sha256}"
            ),
        )
    stage_registry = _load_json(
        stage_registry_path,
        code="M1_EVALUATION_CONTEXT_STAGE_REGISTRY_INVALID",
    )
    if (
        stage_registry.get("registry_id") != "STAGE_REGISTRY"
        or stage_registry.get("version") != "1.1.0"
        or stage_registry.get("core_baseline") != rule_set_version
    ):
        raise EvaluationContextError(
            "M1_EVALUATION_CONTEXT_STAGE_REGISTRY_MISMATCH",
            repr(
                {
                    "registry_id": stage_registry.get("registry_id"),
                    "version": stage_registry.get("version"),
                    "core_baseline": stage_registry.get("core_baseline"),
                }
            ),
        )

    metric_profile_sha256 = _sha256_bytes(_canonical_json_bytes(metric_profile))
    artifact_refs = tuple(
        sorted(
            (
                _artifact_ref(
                    binding_role="RULE_SET",
                    logical_key="CORE_RULES",
                    artifact_version=rule_set_version,
                    artifact_sha256=_sha256_bytes(core_rules_bytes),
                    schema_version=core_rules_schema_version,
                ),
                _artifact_ref(
                    binding_role="METRIC_PROFILE",
                    logical_key=metric_profile_id,
                    artifact_version=metric_profile_id,
                    artifact_sha256=metric_profile_sha256,
                    schema_version=EXPECTED_CONTEXT_SCHEMA,
                ),
            ),
            key=lambda ref: ref.binding_role,
        )
    )
    if tuple(ref.binding_role for ref in artifact_refs) != EXPECTED_BINDING_ROLES:
        raise EvaluationContextError(
            "M1_EVALUATION_CONTEXT_BINDING_ROLE_MISMATCH",
            repr(tuple(ref.binding_role for ref in artifact_refs)),
        )

    logical_payload = {
        "fixture_id": bundle.identity.fixture_id,
        "fixture_version": bundle.identity.fixture_version,
        "context_id": context_id,
        "session_id": bundle.session.session_id,
        "context_version": context_version,
        "rule_set_version": rule_set_version,
        "metric_profile_version": metric_profile_id,
        "stage_profile_id": stage_profile_id,
        "stage_profile_authority": stage_authority,
        "stage_registry_sha256": stage_registry_sha256,
        "context_file_sha256": context_sha256,
        "artifact_refs": [
            {
                "binding_role": ref.binding_role,
                "context_artifact_id": ref.context_artifact_id,
                "artifact_kind": ref.artifact_kind,
                "logical_key": ref.logical_key,
                "artifact_version": ref.artifact_version,
                "object_ref_id": ref.object_ref_id,
                "artifact_sha256": ref.artifact_sha256,
                "schema_version": ref.schema_version,
            }
            for ref in artifact_refs
        ],
    }
    logical_hash = _sha256_bytes(_canonical_json_bytes(logical_payload))

    return ResolvedEvaluationContext(
        fixture_id=bundle.identity.fixture_id,
        fixture_version=bundle.identity.fixture_version,
        context_id=context_id,
        session_id=bundle.session.session_id,
        context_version=context_version,
        revision_no=1,
        supersedes_context_id=None,
        rule_set_version=rule_set_version,
        metric_profile_version=metric_profile_id,
        status="ACTIVE",
        basic_profile_id=context_version,
        stage_profile_id=stage_profile_id,
        stage_profile_authority=stage_authority,
        stage_registry_sha256=stage_registry_sha256,
        context_file_sha256=context_sha256,
        artifact_refs=artifact_refs,
        logical_hash=logical_hash,
        frozen_refs_used=frozen_refs_used,
        current_refs_differ_from_frozen=current_refs_differ,
    )


def resolve_all_evaluation_contexts(
    fixture_root: Path,
    *,
    authority_root: Path,
) -> tuple[ResolvedEvaluationContext, ...]:
    """Resolve all governed M1 fixture contexts in stable fixture-id order."""

    return tuple(
        resolve_evaluation_context(
            fixture_root / fixture_id,
            authority_root=authority_root,
        )
        for fixture_id in sorted(GOVERNED_FIXTURE_IDS)
    )
