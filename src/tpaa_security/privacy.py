"""Purpose-bound pseudonymization, redaction, export and retention policy."""

from __future__ import annotations

import hashlib
import hmac
import json
from dataclasses import dataclass
from datetime import UTC, datetime
from enum import StrEnum
from typing import Protocol

from .permissions import Permission
from .policy import AuthorizationPrincipal, AuthorizationService, ResourceContext
from .secrets import SecretManager


class DataClassification(StrEnum):
    SYNTHETIC = "SYNTHETIC"
    PUBLIC = "PUBLIC"
    INTERNAL = "INTERNAL"
    OPERATIONAL = "OPERATIONAL"
    SENSITIVE = "SENSITIVE"


class PrivacyError(PermissionError):
    def __init__(self, code: str, detail: str = "") -> None:
        self.code = code
        self.detail = detail
        super().__init__(f"{code}:{detail}" if detail else code)


class PrivacyAuditSink(Protocol):
    def record(self, action: str, details: dict[str, object]) -> None: ...


class InMemoryPrivacyAuditSink:
    def __init__(self) -> None:
        self.events: list[tuple[str, dict[str, object]]] = []

    def record(self, action: str, details: dict[str, object]) -> None:
        self.events.append((action, dict(details)))


@dataclass(frozen=True, slots=True)
class ExportManifest:
    export_id: str
    created_at: str
    actor_subject: str
    purpose: str
    classification: DataClassification
    deidentified: bool
    payload_sha256: str
    policy_sha256: str
    redacted_fields: tuple[str, ...]
    retention_until: str
    media_redaction_status: str | None

    def payload(self) -> dict[str, object]:
        return {
            "schema": "TPAA_EXPORT_MANIFEST_V1",
            "export_id": self.export_id,
            "created_at": self.created_at,
            "actor_subject": self.actor_subject,
            "purpose": self.purpose,
            "classification": self.classification.value,
            "deidentified": self.deidentified,
            "payload_sha256": self.payload_sha256,
            "policy_sha256": self.policy_sha256,
            "redacted_fields": list(self.redacted_fields),
            "retention_until": self.retention_until,
            "media_redaction_status": self.media_redaction_status,
        }


@dataclass(frozen=True, slots=True)
class RetentionDecision:
    action: str
    code: str
    physical_delete_allowed: bool


_DIRECT_IDENTIFIERS = frozenset(
    {
        "actor_id",
        "author_id",
        "person_id",
        "personnel_id",
        "name",
        "email",
        "phone",
        "callsign",
    }
)


def _canonical(value: object) -> bytes:
    return json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
        allow_nan=False,
    ).encode("utf-8")


class PrivacyService:
    def __init__(
        self,
        authorization: AuthorizationService,
        secrets: SecretManager,
        *,
        pseudonym_key_reference: str,
        audit: PrivacyAuditSink,
    ) -> None:
        self.authorization = authorization
        self.secrets = secrets
        self.pseudonym_key_reference = pseudonym_key_reference
        self.audit = audit

    def pseudonymize(self, identity: str, *, purpose: str, tenant: str) -> str:
        if not identity or not purpose or not tenant:
            raise PrivacyError("PSEUDONYM_INPUT_INVALID")
        material = self.secrets.resolve(self.pseudonym_key_reference)
        digest = hmac.new(
            material.value,
            f"{tenant}\x00{purpose}\x00{identity}".encode(),
            hashlib.sha256,
        ).hexdigest()
        return f"pseudonym:{digest}"

    def redact(
        self,
        value: object,
        *,
        purpose: str,
        tenant: str,
        permit_direct_identity: bool,
    ) -> tuple[object, tuple[str, ...]]:
        redacted: list[str] = []

        def walk(item: object, path: str) -> object:
            if isinstance(item, dict):
                result: dict[str, object] = {}
                for raw_key, child in item.items():
                    key = str(raw_key)
                    child_path = f"{path}.{key}" if path else key
                    if key.lower() in _DIRECT_IDENTIFIERS and not permit_direct_identity:
                        redacted.append(child_path)
                        result[f"{key}_pseudonym"] = self.pseudonymize(
                            str(child), purpose=purpose, tenant=tenant
                        )
                    else:
                        result[key] = walk(child, child_path)
                return result
            if isinstance(item, list):
                return [walk(child, f"{path}[{index}]") for index, child in enumerate(item)]
            return item

        return walk(value, ""), tuple(redacted)

    def export(
        self,
        principal: AuthorizationPrincipal,
        payload: object,
        *,
        resource: ResourceContext,
        classification: DataClassification,
        purpose: str,
        tenant: str,
        identified: bool,
        retention_until: datetime,
        media_redaction_status: str | None = None,
        now: datetime | None = None,
    ) -> tuple[object, ExportManifest]:
        instant = datetime.now(UTC) if now is None else now.astimezone(UTC)
        if retention_until.astimezone(UTC) <= instant:
            raise PrivacyError("EXPORT_RETENTION_INVALID")
        permission = Permission.EXPORT_IDENTIFIED if identified else Permission.EXPORT_DEIDENTIFIED
        self.authorization.require(principal, permission, resource=resource)
        if classification in {DataClassification.OPERATIONAL, DataClassification.SENSITIVE}:
            if media_redaction_status not in {None, "NOT_APPLICABLE", "REDACTED"}:
                raise PrivacyError("MEDIA_REDACTION_INCOMPLETE")
        exported, redacted = self.redact(
            payload,
            purpose=purpose,
            tenant=tenant,
            permit_direct_identity=identified,
        )
        payload_hash = hashlib.sha256(_canonical(exported)).hexdigest()
        export_id = hashlib.sha256(
            f"{principal.subject}\x00{purpose}\x00{payload_hash}\x00{instant.isoformat()}".encode()
        ).hexdigest()
        manifest = ExportManifest(
            export_id=export_id,
            created_at=instant.isoformat().replace("+00:00", "Z"),
            actor_subject=principal.subject,
            purpose=purpose,
            classification=classification,
            deidentified=not identified,
            payload_sha256=payload_hash,
            policy_sha256=self.authorization.policy.sha256,
            redacted_fields=redacted,
            retention_until=retention_until.astimezone(UTC).isoformat().replace("+00:00", "Z"),
            media_redaction_status=media_redaction_status,
        )
        self.audit.record(
            "DATA_EXPORT",
            {
                "export_id": export_id,
                "actor_subject": principal.subject,
                "classification": classification.value,
                "deidentified": not identified,
                "policy_sha256": self.authorization.policy.sha256,
                "payload_sha256": payload_hash,
            },
        )
        return exported, manifest

    def retention_decision(
        self,
        *,
        expired: bool,
        legal_hold: bool,
        release_references: tuple[str, ...],
        requested_action: str,
    ) -> RetentionDecision:
        if requested_action not in {"KEEP", "ARCHIVE", "DELETE"}:
            raise PrivacyError("RETENTION_ACTION_INVALID", requested_action)
        if legal_hold:
            return RetentionDecision("KEEP", "LEGAL_HOLD", False)
        if requested_action == "DELETE" and release_references:
            return RetentionDecision("ARCHIVE", "RELEASE_REFERENCE_PRESERVED", False)
        if requested_action == "DELETE" and not expired:
            return RetentionDecision("KEEP", "RETENTION_NOT_EXPIRED", False)
        if requested_action == "DELETE":
            return RetentionDecision("DELETE", "DELETE_ALLOWED", True)
        return RetentionDecision(requested_action, "POLICY_ACTION", False)


__all__ = [
    "DataClassification",
    "ExportManifest",
    "InMemoryPrivacyAuditSink",
    "PrivacyError",
    "PrivacyService",
    "RetentionDecision",
]
