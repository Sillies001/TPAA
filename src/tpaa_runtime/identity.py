"""PRCB C3 fail-closed production identity adapter."""

from __future__ import annotations

import hashlib
import hmac

from fastapi import Request

from tpaa_api.unified import UnifiedPrincipal, UnifiedPrincipalResolver

from .config import ProductionPrincipalBinding
from .principal_policy import (
    PrincipalPolicyError,
    validate_production_principal_policy,
)


class ProductionIdentityError(PermissionError):
    """Production principal is unavailable or violates frozen least privilege."""


def validate_production_principal(value: object) -> UnifiedPrincipal:
    if not isinstance(value, UnifiedPrincipal):
        raise ProductionIdentityError("PRCB_C3_PRINCIPAL_INVALID")
    try:
        validate_production_principal_policy(
            role=value.role,
            privileged_identity_authorized=value.privileged_identity_authorized,
            visibility_authorized=value.visibility_authorized,
            export_authorized=value.export_authorized,
        )
    except PrincipalPolicyError as exc:
        raise ProductionIdentityError(f"PRCB_C3_{exc.code}") from exc
    return value


class ConfiguredBearerIdentityProvider:
    """Map bearer-token SHA-256 fingerprints to frozen least-privilege principals."""

    def __init__(
        self,
        bindings: tuple[ProductionPrincipalBinding, ...],
    ) -> None:
        if not bindings:
            raise ValueError("configured identity provider requires principal bindings")
        self._bindings = bindings

    def resolve(self, request: Request) -> UnifiedPrincipal:
        header = request.headers.get("authorization", "")
        scheme, separator, credential = header.partition(" ")
        if (
            separator != " "
            or scheme.lower() != "bearer"
            or not credential
            or credential.strip() != credential
        ):
            raise ProductionIdentityError("PRCB_C3_BEARER_REQUIRED")
        digest = hashlib.sha256(credential.encode("utf-8")).hexdigest()
        for binding in self._bindings:
            if hmac.compare_digest(digest, binding.credential_sha256):
                return validate_production_principal(
                    UnifiedPrincipal(
                        role=binding.role,
                        actor_id=binding.actor_id,
                        scope_match=binding.scope_match,
                        validation_only=binding.validation_only,
                        privileged_identity_authorized=(binding.privileged_identity_authorized),
                        visibility_authorized=binding.visibility_authorized,
                        export_authorized=binding.export_authorized,
                    )
                )
        raise ProductionIdentityError("PRCB_C3_CREDENTIAL_NOT_AUTHORIZED")


def configured_service_principal_resolver(
    bindings: tuple[ProductionPrincipalBinding, ...],
) -> UnifiedPrincipalResolver:
    provider = ConfiguredBearerIdentityProvider(bindings)
    return provider.resolve


def guard_production_principal_resolver(
    resolver: UnifiedPrincipalResolver,
) -> UnifiedPrincipalResolver:
    def guarded(request: Request) -> object:
        return validate_production_principal(resolver(request))

    return guarded
