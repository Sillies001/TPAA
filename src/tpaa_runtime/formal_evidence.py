"""Verified loader for deployment-bound W7-W9 qualification evidence."""

from __future__ import annotations

import base64
import binascii
import hashlib
import json
from collections.abc import Mapping, Sequence
from dataclasses import dataclass

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey

from tpaa_application import W7ExternalCapabilityRegistry, build_w7_external_registry
from tpaa_qualification import (
    M5QualificationAuthority,
    W9FinalQualificationStatus,
    build_w9_final_qualification_status,
)

from .config import FormalQualificationEvidenceConfig
from .w8_operations import W8OperationsStatus, build_w8_operations_status

FORMAL_EVIDENCE_ENVELOPE_SCHEMA = "TPAA_FORMAL_RUNTIME_EVIDENCE_ENVELOPE_V1"
FORMAL_EVIDENCE_PAYLOAD_SCHEMA = "TPAA_FORMAL_RUNTIME_EVIDENCE_V1"


class FormalEvidenceError(RuntimeError):
    """Untrusted, malformed, or candidate-mismatched formal evidence."""


@dataclass(frozen=True, slots=True)
class FormalRuntimeEvidence:
    w7_external_capabilities: W7ExternalCapabilityRegistry
    w8_operations_status: W8OperationsStatus
    w9_final_qualification_status: W9FinalQualificationStatus
    envelope_sha256: str
    signature_sha256: str


def _mapping(value: object, field: str) -> Mapping[str, object]:
    if not isinstance(value, Mapping):
        raise FormalEvidenceError(f"FORMAL_EVIDENCE_OBJECT_REQUIRED:{field}")
    return value


def _sequence(value: object, field: str) -> Sequence[Mapping[str, object]]:
    if not isinstance(value, list) or not all(isinstance(item, Mapping) for item in value):
        raise FormalEvidenceError(f"FORMAL_EVIDENCE_LIST_REQUIRED:{field}")
    return value


def _text(value: object, field: str) -> str:
    if not isinstance(value, str) or not value.strip() or value != value.strip():
        raise FormalEvidenceError(f"FORMAL_EVIDENCE_TEXT_INVALID:{field}")
    return value


def _boolean(value: object, field: str) -> bool:
    if type(value) is not bool:
        raise FormalEvidenceError(f"FORMAL_EVIDENCE_BOOLEAN_INVALID:{field}")
    return value


def _count(value: object, field: str) -> int:
    if type(value) is not int or value < 0:
        raise FormalEvidenceError(f"FORMAL_EVIDENCE_COUNT_INVALID:{field}")
    return value


def _exact_fields(
    value: Mapping[str, object],
    expected: set[str],
    field: str,
) -> None:
    if set(value) != expected:
        raise FormalEvidenceError(f"FORMAL_EVIDENCE_FIELDS_INVALID:{field}")


def _canonical_bytes(value: object) -> bytes:
    try:
        return json.dumps(
            value,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=True,
            allow_nan=False,
        ).encode("ascii")
    except (TypeError, ValueError, UnicodeEncodeError) as exc:
        raise FormalEvidenceError("FORMAL_EVIDENCE_CANONICALIZATION_FAILED") from exc


def load_formal_runtime_evidence(
    config: FormalQualificationEvidenceConfig,
    *,
    authority: M5QualificationAuthority,
) -> FormalRuntimeEvidence:
    """Verify an Ed25519 envelope before constructing any runtime gate status."""

    try:
        raw_bytes = config.manifest_path.read_bytes()
        raw: object = json.loads(raw_bytes)
    except Exception as exc:
        raise FormalEvidenceError("FORMAL_EVIDENCE_MANIFEST_UNAVAILABLE") from exc
    envelope = _mapping(raw, "envelope")
    _exact_fields(envelope, {"schema", "payload", "signature"}, "envelope")
    if envelope.get("schema") != FORMAL_EVIDENCE_ENVELOPE_SCHEMA:
        raise FormalEvidenceError("FORMAL_EVIDENCE_ENVELOPE_SCHEMA_MISMATCH")

    signature = _mapping(envelope.get("signature"), "signature")
    _exact_fields(signature, {"algorithm", "key_id", "value_base64"}, "signature")
    if signature.get("algorithm") != "Ed25519":
        raise FormalEvidenceError("FORMAL_EVIDENCE_SIGNATURE_ALGORITHM_INVALID")
    if _text(signature.get("key_id"), "signature.key_id") != config.key_id:
        raise FormalEvidenceError("FORMAL_EVIDENCE_KEY_ID_MISMATCH")
    try:
        signature_bytes = base64.b64decode(
            _text(signature.get("value_base64"), "signature.value_base64"),
            validate=True,
        )
    except (ValueError, binascii.Error) as exc:
        raise FormalEvidenceError("FORMAL_EVIDENCE_SIGNATURE_ENCODING_INVALID") from exc
    if len(signature_bytes) != 64:
        raise FormalEvidenceError("FORMAL_EVIDENCE_SIGNATURE_LENGTH_INVALID")

    payload = _mapping(envelope.get("payload"), "payload")
    _exact_fields(
        payload,
        {
            "schema",
            "candidate_identity_sha256",
            "source_revision",
            "w7_external_capabilities",
            "w8_target_profiles",
            "w9",
        },
        "payload",
    )
    if payload.get("schema") != FORMAL_EVIDENCE_PAYLOAD_SCHEMA:
        raise FormalEvidenceError("FORMAL_EVIDENCE_PAYLOAD_SCHEMA_MISMATCH")
    if payload.get("candidate_identity_sha256") != config.candidate_identity_sha256:
        raise FormalEvidenceError("FORMAL_EVIDENCE_CANDIDATE_MISMATCH")
    if payload.get("source_revision") != config.source_revision:
        raise FormalEvidenceError("FORMAL_EVIDENCE_SOURCE_REVISION_MISMATCH")

    canonical_payload = _canonical_bytes(payload)
    try:
        public_key = serialization.load_pem_public_key(config.trust_root_path.read_bytes())
    except Exception as exc:
        raise FormalEvidenceError("FORMAL_EVIDENCE_TRUST_ROOT_INVALID") from exc
    if not isinstance(public_key, Ed25519PublicKey):
        raise FormalEvidenceError("FORMAL_EVIDENCE_TRUST_ROOT_NOT_ED25519")
    try:
        public_key.verify(signature_bytes, canonical_payload)
    except InvalidSignature as exc:
        raise FormalEvidenceError("FORMAL_EVIDENCE_SIGNATURE_INVALID") from exc

    w9 = _mapping(payload.get("w9"), "w9")
    _exact_fields(
        w9,
        {
            "gates",
            "unwaived_findings",
            "protected_main_exact",
            "hosted_ci_success",
            "independent_approval_complete",
        },
        "w9",
    )
    findings = _mapping(w9.get("unwaived_findings"), "w9.unwaived_findings")
    _exact_fields(findings, {"blocker", "high"}, "w9.unwaived_findings")
    signature_sha256 = hashlib.sha256(signature_bytes).hexdigest()
    w7_registry = build_w7_external_registry(
        _sequence(payload.get("w7_external_capabilities"), "w7_external_capabilities")
    )
    w8_status = build_w8_operations_status(
        authority,
        _sequence(payload.get("w8_target_profiles"), "w8_target_profiles"),
    )
    w9_status = build_w9_final_qualification_status(
        _sequence(w9.get("gates"), "w9.gates"),
        candidate_identity_sha256=config.candidate_identity_sha256,
        source_revision=config.source_revision,
        unwaived_blocker_count=_count(findings.get("blocker"), "w9.blocker"),
        unwaived_high_count=_count(findings.get("high"), "w9.high"),
        protected_main_exact=_boolean(
            w9.get("protected_main_exact"),
            "w9.protected_main_exact",
        ),
        hosted_ci_success=_boolean(w9.get("hosted_ci_success"), "w9.hosted_ci_success"),
        independent_approval_complete=_boolean(
            w9.get("independent_approval_complete"),
            "w9.independent_approval_complete",
        ),
        signature_sha256=signature_sha256,
    )
    return FormalRuntimeEvidence(
        w7_external_capabilities=w7_registry,
        w8_operations_status=w8_status,
        w9_final_qualification_status=w9_status,
        envelope_sha256=hashlib.sha256(raw_bytes).hexdigest(),
        signature_sha256=signature_sha256,
    )


__all__ = [
    "FORMAL_EVIDENCE_ENVELOPE_SCHEMA",
    "FORMAL_EVIDENCE_PAYLOAD_SCHEMA",
    "FormalEvidenceError",
    "FormalRuntimeEvidence",
    "load_formal_runtime_evidence",
]
