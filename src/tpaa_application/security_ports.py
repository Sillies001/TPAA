"""Reserved service-profile identity/RBAC ports for later secure deployment wiring."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol


@dataclass(frozen=True)
class ServicePrincipal:
    subject: str
    roles: tuple[str, ...]


class ServiceIdentityPort(Protocol):
    def authenticate(self, credential: str) -> ServicePrincipal:
        """Authenticate a Service-profile credential without exposing provider internals."""


class ServiceAuthorizationPort(Protocol):
    def require(self, principal: ServicePrincipal, permission: str) -> None:
        """Fail closed unless the principal has the requested permission."""
