"""Production request adapters for W3 OIDC/mTLS and Desktop local identity."""

from __future__ import annotations

import base64
import getpass
import os
import platform
from collections.abc import Mapping
from pathlib import Path

from cryptography import x509
from cryptography.hazmat.primitives.serialization import Encoding
from fastapi import Request

from tpaa_api.unified import UnifiedPrincipal, UnifiedPrincipalResolver
from tpaa_security import (
    AuthorizationPrincipal,
    DesktopIdentityProvider,
    EnvironmentSecretManager,
    LocalAccount,
    MtlsCertificateVerifier,
    OidcTokenVerifier,
    Permission,
    SecurityPolicy,
)

from .identity import ProductionIdentityError


def _unified(
    principal: AuthorizationPrincipal,
    policy: SecurityPolicy,
) -> UnifiedPrincipal:
    permissions = set().union(*(policy.role_permissions[role] for role in principal.roles))
    return UnifiedPrincipal(
        role=policy.projection_role(principal.roles),
        actor_id=principal.subject,
        scope_match=bool(principal.scopes),
        privileged_identity_authorized=Permission.DIRECT_IDENTITY_READ in permissions,
        visibility_authorized=Permission.DERIVED_DATA_READ in permissions,
        export_authorized=bool(
            {Permission.EXPORT_DEIDENTIFIED, Permission.EXPORT_IDENTIFIED} & permissions
        ),
        security_roles=tuple(sorted(role.value for role in principal.roles)),
        resource_scopes=tuple(sorted(principal.scopes)),
        authentication_method=principal.authentication_method,
        credential_id=principal.credential_id,
    )


class OidcMtlsRequestIdentityProvider:
    """Authenticate bearer JWTs bound to an ASGI TLS client certificate."""

    def __init__(
        self,
        *,
        oidc: OidcTokenVerifier,
        mtls: MtlsCertificateVerifier,
        policy: SecurityPolicy,
    ) -> None:
        self._oidc = oidc
        self._mtls = mtls
        self._policy = policy

    @staticmethod
    def _certificate_pem(request: Request) -> bytes:
        extensions = request.scope.get("extensions")
        if not isinstance(extensions, dict):
            raise ProductionIdentityError("W3_MTLS_CERTIFICATE_REQUIRED")
        tls = extensions.get("tls")
        if not isinstance(tls, dict):
            raise ProductionIdentityError("W3_MTLS_CERTIFICATE_REQUIRED")
        chain = tls.get("client_cert_chain")
        if not isinstance(chain, list) or not chain:
            raise ProductionIdentityError("W3_MTLS_CERTIFICATE_REQUIRED")
        leaf = chain[0]
        if isinstance(leaf, str):
            try:
                leaf = base64.b64decode(leaf, validate=True)
            except ValueError as exc:
                raise ProductionIdentityError("W3_MTLS_CERTIFICATE_INVALID") from exc
        if not isinstance(leaf, bytes):
            raise ProductionIdentityError("W3_MTLS_CERTIFICATE_INVALID")
        if leaf.startswith(b"-----BEGIN CERTIFICATE-----"):
            return leaf
        try:
            return x509.load_der_x509_certificate(leaf).public_bytes(Encoding.PEM)
        except ValueError as exc:
            raise ProductionIdentityError("W3_MTLS_CERTIFICATE_INVALID") from exc

    def resolve(self, request: Request) -> UnifiedPrincipal:
        header = request.headers.get("authorization", "")
        scheme, separator, token = header.partition(" ")
        if separator != " " or scheme.lower() != "bearer" or not token:
            raise ProductionIdentityError("W3_OIDC_BEARER_REQUIRED")
        certificate = self._mtls.verify(self._certificate_pem(request))
        identity = self._oidc.verify(
            token,
            certificate_fingerprint=certificate.fingerprint,
        )
        return _unified(identity.principal, self._policy)


def oidc_mtls_principal_resolver(
    provider: OidcMtlsRequestIdentityProvider,
) -> UnifiedPrincipalResolver:
    return provider.resolve


def desktop_local_principal_resolver(
    *,
    data_root: Path,
    policy: SecurityPolicy,
    environ: Mapping[str, str] | None = None,
) -> UnifiedPrincipalResolver | None:
    """Load a signed OS-account assignment; absence leaves role routes closed."""

    values = os.environ if environ is None else environ
    raw_path = values.get("TPAA_DESKTOP_IDENTITY_FILE", "").strip()
    secret_reference = values.get("TPAA_DESKTOP_IDENTITY_KEY_REF", "").strip()
    if not raw_path and not secret_reference:
        return None
    if not raw_path or not secret_reference:
        raise ValueError("Desktop identity file and key reference must be configured together")
    assignment_file = Path(raw_path)
    if not assignment_file.is_absolute():
        raise ValueError("TPAA_DESKTOP_IDENTITY_FILE must be absolute")
    try:
        assignment_file.resolve(strict=False).relative_to(data_root.resolve(strict=False))
    except ValueError as exc:
        raise ValueError("Desktop identity file must be inside the Desktop data root") from exc
    provider = DesktopIdentityProvider(
        assignment_file,
        secret_reference=secret_reference,
        secrets=EnvironmentSecretManager(values),
        account=LocalAccount(
            account_id=getpass.getuser(),
            device_id=platform.node(),
        ),
    )

    def resolve(_request: Request) -> UnifiedPrincipal:
        return _unified(provider.resolve(), policy)

    return resolve


__all__ = [
    "OidcMtlsRequestIdentityProvider",
    "desktop_local_principal_resolver",
    "oidc_mtls_principal_resolver",
]
