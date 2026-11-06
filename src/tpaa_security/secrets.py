"""Secret-manager ports with explicit version and validity metadata."""

from __future__ import annotations

import re
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Protocol

_REFERENCE = re.compile(r"^(env|secret)://([A-Za-z0-9_.-]+)(?:/([A-Za-z0-9_.-]+))?$")


class SecretResolutionError(RuntimeError):
    def __init__(self, code: str, reference: str) -> None:
        self.code = code
        self.reference = reference
        super().__init__(f"{code}:{reference}")


@dataclass(frozen=True, slots=True)
class SecretMaterial:
    value: bytes
    key_id: str
    version: str
    not_before: datetime | None = None
    expires_at: datetime | None = None
    revoked: bool = False

    def active(self, now: datetime | None = None) -> bool:
        instant = datetime.now(UTC) if now is None else now.astimezone(UTC)
        return (
            not self.revoked
            and (self.not_before is None or instant >= self.not_before)
            and (self.expires_at is None or instant < self.expires_at)
        )


class SecretManager(Protocol):
    def resolve(self, reference: str, *, now: datetime | None = None) -> SecretMaterial:
        """Return active material or fail closed without logging its value."""


class EnvironmentSecretManager:
    """Development/Desktop adapter; production may inject a managed backend."""

    def __init__(self, environ: Mapping[str, str]) -> None:
        self._environ = environ

    def resolve(self, reference: str, *, now: datetime | None = None) -> SecretMaterial:
        match = _REFERENCE.fullmatch(reference)
        if match is None or match.group(1) != "env" or match.group(3) is not None:
            raise SecretResolutionError("SECRET_REFERENCE_UNSUPPORTED", reference)
        value = self._environ.get(match.group(2), "")
        if not value:
            raise SecretResolutionError("SECRET_UNAVAILABLE", reference)
        return SecretMaterial(
            value=value.encode("utf-8"),
            key_id=match.group(2),
            version="environment-current",
        )


class InMemoryVersionedSecretManager:
    """Deterministic rotation/revocation adapter used by contract tests."""

    def __init__(self, values: Mapping[str, tuple[SecretMaterial, ...]]) -> None:
        self._values = dict(values)

    def resolve(self, reference: str, *, now: datetime | None = None) -> SecretMaterial:
        match = _REFERENCE.fullmatch(reference)
        if match is None or match.group(1) != "secret":
            raise SecretResolutionError("SECRET_REFERENCE_UNSUPPORTED", reference)
        name = match.group(2)
        requested_version = match.group(3)
        candidates = self._values.get(name, ())
        for material in reversed(candidates):
            if requested_version is not None and material.version != requested_version:
                continue
            if material.active(now):
                return material
        raise SecretResolutionError("SECRET_NO_ACTIVE_VERSION", reference)


__all__ = [
    "EnvironmentSecretManager",
    "InMemoryVersionedSecretManager",
    "SecretManager",
    "SecretMaterial",
    "SecretResolutionError",
]
