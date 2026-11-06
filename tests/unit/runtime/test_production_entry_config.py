from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

import tpaa_canonical.loader as canonical_loader_module
from tpaa_desktop import create_app as create_desktop_app
from tpaa_runtime import (
    RuntimeProfile,
    default_desktop_data_root,
    load_runtime_config_document,
    load_service_principal_bindings,
    prepare_desktop_production_config,
    project_version,
    resolve_authority_root,
    service_production_config_from_environment,
)
from tpaa_storage import S3ObjectStore, verify_sqlite

ROOT = Path(__file__).resolve().parents[3]
AUTHORITY = ROOT / "baseline" / "CB-1.5.0" / "canonical"


def test_public_desktop_factory_uses_project_version_and_db_1_9(
    tmp_path: Path,
) -> None:
    data_root = tmp_path / "desktop-entry"
    app = create_desktop_app(
        bearer_token="desktop-entry-test-token-00000000",
        data_root=data_root,
        app_root=ROOT,
        environ={},
    )

    assert app.version == project_version(ROOT)
    verification = verify_sqlite(
        data_root / "tpaa.sqlite3",
        authority_root=AUTHORITY,
    )
    assert verification.schema_version == "1.9.0"
    assert verification.core_baseline == "CB-1.5.0"


def test_default_desktop_data_root_honors_absolute_override(tmp_path: Path) -> None:
    expected = tmp_path / "desktop-data"
    assert (
        default_desktop_data_root(
            environ={"TPAA_DESKTOP_DATA_ROOT": str(expected)},
            platform_name="nt",
            home=tmp_path,
        )
        == expected
    )


def test_default_desktop_data_root_rejects_cwd_relative_override() -> None:
    with pytest.raises(ValueError, match="absolute path"):
        default_desktop_data_root(environ={"TPAA_DESKTOP_DATA_ROOT": "relative-data"})


def test_authority_root_is_discovered_from_source_anchor() -> None:
    assert resolve_authority_root(anchor=Path(__file__), environ={}) == AUTHORITY


def test_authority_root_honors_valid_absolute_override(tmp_path: Path) -> None:
    authority = tmp_path / "canonical"
    authority.mkdir()
    (authority / "CORE_RULES.json").write_text("{}", encoding="utf-8")
    assert (
        resolve_authority_root(
            anchor=Path(__file__),
            environ={"TPAA_AUTHORITY_ROOT": str(authority)},
        )
        == authority
    )


def test_authority_root_rejects_invalid_override(tmp_path: Path) -> None:
    with pytest.raises(RuntimeError, match="authority root is invalid"):
        resolve_authority_root(
            anchor=Path(__file__),
            environ={"TPAA_AUTHORITY_ROOT": str(tmp_path / "missing")},
        )


def test_prepare_desktop_config_bootstraps_and_reuses_db_1_9(
    tmp_path: Path,
) -> None:
    data_root = tmp_path / "desktop"
    first = prepare_desktop_production_config(
        product_build_version="test-build",
        authority_root=AUTHORITY,
        data_root=data_root,
    )
    second = prepare_desktop_production_config(
        product_build_version="test-build",
        authority_root=AUTHORITY,
        data_root=data_root,
    )

    assert first == second
    assert first.profile is RuntimeProfile.DESKTOP
    assert first.desktop_database_path == data_root / "tpaa.sqlite3"
    assert first.object_root == data_root / "objects"
    verification = verify_sqlite(data_root / "tpaa.sqlite3")
    assert verification.schema_version == "1.9.0"
    assert verification.core_baseline == "CB-1.5.0"


def test_explicit_authority_root_does_not_depend_on_source_layout(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        canonical_loader_module,
        "_default_baseline_root",
        lambda: tmp_path / "unavailable-source-baseline",
    )
    config = prepare_desktop_production_config(
        product_build_version="installed-build",
        authority_root=AUTHORITY,
        data_root=tmp_path / "installed-data",
    )
    verification = verify_sqlite(
        config.desktop_database_path,
        authority_root=AUTHORITY,
    )
    assert verification.core_baseline == "CB-1.5.0"


def test_legacy_service_principal_loader_remains_migration_only(
    tmp_path: Path,
) -> None:
    token_hash = hashlib.sha256(b"service-test-token").hexdigest()
    principals = tmp_path / "principals.json"
    principals.write_text(
        json.dumps(
            {
                "schema": "TPAA_SERVICE_PRINCIPALS_V1",
                "principals": [
                    {
                        "credential_sha256": token_hash,
                        "role": "ANALYST",
                        "actor_id": "test-analyst",
                        "scope_match": True,
                    }
                ],
            }
        ),
        encoding="utf-8",
    )

    bindings = load_service_principal_bindings(principals)
    assert len(bindings) == 1
    assert bindings[0].role == "ANALYST"
    with pytest.raises(ValueError, match="TPAA_RUNTIME_CONFIG_FILE"):
        service_production_config_from_environment(
            product_build_version="test-build",
            authority_root=AUTHORITY,
            environ={
                "TPAA_SERVICE_CONNINFO": "dbname=tpaa",
                "TPAA_OBJECT_ROOT": str(tmp_path / "objects"),
                "TPAA_SERVICE_PRINCIPALS_FILE": str(principals),
            },
        )


def test_service_config_fails_closed_without_runtime_document(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="TPAA_RUNTIME_CONFIG_FILE"):
        service_production_config_from_environment(
            product_build_version="test-build",
            authority_root=AUTHORITY,
            environ={
                "TPAA_SERVICE_CONNINFO": "dbname=tpaa",
                "TPAA_OBJECT_ROOT": str(tmp_path / "objects"),
            },
        )


def test_service_config_rejects_direct_environment_s3_secrets(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="TPAA_RUNTIME_CONFIG_FILE"):
        service_production_config_from_environment(
            product_build_version="test-build",
            authority_root=AUTHORITY,
            environ={
                "TPAA_SERVICE_CONNINFO": "dbname=tpaa",
                "TPAA_OBJECT_STORE_BACKEND": "S3",
                "TPAA_S3_SECRET_ACCESS_KEY": "inline-secret",
            },
        )


def test_service_config_fails_closed_for_unknown_object_backend(
    tmp_path: Path,
) -> None:
    document = tmp_path / "service-runtime.json"
    document.write_text(
        json.dumps(
            {
                **_service_document(tmp_path),
                "object_store": {"backend": "UNSUPPORTED"},
            }
        ),
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="LOCAL or S3"):
        service_production_config_from_environment(
            product_build_version="test-build",
            authority_root=AUTHORITY,
            environ={
                "TPAA_RUNTIME_CONFIG_FILE": str(document),
                "TPAA_TEST_CONNINFO": "dbname=tpaa",
            },
        )


def test_service_principal_file_rejects_unknown_fields(tmp_path: Path) -> None:
    principals = tmp_path / "principals.json"
    principals.write_text(
        json.dumps(
            {
                "schema": "TPAA_SERVICE_PRINCIPALS_V1",
                "principals": [
                    {
                        "credential_sha256": hashlib.sha256(b"token").hexdigest(),
                        "role": "ANALYST",
                        "actor_id": None,
                        "scope_match": True,
                        "model_release_authorized": True,
                    }
                ],
            }
        ),
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="unsupported fields"):
        load_service_principal_bindings(principals)


def _principal_file(tmp_path: Path) -> Path:
    principals = tmp_path / "principals-v1.json"
    principals.write_text(
        json.dumps(
            {
                "schema": "TPAA_SERVICE_PRINCIPALS_V1",
                "principals": [
                    {
                        "credential_sha256": hashlib.sha256(b"document-token").hexdigest(),
                        "role": "ANALYST",
                        "actor_id": None,
                        "scope_match": True,
                    }
                ],
            }
        ),
        encoding="utf-8",
    )
    return principals


def _identity_document(tmp_path: Path) -> dict[str, object]:
    ca_bundle = tmp_path / "service-ca.pem"
    ca_bundle.write_text("test-ca-placeholder", encoding="utf-8")
    revocations = tmp_path / "revocations.json"
    revocations.write_text(
        json.dumps(
            {
                "schema": "TPAA_REVOCATION_REGISTRY_V1",
                "revoked_tokens": [],
                "revoked_certificates": [],
                "issuer_not_before": {},
            }
        ),
        encoding="utf-8",
    )
    return {
        "mode": "OIDC_MTLS",
        "issuer": "https://identity.example.test",
        "audience": "tpaa-service",
        "jwks_uri": "https://identity.example.test/.well-known/jwks.json",
        "ca_bundle": str(ca_bundle),
        "allowed_spiffe_prefixes": ["spiffe://tpaa/service/"],
        "revocation_file": str(revocations),
    }


def _service_document(tmp_path: Path) -> dict[str, object]:
    return {
        "schema": "TPAA_RUNTIME_CONFIG_V1",
        "profile": "SERVICE",
        "product_build_version": "test-build",
        "core_baseline": "CB-1.5.0",
        "db_schema_version": "1.9.0",
        "authority_root": str(AUTHORITY),
        "object_root": str(tmp_path / "service-control"),
        "migration_state_root": str(tmp_path / "migration-state"),
        "identity": _identity_document(tmp_path),
        "database": {
            "backend": "POSTGRESQL",
            "conninfo_ref": "env://TPAA_TEST_CONNINFO",
        },
        "object_store": {"backend": "LOCAL"},
    }


def test_w1_shared_desktop_runtime_config_document(tmp_path: Path) -> None:
    document = tmp_path / "desktop-runtime.json"
    data_root = tmp_path / "desktop-document-data"
    document.write_text(
        json.dumps(
            {
                "schema": "TPAA_RUNTIME_CONFIG_V1",
                "profile": "DESKTOP",
                "product_build_version": "test-build",
                "core_baseline": "CB-1.5.0",
                "db_schema_version": "1.9.0",
                "authority_root": str(AUTHORITY),
                "data_root": str(data_root),
            }
        ),
        encoding="utf-8",
    )
    config = load_runtime_config_document(
        document,
        expected_product_build_version="test-build",
        expected_authority_root=AUTHORITY,
        environ={},
    )
    assert config.profile is RuntimeProfile.DESKTOP
    assert config.desktop_database_path == data_root / "tpaa.sqlite3"
    assert verify_sqlite(config.desktop_database_path).schema_version == "1.9.0"


def test_runtime_config_loads_complete_formal_qualification_binding(
    tmp_path: Path,
) -> None:
    manifest = tmp_path / "formal-evidence.json"
    trust_root = tmp_path / "release-authority.pem"
    manifest.write_text("{}", encoding="utf-8")
    trust_root.write_text("placeholder", encoding="utf-8")
    document = tmp_path / "desktop-runtime-formal.json"
    document.write_text(
        json.dumps(
            {
                "schema": "TPAA_RUNTIME_CONFIG_V1",
                "profile": "DESKTOP",
                "product_build_version": "test-build",
                "core_baseline": "CB-1.5.0",
                "db_schema_version": "1.9.0",
                "authority_root": str(AUTHORITY),
                "data_root": str(tmp_path / "desktop-formal-data"),
                "formal_qualification": {
                    "manifest": str(manifest),
                    "trust_root": str(trust_root),
                    "key_id": "release-authority-1",
                    "candidate_identity_sha256": "a" * 64,
                    "source_revision": "b" * 40,
                },
            }
        ),
        encoding="utf-8",
    )

    config = load_runtime_config_document(
        document,
        expected_product_build_version="test-build",
        expected_authority_root=AUTHORITY,
        environ={},
    )

    assert config.formal_qualification is not None
    assert config.formal_qualification.manifest_path == manifest
    assert config.formal_qualification.candidate_identity_sha256 == "a" * 64


def test_w1_shared_service_config_resolves_secret_references(tmp_path: Path) -> None:
    document = tmp_path / "service-runtime.json"
    document.write_text(
        json.dumps(
            {
                "schema": "TPAA_RUNTIME_CONFIG_V1",
                "profile": "SERVICE",
                "product_build_version": "test-build",
                "core_baseline": "CB-1.5.0",
                "db_schema_version": "1.9.0",
                "authority_root": str(AUTHORITY),
                "object_root": str(tmp_path / "service-control"),
                "migration_state_root": str(tmp_path / "migration-state"),
                "identity": _identity_document(tmp_path),
                "database": {
                    "backend": "POSTGRESQL",
                    "conninfo_ref": "env://TPAA_TEST_CONNINFO",
                },
                "object_store": {
                    "backend": "S3",
                    "bucket": "tpaa-test",
                    "prefix": "w1",
                    "endpoint_url": "http://127.0.0.1:5000",
                    "region": "us-east-1",
                    "access_key_id_ref": "env://TPAA_TEST_ACCESS_KEY",
                    "secret_access_key_ref": "env://TPAA_TEST_SECRET_KEY",
                },
            }
        ),
        encoding="utf-8",
    )
    config = load_runtime_config_document(
        document,
        expected_product_build_version="test-build",
        expected_authority_root=AUTHORITY,
        environ={
            "TPAA_TEST_CONNINFO": "dbname=tpaa",
            "TPAA_TEST_ACCESS_KEY": "access",
            "TPAA_TEST_SECRET_KEY": "secret",
        },
    )
    assert config.profile is RuntimeProfile.SERVICE
    assert config.service_conninfo == "dbname=tpaa"
    assert config.service_identity is not None
    assert isinstance(config.object_store, S3ObjectStore)


def test_w1_runtime_config_rejects_inline_secret_and_version_drift(
    tmp_path: Path,
) -> None:
    document = tmp_path / "invalid-runtime.json"
    payload = {
        "schema": "TPAA_RUNTIME_CONFIG_V1",
        "profile": "SERVICE",
        "product_build_version": "wrong-build",
        "core_baseline": "CB-1.5.0",
        "db_schema_version": "1.9.0",
        "authority_root": str(AUTHORITY),
        "object_root": str(tmp_path / "objects"),
        "identity": _identity_document(tmp_path),
        "database": {"backend": "POSTGRESQL", "conninfo_ref": "password=inline"},
        "object_store": {"backend": "LOCAL"},
    }
    document.write_text(json.dumps(payload), encoding="utf-8")
    with pytest.raises(ValueError, match="product version handshake"):
        load_runtime_config_document(
            document,
            expected_product_build_version="test-build",
            expected_authority_root=AUTHORITY,
            environ={},
        )

    payload["product_build_version"] = "test-build"
    document.write_text(json.dumps(payload), encoding="utf-8")
    with pytest.raises(ValueError, match="env:// secret reference"):
        load_runtime_config_document(
            document,
            expected_product_build_version="test-build",
            expected_authority_root=AUTHORITY,
            environ={},
        )
