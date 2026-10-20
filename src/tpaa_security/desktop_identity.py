"""Signed local-account identity assignment for the Desktop profile."""

from __future__ import annotations

import hashlib
import hmac
import json
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

from .permissions import SecurityRole
from .policy import AuthorizationPrincipal
from .secrets import SecretManager

ASSIGNMENT_SCHEMA = "TPAA_DESKTOP_IDENTITY_ASSIGNMENT_V1"


class DesktopIdentityError(PermissionError):
    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(code)


@dataclass(frozen=True, slots=True)
class LocalAccount:
    account_id: str
    device_id: str


def _canonical(value: object) -> bytes:
    return json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
        allow_nan=False,
    ).encode("utf-8")


def sign_assignment(payload: Mapping[str, object], key: bytes) -> str:
    return hmac.new(key, _canonical(payload), hashlib.sha256).hexdigest()


class DesktopIdentityProvider:
    """Resolve a user identity independently from the loopback bearer token."""

    def __init__(
        self,
        assignment_file: Path,
        *,
        secret_reference: str,
        secrets: SecretManager,
        account: LocalAccount,
    ) -> None:
        self._path = assignment_file
        self._secret_reference = secret_reference
        self._secrets = secrets
        self._account = account

    def resolve(self, *, now: datetime | None = None) -> AuthorizationPrincipal:
        try:
            document: object = json.loads(self._path.read_text(encoding="utf-8"))
        except Exception as exc:
            raise DesktopIdentityError("DESKTOP_IDENTITY_UNAVAILABLE") from exc
        if not isinstance(document, dict) or document.get("schema") != ASSIGNMENT_SCHEMA:
            raise DesktopIdentityError("DESKTOP_IDENTITY_SCHEMA_MISMATCH")
        signature = document.get("signature")
        key_id = document.get("key_id")
        if not isinstance(signature, str) or not isinstance(key_id, str):
            raise DesktopIdentityError("DESKTOP_IDENTITY_SIGNATURE_INVALID")
        payload = {key: value for key, value in document.items() if key != "signature"}
        material = self._secrets.resolve(self._secret_reference, now=now)
        if material.key_id != key_id or not hmac.compare_digest(
            sign_assignment(payload, material.value), signature
        ):
            raise DesktopIdentityError("DESKTOP_IDENTITY_SIGNATURE_INVALID")
        if document.get("account_id") != self._account.account_id:
            raise DesktopIdentityError("DESKTOP_ACCOUNT_MISMATCH")
        if document.get("device_id") != self._account.device_id:
            raise DesktopIdentityError("DESKTOP_DEVICE_MISMATCH")
        instant = datetime.now(UTC) if now is None else now.astimezone(UTC)
        try:
            issued = datetime.fromisoformat(str(document["issued_at"]).replace("Z", "+00:00"))
            expires = datetime.fromisoformat(str(document["expires_at"]).replace("Z", "+00:00"))
        except (KeyError, ValueError) as exc:
            raise DesktopIdentityError("DESKTOP_IDENTITY_TIME_INVALID") from exc
        if issued > instant or expires <= instant or expires <= issued:
            raise DesktopIdentityError("DESKTOP_IDENTITY_EXPIRED")
        roles = document.get("roles")
        scopes = document.get("scopes")
        subject = document.get("subject")
        if (
            not isinstance(roles, list)
            or not isinstance(scopes, list)
            or not isinstance(subject, str)
        ):
            raise DesktopIdentityError("DESKTOP_IDENTITY_CLAIMS_INVALID")
        try:
            parsed_roles = frozenset(SecurityRole(str(value)) for value in roles)
        except ValueError as exc:
            raise DesktopIdentityError("DESKTOP_IDENTITY_ROLE_DENIED") from exc
        parsed_scopes = frozenset(str(value) for value in scopes if isinstance(value, str))
        if not parsed_roles or len(parsed_scopes) != len(scopes):
            raise DesktopIdentityError("DESKTOP_IDENTITY_CLAIMS_INVALID")
        return AuthorizationPrincipal(
            subject=subject,
            roles=parsed_roles,
            scopes=parsed_scopes,
            authentication_method="DESKTOP_LOCAL_ACCOUNT",
            credential_id=hashlib.sha256(signature.encode("ascii")).hexdigest(),
        )


__all__ = [
    "ASSIGNMENT_SCHEMA",
    "DesktopIdentityError",
    "DesktopIdentityProvider",
    "LocalAccount",
    "sign_assignment",
]
