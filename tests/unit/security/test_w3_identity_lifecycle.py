from __future__ import annotations

import base64
import json
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding, rsa
from cryptography.x509.oid import NameOID

from tpaa_security import (
    ASSIGNMENT_SCHEMA,
    DesktopIdentityError,
    DesktopIdentityProvider,
    IdentityVerificationError,
    InMemoryRevocationRegistry,
    InMemoryVersionedSecretManager,
    LocalAccount,
    MtlsCertificateVerifier,
    MtlsConfiguration,
    OidcConfiguration,
    OidcTokenVerifier,
    SecretMaterial,
    StaticJwksProvider,
    sign_assignment,
)

NOW = datetime(2026, 10, 21, 8, 0, tzinfo=UTC)


def _b64(value: bytes) -> str:
    return base64.urlsafe_b64encode(value).rstrip(b"=").decode("ascii")


def _certificates() -> tuple[rsa.RSAPrivateKey, bytes, bytes]:
    ca_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    ca_name = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, "TPAA Test CA")])
    ca = (
        x509.CertificateBuilder()
        .subject_name(ca_name)
        .issuer_name(ca_name)
        .public_key(ca_key.public_key())
        .serial_number(1)
        .not_valid_before(NOW - timedelta(days=1))
        .not_valid_after(NOW + timedelta(days=30))
        .add_extension(x509.BasicConstraints(ca=True, path_length=0), critical=True)
        .sign(ca_key, hashes.SHA256())
    )
    leaf_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    leaf_name = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, "TPAA Service Client")])
    leaf = (
        x509.CertificateBuilder()
        .subject_name(leaf_name)
        .issuer_name(ca_name)
        .public_key(leaf_key.public_key())
        .serial_number(2)
        .not_valid_before(NOW - timedelta(hours=1))
        .not_valid_after(NOW + timedelta(days=1))
        .add_extension(
            x509.SubjectAlternativeName(
                [x509.UniformResourceIdentifier("spiffe://tpaa/service/client-1")]
            ),
            critical=False,
        )
        .sign(ca_key, hashes.SHA256())
    )
    return (
        leaf_key,
        ca.public_bytes(serialization.Encoding.PEM),
        leaf.public_bytes(serialization.Encoding.PEM),
    )


def _token(
    key: rsa.RSAPrivateKey,
    fingerprint: str,
    *,
    audience: str = "tpaa-service",
    expires: datetime = NOW + timedelta(minutes=5),
) -> tuple[str, dict[str, object]]:
    public = key.public_key().public_numbers()
    jwk = {
        "kid": "rotation-key-1",
        "kty": "RSA",
        "use": "sig",
        "n": _b64(public.n.to_bytes((public.n.bit_length() + 7) // 8, "big")),
        "e": _b64(public.e.to_bytes((public.e.bit_length() + 7) // 8, "big")),
    }
    header = {"alg": "RS256", "typ": "at+jwt", "kid": "rotation-key-1"}
    claims = {
        "iss": "https://identity.example.test",
        "sub": "00000000-0000-4000-8000-000000000001",
        "aud": audience,
        "iat": int(NOW.timestamp()),
        "exp": int(expires.timestamp()),
        "jti": "token-1",
        "tpaa_roles": ["MODEL_REVIEWER"],
        "tpaa_scopes": ["*"],
        "cnf": {"x5t#S256": fingerprint},
    }
    encoded_header = _b64(json.dumps(header, separators=(",", ":")).encode())
    encoded_claims = _b64(json.dumps(claims, separators=(",", ":")).encode())
    signing_input = f"{encoded_header}.{encoded_claims}".encode("ascii")
    signature = key.sign(signing_input, padding.PKCS1v15(), hashes.SHA256())
    return f"{encoded_header}.{encoded_claims}.{_b64(signature)}", jwk


def test_oidc_mtls_binding_rotation_and_revocation() -> None:
    token_key, ca_pem, client_pem = _certificates()
    revocations = InMemoryRevocationRegistry()
    mtls = MtlsCertificateVerifier(
        MtlsConfiguration(ca_pem, ("spiffe://tpaa/service/",)), revocations
    )
    certificate = mtls.verify(client_pem, now=NOW)
    token, jwk = _token(token_key, certificate.fingerprint)
    verifier = OidcTokenVerifier(
        OidcConfiguration(
            issuer="https://identity.example.test",
            audience="tpaa-service",
        ),
        StaticJwksProvider({"keys": [jwk]}),
        revocations,
    )
    identity = verifier.verify(
        token,
        certificate_fingerprint=certificate.fingerprint,
        now=NOW,
    )
    assert identity.principal.credential_id == "token-1"
    assert identity.principal.authentication_method == "OIDC_MTLS"

    with pytest.raises(IdentityVerificationError, match="TOKEN_CERTIFICATE_BINDING_MISMATCH"):
        verifier.verify(token, certificate_fingerprint="wrong", now=NOW)
    revocations.revoked_jti.add(("https://identity.example.test", "token-1"))
    with pytest.raises(IdentityVerificationError, match="TOKEN_REVOKED"):
        verifier.verify(token, certificate_fingerprint=certificate.fingerprint, now=NOW)
    revocations.revoked_certificates.add((certificate.fingerprint, certificate.serial_number))
    with pytest.raises(IdentityVerificationError, match="MTLS_CERTIFICATE_REVOKED"):
        mtls.verify(client_pem, now=NOW)


def test_oidc_wrong_audience_and_expiry_fail_closed() -> None:
    token_key, ca_pem, client_pem = _certificates()
    revocations = InMemoryRevocationRegistry()
    certificate = MtlsCertificateVerifier(
        MtlsConfiguration(ca_pem, ("spiffe://tpaa/service/",)), revocations
    ).verify(client_pem, now=NOW)
    token, jwk = _token(token_key, certificate.fingerprint, audience="wrong")
    verifier = OidcTokenVerifier(
        OidcConfiguration(
            issuer="https://identity.example.test", audience="tpaa-service"
        ),
        StaticJwksProvider({"keys": [jwk]}),
        revocations,
    )
    with pytest.raises(IdentityVerificationError, match="TOKEN_AUDIENCE_DENIED"):
        verifier.verify(token, certificate_fingerprint=certificate.fingerprint, now=NOW)
    expired, _ = _token(
        token_key, certificate.fingerprint, expires=NOW - timedelta(minutes=1)
    )
    with pytest.raises(IdentityVerificationError, match="TOKEN_EXPIRED"):
        verifier.verify(expired, certificate_fingerprint=certificate.fingerprint, now=NOW)


def test_desktop_assignment_binds_account_device_time_and_signature(tmp_path: Path) -> None:
    material = SecretMaterial(value=b"desktop-signing-key", key_id="desktop-key", version="v1")
    secrets = InMemoryVersionedSecretManager({"desktop": (material,)})
    payload: dict[str, object] = {
        "schema": ASSIGNMENT_SCHEMA,
        "key_id": "desktop-key",
        "account_id": "local-user",
        "device_id": "workstation-1",
        "subject": "00000000-0000-4000-8000-000000000001",
        "roles": ["INSTRUCTOR"],
        "scopes": ["*"],
        "issued_at": (NOW - timedelta(minutes=1)).isoformat(),
        "expires_at": (NOW + timedelta(hours=1)).isoformat(),
    }
    assignment = tmp_path / "identity.json"
    assignment.write_text(
        json.dumps({**payload, "signature": sign_assignment(payload, material.value)}),
        encoding="utf-8",
    )
    provider = DesktopIdentityProvider(
        assignment,
        secret_reference="secret://desktop/v1",
        secrets=secrets,
        account=LocalAccount("local-user", "workstation-1"),
    )
    assert provider.resolve(now=NOW).authentication_method == "DESKTOP_LOCAL_ACCOUNT"
    document = json.loads(assignment.read_text(encoding="utf-8"))
    document["roles"] = ["ADMINISTRATOR"]
    assignment.write_text(json.dumps(document), encoding="utf-8")
    with pytest.raises(DesktopIdentityError, match="DESKTOP_IDENTITY_SIGNATURE_INVALID"):
        provider.resolve(now=NOW)
