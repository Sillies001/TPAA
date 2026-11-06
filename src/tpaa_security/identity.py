"""OIDC/JWKS and mutual-TLS identity verification with lifecycle controls."""

from __future__ import annotations

import base64
import json
import ssl
import time
import urllib.request
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from threading import Lock
from typing import Protocol

from cryptography import x509
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric import padding, rsa

from .permissions import SecurityRole
from .policy import AuthorizationPrincipal


class IdentityVerificationError(PermissionError):
    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(code)


def _b64url(value: str) -> bytes:
    try:
        return base64.urlsafe_b64decode(value + "=" * (-len(value) % 4))
    except Exception as exc:
        raise IdentityVerificationError("TOKEN_ENCODING_INVALID") from exc


def _json_segment(value: str) -> Mapping[str, object]:
    try:
        parsed: object = json.loads(_b64url(value))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise IdentityVerificationError("TOKEN_JSON_INVALID") from exc
    if not isinstance(parsed, dict):
        raise IdentityVerificationError("TOKEN_JSON_INVALID")
    return parsed


def _text(claims: Mapping[str, object], name: str) -> str:
    value = claims.get(name)
    if not isinstance(value, str) or not value or value != value.strip():
        raise IdentityVerificationError(f"TOKEN_{name.upper()}_INVALID")
    return value


def _numeric(claims: Mapping[str, object], name: str) -> float:
    value = claims.get(name)
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise IdentityVerificationError(f"TOKEN_{name.upper()}_INVALID")
    return float(value)


class JwksProvider(Protocol):
    def keys(self) -> Mapping[str, Mapping[str, object]]: ...


class StaticJwksProvider:
    def __init__(self, document: Mapping[str, object]) -> None:
        values = document.get("keys")
        if not isinstance(values, list):
            raise IdentityVerificationError("JWKS_INVALID")
        result: dict[str, Mapping[str, object]] = {}
        for item in values:
            if not isinstance(item, dict):
                raise IdentityVerificationError("JWKS_INVALID")
            kid = item.get("kid")
            if not isinstance(kid, str) or not kid or kid in result:
                raise IdentityVerificationError("JWKS_KID_INVALID")
            result[kid] = item
        self._keys = result

    def keys(self) -> Mapping[str, Mapping[str, object]]:
        return self._keys


class HttpsJwksProvider:
    """Small HTTPS-only cache; a new ``kid`` forces one refresh for rotation."""

    def __init__(self, uri: str, *, cache_seconds: int = 300) -> None:
        if not uri.startswith("https://"):
            raise ValueError("JWKS URI must use HTTPS")
        if cache_seconds < 1:
            raise ValueError("cache_seconds must be positive")
        self._uri = uri
        self._cache_seconds = cache_seconds
        self._cached: Mapping[str, Mapping[str, object]] = {}
        self._expires = 0.0
        self._lock = Lock()

    def keys(self) -> Mapping[str, Mapping[str, object]]:
        now = time.monotonic()
        with self._lock:
            if self._cached and now < self._expires:
                return self._cached
            request = urllib.request.Request(
                self._uri,
                headers={"Accept": "application/json", "User-Agent": "tpaa/1.0"},
            )
            try:
                with urllib.request.urlopen(  # noqa: S310 - HTTPS enforced above
                    request,
                    timeout=5.0,
                    context=ssl.create_default_context(),
                ) as response:
                    document: object = json.loads(response.read(1_048_577))
            except Exception as exc:
                raise IdentityVerificationError("JWKS_UNAVAILABLE") from exc
            if not isinstance(document, dict):
                raise IdentityVerificationError("JWKS_INVALID")
            self._cached = StaticJwksProvider(document).keys()
            self._expires = now + self._cache_seconds
            return self._cached

    def refresh(self) -> None:
        with self._lock:
            self._expires = 0.0


class RevocationRegistry(Protocol):
    def token_revoked(self, issuer: str, jti: str, issued_at: int) -> bool: ...

    def certificate_revoked(self, fingerprint: str, serial_number: int) -> bool: ...


class InMemoryRevocationRegistry:
    def __init__(self) -> None:
        self.revoked_jti: set[tuple[str, str]] = set()
        self.revoked_certificates: set[tuple[str, int]] = set()
        self.issuer_not_before: dict[str, int] = {}

    def token_revoked(self, issuer: str, jti: str, issued_at: int) -> bool:
        return (issuer, jti) in self.revoked_jti or issued_at < self.issuer_not_before.get(
            issuer, 0
        )

    def certificate_revoked(self, fingerprint: str, serial_number: int) -> bool:
        return (fingerprint, serial_number) in self.revoked_certificates


class JsonRevocationRegistry:
    """Reloadable deployment revocation set; malformed updates fail closed."""

    def __init__(self, path: Path) -> None:
        self._path = path

    def _document(self) -> Mapping[str, object]:
        try:
            value: object = json.loads(self._path.read_text(encoding="utf-8"))
        except Exception as exc:
            raise IdentityVerificationError("REVOCATION_REGISTRY_UNAVAILABLE") from exc
        if not isinstance(value, dict) or value.get("schema") != "TPAA_REVOCATION_REGISTRY_V1":
            raise IdentityVerificationError("REVOCATION_REGISTRY_INVALID")
        return value

    def token_revoked(self, issuer: str, jti: str, issued_at: int) -> bool:
        document = self._document()
        revoked = document.get("revoked_tokens")
        not_before = document.get("issuer_not_before")
        if not isinstance(revoked, list) or not isinstance(not_before, dict):
            raise IdentityVerificationError("REVOCATION_REGISTRY_INVALID")
        if any(
            isinstance(item, dict) and item.get("issuer") == issuer and item.get("jti") == jti
            for item in revoked
        ):
            return True
        threshold = not_before.get(issuer, 0)
        if isinstance(threshold, bool) or not isinstance(threshold, int):
            raise IdentityVerificationError("REVOCATION_REGISTRY_INVALID")
        return issued_at < threshold

    def certificate_revoked(self, fingerprint: str, serial_number: int) -> bool:
        revoked = self._document().get("revoked_certificates")
        if not isinstance(revoked, list):
            raise IdentityVerificationError("REVOCATION_REGISTRY_INVALID")
        return any(
            isinstance(item, dict)
            and item.get("fingerprint") == fingerprint
            and item.get("serial_number") == serial_number
            for item in revoked
        )


@dataclass(frozen=True, slots=True)
class OidcConfiguration:
    issuer: str
    audience: str
    maximum_token_age_seconds: int = 900
    clock_skew_seconds: int = 30
    roles_claim: str = "tpaa_roles"
    scopes_claim: str = "tpaa_scopes"
    require_certificate_binding: bool = True

    def __post_init__(self) -> None:
        if not self.issuer.startswith("https://") or not self.audience:
            raise ValueError("OIDC issuer must use HTTPS and audience is required")
        if self.maximum_token_age_seconds < 1 or self.clock_skew_seconds < 0:
            raise ValueError("OIDC token lifetime policy is invalid")


@dataclass(frozen=True, slots=True)
class AuthenticatedIdentity:
    principal: AuthorizationPrincipal
    claims: Mapping[str, object]
    certificate_fingerprint: str | None


class OidcTokenVerifier:
    def __init__(
        self,
        config: OidcConfiguration,
        jwks: JwksProvider,
        revocations: RevocationRegistry,
    ) -> None:
        self._config = config
        self._jwks = jwks
        self._revocations = revocations

    def verify(
        self,
        token: str,
        *,
        certificate_fingerprint: str | None,
        now: datetime | None = None,
    ) -> AuthenticatedIdentity:
        parts = token.split(".")
        if len(parts) != 3 or not all(parts):
            raise IdentityVerificationError("TOKEN_COMPACT_INVALID")
        header = _json_segment(parts[0])
        claims = _json_segment(parts[1])
        if header.get("alg") != "RS256" or header.get("typ") not in {None, "JWT", "at+jwt"}:
            raise IdentityVerificationError("TOKEN_ALGORITHM_DENIED")
        kid = _text(header, "kid")
        jwk = self._jwks.keys().get(kid)
        if jwk is None and isinstance(self._jwks, HttpsJwksProvider):
            self._jwks.refresh()
            jwk = self._jwks.keys().get(kid)
        if jwk is None:
            raise IdentityVerificationError("TOKEN_KEY_UNKNOWN")
        if jwk.get("kty") != "RSA" or jwk.get("use", "sig") != "sig":
            raise IdentityVerificationError("TOKEN_KEY_INVALID")
        n = jwk.get("n")
        e = jwk.get("e")
        if not isinstance(n, str) or not isinstance(e, str):
            raise IdentityVerificationError("TOKEN_KEY_INVALID")
        public_key = rsa.RSAPublicNumbers(
            int.from_bytes(_b64url(e), "big"),
            int.from_bytes(_b64url(n), "big"),
        ).public_key()
        try:
            public_key.verify(
                _b64url(parts[2]),
                f"{parts[0]}.{parts[1]}".encode("ascii"),
                padding.PKCS1v15(),
                hashes.SHA256(),
            )
        except Exception as exc:
            raise IdentityVerificationError("TOKEN_SIGNATURE_INVALID") from exc

        instant = datetime.now(UTC) if now is None else now.astimezone(UTC)
        epoch = instant.timestamp()
        issuer = _text(claims, "iss")
        subject = _text(claims, "sub")
        jti = _text(claims, "jti")
        issued_at = int(_numeric(claims, "iat"))
        expires = _numeric(claims, "exp")
        if issuer != self._config.issuer:
            raise IdentityVerificationError("TOKEN_ISSUER_DENIED")
        audience = claims.get("aud")
        if isinstance(audience, str):
            audiences = {audience}
        elif isinstance(audience, list) and all(isinstance(item, str) for item in audience):
            audiences = set(audience)
        else:
            raise IdentityVerificationError("TOKEN_AUDIENCE_INVALID")
        if self._config.audience not in audiences:
            raise IdentityVerificationError("TOKEN_AUDIENCE_DENIED")
        if expires <= epoch - self._config.clock_skew_seconds:
            raise IdentityVerificationError("TOKEN_EXPIRED")
        if issued_at > epoch + self._config.clock_skew_seconds:
            raise IdentityVerificationError("TOKEN_ISSUED_IN_FUTURE")
        if epoch - issued_at > self._config.maximum_token_age_seconds:
            raise IdentityVerificationError("TOKEN_TOO_OLD")
        nbf = claims.get("nbf")
        if nbf is not None and _numeric(claims, "nbf") > epoch + self._config.clock_skew_seconds:
            raise IdentityVerificationError("TOKEN_NOT_ACTIVE")
        if self._revocations.token_revoked(issuer, jti, issued_at):
            raise IdentityVerificationError("TOKEN_REVOKED")

        confirmation = claims.get("cnf")
        bound_fingerprint: object = None
        if isinstance(confirmation, dict):
            bound_fingerprint = confirmation.get("x5t#S256")
        if self._config.require_certificate_binding:
            if not isinstance(bound_fingerprint, str) or not certificate_fingerprint:
                raise IdentityVerificationError("TOKEN_CERTIFICATE_BINDING_REQUIRED")
            if bound_fingerprint != certificate_fingerprint:
                raise IdentityVerificationError("TOKEN_CERTIFICATE_BINDING_MISMATCH")

        raw_roles = claims.get(self._config.roles_claim)
        raw_scopes = claims.get(self._config.scopes_claim, [])
        if not isinstance(raw_roles, list) or not isinstance(raw_scopes, list):
            raise IdentityVerificationError("TOKEN_AUTHORIZATION_CLAIMS_INVALID")
        try:
            roles = frozenset(SecurityRole(str(value)) for value in raw_roles)
        except ValueError as exc:
            raise IdentityVerificationError("TOKEN_ROLE_DENIED") from exc
        scopes = frozenset(str(value) for value in raw_scopes if isinstance(value, str))
        if not roles or len(scopes) != len(raw_scopes):
            raise IdentityVerificationError("TOKEN_AUTHORIZATION_CLAIMS_INVALID")
        return AuthenticatedIdentity(
            principal=AuthorizationPrincipal(
                subject=subject,
                roles=roles,
                scopes=scopes,
                authentication_method="OIDC_MTLS" if certificate_fingerprint else "OIDC",
                credential_id=jti,
            ),
            claims=claims,
            certificate_fingerprint=certificate_fingerprint,
        )


@dataclass(frozen=True, slots=True)
class MtlsConfiguration:
    ca_certificate_pem: bytes
    allowed_spiffe_prefixes: tuple[str, ...]

    def __post_init__(self) -> None:
        if not self.ca_certificate_pem or not self.allowed_spiffe_prefixes:
            raise ValueError("mTLS trust and SPIFFE scope are required")


@dataclass(frozen=True, slots=True)
class VerifiedClientCertificate:
    fingerprint: str
    serial_number: int
    subject: str
    spiffe_id: str


class MtlsCertificateVerifier:
    def __init__(
        self,
        config: MtlsConfiguration,
        revocations: RevocationRegistry,
    ) -> None:
        self._config = config
        self._revocations = revocations
        self._ca = x509.load_pem_x509_certificate(config.ca_certificate_pem)

    def verify(
        self,
        certificate_pem: bytes,
        *,
        now: datetime | None = None,
    ) -> VerifiedClientCertificate:
        try:
            certificate = x509.load_pem_x509_certificate(certificate_pem)
            certificate.verify_directly_issued_by(self._ca)
        except Exception as exc:
            raise IdentityVerificationError("MTLS_CERTIFICATE_UNTRUSTED") from exc
        instant = datetime.now(UTC) if now is None else now.astimezone(UTC)
        if instant < certificate.not_valid_before_utc or instant >= certificate.not_valid_after_utc:
            raise IdentityVerificationError("MTLS_CERTIFICATE_EXPIRED")
        fingerprint = (
            base64.urlsafe_b64encode(certificate.fingerprint(hashes.SHA256()))
            .rstrip(b"=")
            .decode("ascii")
        )
        if self._revocations.certificate_revoked(fingerprint, certificate.serial_number):
            raise IdentityVerificationError("MTLS_CERTIFICATE_REVOKED")
        try:
            sans = certificate.extensions.get_extension_for_class(
                x509.SubjectAlternativeName
            ).value.get_values_for_type(x509.UniformResourceIdentifier)
        except x509.ExtensionNotFound as exc:
            raise IdentityVerificationError("MTLS_SPIFFE_ID_REQUIRED") from exc
        matches = [
            value
            for value in sans
            if any(value.startswith(prefix) for prefix in self._config.allowed_spiffe_prefixes)
        ]
        if len(matches) != 1:
            raise IdentityVerificationError("MTLS_SPIFFE_ID_DENIED")
        return VerifiedClientCertificate(
            fingerprint=fingerprint,
            serial_number=certificate.serial_number,
            subject=certificate.subject.rfc4514_string(),
            spiffe_id=matches[0],
        )


__all__ = [
    "AuthenticatedIdentity",
    "HttpsJwksProvider",
    "IdentityVerificationError",
    "InMemoryRevocationRegistry",
    "JsonRevocationRegistry",
    "JwksProvider",
    "MtlsCertificateVerifier",
    "MtlsConfiguration",
    "OidcConfiguration",
    "OidcTokenVerifier",
    "RevocationRegistry",
    "StaticJwksProvider",
    "VerifiedClientCertificate",
]
