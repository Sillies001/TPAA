"""Fail-closed configuration for public Desktop and Service entry points."""

from __future__ import annotations

import json
import os
import re
import tomllib
from collections.abc import Mapping
from importlib.metadata import PackageNotFoundError, version
from pathlib import Path

from tpaa_storage import S3ObjectStore, bootstrap_sqlite, verify_sqlite

from .config import (
    OidcMtlsRuntimeConfig,
    ProductionPrincipalBinding,
    ProductionRuntimeConfig,
    RuntimeProfile,
)

SERVICE_PRINCIPALS_SCHEMA = "TPAA_SERVICE_PRINCIPALS_V1"
SERVICE_PRINCIPAL_FIELDS = frozenset(
    {
        "credential_sha256",
        "role",
        "actor_id",
        "scope_match",
        "validation_only",
        "privileged_identity_authorized",
        "visibility_authorized",
        "export_authorized",
    }
)
AUTHORITY_RELATIVE_PATH = Path("baseline") / "CB-1.5.0" / "canonical"
AUTHORITY_MARKER = "CORE_RULES.json"
RUNTIME_CONFIG_SCHEMA = "TPAA_RUNTIME_CONFIG_V1"
RUNTIME_CORE_BASELINE = "CB-1.5.0"
RUNTIME_DB_SCHEMA_VERSION = "1.9.0"
_SECRET_REFERENCE = re.compile(r"^env://([A-Z][A-Z0-9_]*)$")
_RUNTIME_CONFIG_FIELDS = frozenset(
    {
        "schema",
        "profile",
        "product_build_version",
        "core_baseline",
        "db_schema_version",
        "authority_root",
        "data_root",
        "object_root",
        "identity",
        "database",
        "object_store",
        "migration_state_root",
    }
)


def project_version(app_root: Path | None = None) -> str:
    """Read one project version from installed metadata or a source root."""

    if app_root is None:
        try:
            return version("tpaa")
        except PackageNotFoundError:
            candidates = Path(__file__).resolve().parents
    else:
        candidates = (app_root.resolve(strict=False),)

    for root in candidates:
        metadata = root / "pyproject.toml"
        if not metadata.is_file():
            continue
        raw = tomllib.loads(metadata.read_text(encoding="utf-8"))
        project = raw.get("project")
        if not isinstance(project, dict):
            break
        value = project.get("version")
        if isinstance(value, str) and value.strip():
            return value
        break
    raise RuntimeError("project version unavailable")


def _absolute_path(value: str | Path, *, field: str) -> Path:
    path = Path(value).expanduser()
    if not path.is_absolute():
        raise ValueError(f"{field} must be an absolute path")
    return path.resolve(strict=False)


def _valid_authority_root(path: Path) -> bool:
    return path.is_dir() and (path / AUTHORITY_MARKER).is_file()


def _document_text(values: Mapping[str, object], key: str) -> str:
    value = values.get(key)
    if not isinstance(value, str) or not value or value != value.strip():
        raise ValueError(f"runtime config field {key} must be non-empty text")
    return value


def _document_mapping(values: Mapping[str, object], key: str) -> Mapping[str, object]:
    value = values.get(key)
    if not isinstance(value, Mapping):
        raise ValueError(f"runtime config field {key} must be an object")
    return value


def _resolve_secret_reference(
    reference: object,
    *,
    field: str,
    environ: Mapping[str, str],
) -> str:
    if not isinstance(reference, str):
        raise ValueError(f"{field} must use an env:// secret reference")
    match = _SECRET_REFERENCE.fullmatch(reference)
    if match is None:
        raise ValueError(f"{field} must use an env:// secret reference")
    value = environ.get(match.group(1), "")
    if not value:
        raise ValueError(f"secret reference for {field} is unavailable")
    return value


def load_runtime_config_document(
    path: Path,
    *,
    expected_product_build_version: str,
    expected_authority_root: Path,
    environ: Mapping[str, str] | None = None,
) -> ProductionRuntimeConfig:
    """Load the shared Desktop/Service V1 document with secret references only."""

    source = _absolute_path(path, field="TPAA_RUNTIME_CONFIG_FILE")
    try:
        raw: object = json.loads(source.read_text(encoding="utf-8"))
    except Exception as exc:
        raise ValueError("runtime configuration document is unavailable") from exc
    if not isinstance(raw, Mapping) or raw.get("schema") != RUNTIME_CONFIG_SCHEMA:
        raise ValueError("runtime configuration schema mismatch")
    unexpected = sorted(set(raw) - _RUNTIME_CONFIG_FIELDS)
    if unexpected:
        raise ValueError("runtime configuration contains unsupported fields")
    if _document_text(raw, "product_build_version") != expected_product_build_version:
        raise ValueError("runtime configuration product version handshake failed")
    if _document_text(raw, "core_baseline") != RUNTIME_CORE_BASELINE:
        raise ValueError("runtime configuration Core baseline handshake failed")
    if _document_text(raw, "db_schema_version") != RUNTIME_DB_SCHEMA_VERSION:
        raise ValueError("runtime configuration DB schema handshake failed")
    authority_root = _absolute_path(
        _document_text(raw, "authority_root"),
        field="authority_root",
    )
    if authority_root != expected_authority_root.resolve(strict=False):
        raise ValueError("runtime configuration authority root handshake failed")
    if not _valid_authority_root(authority_root):
        raise ValueError("runtime configuration authority root is invalid")

    profile_text = _document_text(raw, "profile")
    try:
        profile = RuntimeProfile(profile_text)
    except ValueError as exc:
        raise ValueError("runtime configuration profile is invalid") from exc
    values = os.environ if environ is None else environ
    if profile is RuntimeProfile.DESKTOP:
        forbidden = (
            "object_root",
            "identity",
            "database",
            "object_store",
        )
        if any(key in raw for key in forbidden):
            raise ValueError("Desktop runtime configuration contains Service fields")
        data_root = _absolute_path(
            _document_text(raw, "data_root"),
            field="data_root",
        )
        return prepare_desktop_production_config(
            product_build_version=expected_product_build_version,
            authority_root=authority_root,
            data_root=data_root,
        )

    if "data_root" in raw:
        raise ValueError("Service runtime configuration forbids data_root")
    database = _document_mapping(raw, "database")
    if set(database) != {"backend", "conninfo_ref"}:
        raise ValueError("Service database configuration fields are invalid")
    if _document_text(database, "backend") != "POSTGRESQL":
        raise ValueError("Service database backend must be POSTGRESQL")
    conninfo = _resolve_secret_reference(
        database.get("conninfo_ref"),
        field="database.conninfo_ref",
        environ=values,
    )
    object_root = _absolute_path(
        _document_text(raw, "object_root"),
        field="object_root",
    )
    object_root.mkdir(parents=True, exist_ok=True)
    if not object_root.is_dir():
        raise RuntimeError("service object root is not a directory")
    principals: tuple[ProductionPrincipalBinding, ...] = ()
    identity = _document_mapping(raw, "identity")
    expected_identity_fields = {
        "mode",
        "issuer",
        "audience",
        "jwks_uri",
        "ca_bundle",
        "allowed_spiffe_prefixes",
        "revocation_file",
    }
    if set(identity) != expected_identity_fields:
        raise ValueError("Service identity configuration fields are invalid")
    if _document_text(identity, "mode") != "OIDC_MTLS":
        raise ValueError("Service identity mode must be OIDC_MTLS")
    raw_prefixes = identity.get("allowed_spiffe_prefixes")
    if (
        not isinstance(raw_prefixes, list)
        or not raw_prefixes
        or not all(
            isinstance(value, str) and value.startswith("spiffe://") for value in raw_prefixes
        )
    ):
        raise ValueError("Service SPIFFE prefixes are invalid")
    service_identity = OidcMtlsRuntimeConfig(
        issuer=_document_text(identity, "issuer"),
        audience=_document_text(identity, "audience"),
        jwks_uri=_document_text(identity, "jwks_uri"),
        ca_bundle_path=_absolute_path(
            _document_text(identity, "ca_bundle"), field="identity.ca_bundle"
        ),
        allowed_spiffe_prefixes=tuple(raw_prefixes),
        revocation_file=_absolute_path(
            _document_text(identity, "revocation_file"),
            field="identity.revocation_file",
        ),
    )
    migration_state_root = _absolute_path(
        _document_text(raw, "migration_state_root"),
        field="migration_state_root",
    )
    migration_state_root.mkdir(parents=True, exist_ok=True)
    object_document = _document_mapping(raw, "object_store")
    backend = _document_text(object_document, "backend")
    object_store = None
    if backend == "LOCAL":
        if set(object_document) != {"backend"}:
            raise ValueError("LOCAL object store configuration fields are invalid")
    elif backend == "S3":
        required = {
            "backend",
            "bucket",
            "prefix",
            "region",
            "access_key_id_ref",
            "secret_access_key_ref",
        }
        allowed = required | {"endpoint_url"}
        if set(object_document) - allowed or not required.issubset(object_document):
            raise ValueError("S3 object store configuration fields are invalid")
        object_store = S3ObjectStore(
            bucket=_document_text(object_document, "bucket"),
            prefix=_document_text(object_document, "prefix"),
            endpoint_url=(
                _document_text(object_document, "endpoint_url")
                if "endpoint_url" in object_document
                else None
            ),
            region_name=_document_text(object_document, "region"),
            access_key_id=_resolve_secret_reference(
                object_document.get("access_key_id_ref"),
                field="object_store.access_key_id_ref",
                environ=values,
            ),
            secret_access_key=_resolve_secret_reference(
                object_document.get("secret_access_key_ref"),
                field="object_store.secret_access_key_ref",
                environ=values,
            ),
        )
    else:
        raise ValueError("object store backend must be LOCAL or S3")
    return ProductionRuntimeConfig(
        profile=RuntimeProfile.SERVICE,
        product_build_version=expected_product_build_version,
        authority_root=authority_root,
        object_root=object_root,
        service_conninfo=conninfo,
        service_principals=principals,
        service_identity=service_identity,
        object_store=object_store,
        migration_state_root=migration_state_root,
    )


def resolve_authority_root(
    *,
    anchor: Path,
    environ: Mapping[str, str] | None = None,
) -> Path:
    """Resolve the frozen Canonical authority without relying on the CWD.

    Source/editable installs are discovered by walking up from ``anchor``.
    A regular wheel or separately deployed runtime must provide the absolute
    ``TPAA_AUTHORITY_ROOT`` path explicitly.
    """

    values = os.environ if environ is None else environ
    configured = values.get("TPAA_AUTHORITY_ROOT", "").strip()
    if configured:
        authority = _absolute_path(configured, field="TPAA_AUTHORITY_ROOT")
        if not _valid_authority_root(authority):
            raise RuntimeError(f"TPAA authority root is invalid: {authority}")
        return authority

    location = anchor.resolve(strict=False)
    start = location if location.is_dir() else location.parent
    for root in (start, *start.parents):
        authority = root / AUTHORITY_RELATIVE_PATH
        if _valid_authority_root(authority):
            return authority.resolve(strict=False)
    raise RuntimeError(
        "TPAA authority root is unavailable; set TPAA_AUTHORITY_ROOT to the "
        "absolute CB-1.5.0 canonical directory"
    )


def default_desktop_data_root(
    *,
    environ: Mapping[str, str] | None = None,
    platform_name: str | None = None,
    home: Path | None = None,
) -> Path:
    """Return one stable per-user data root without depending on the CWD."""

    values = os.environ if environ is None else environ
    configured = values.get("TPAA_DESKTOP_DATA_ROOT", "").strip()
    if configured:
        return _absolute_path(configured, field="TPAA_DESKTOP_DATA_ROOT")

    selected_platform = os.name if platform_name is None else platform_name
    selected_home = (Path.home() if home is None else home).resolve(strict=False)
    if selected_platform == "nt":
        base = values.get("LOCALAPPDATA", "").strip() or values.get("APPDATA", "").strip()
        root = selected_home if not base else _absolute_path(base, field="LOCALAPPDATA")
        return root / "TPAA"

    xdg_data = values.get("XDG_DATA_HOME", "").strip()
    root = (
        selected_home / ".local" / "share"
        if not xdg_data
        else _absolute_path(xdg_data, field="XDG_DATA_HOME")
    )
    return root / "tpaa"


def _bootstrap_desktop_database(database: Path, *, authority_root: Path) -> None:
    if database.exists():
        verify_sqlite(database, authority_root=authority_root)
        return

    staging = database.with_name(f".{database.name}.bootstrap")
    if staging.exists():
        raise RuntimeError(f"desktop database bootstrap staging already exists: {staging}")
    sidecars = (
        Path(f"{staging}-wal"),
        Path(f"{staging}-shm"),
    )
    try:
        bootstrap_sqlite(staging, authority_root=authority_root)
        verify_sqlite(staging, authority_root=authority_root)
        staging.replace(database)
    except Exception:
        staging.unlink(missing_ok=True)
        for sidecar in sidecars:
            sidecar.unlink(missing_ok=True)
        raise


def prepare_desktop_production_config(
    *,
    product_build_version: str,
    authority_root: Path,
    data_root: Path,
) -> ProductionRuntimeConfig:
    """Create or verify one Desktop DB 1.9 runtime without fixture fallback."""

    resolved_root = _absolute_path(data_root, field="desktop_data_root")
    resolved_root.mkdir(parents=True, exist_ok=True)
    if not resolved_root.is_dir():
        raise RuntimeError(f"desktop data root is not a directory: {resolved_root}")

    database = resolved_root / "tpaa.sqlite3"
    _bootstrap_desktop_database(database, authority_root=authority_root)
    object_root = resolved_root / "objects"
    object_root.mkdir(parents=True, exist_ok=True)
    if not object_root.is_dir():
        raise RuntimeError(f"desktop object root is not a directory: {object_root}")

    return ProductionRuntimeConfig(
        profile=RuntimeProfile.DESKTOP,
        product_build_version=product_build_version,
        authority_root=authority_root,
        object_root=object_root,
        desktop_database_path=database,
        migration_state_root=database.parent / ".tpaa-migrations",
    )


def desktop_production_config_from_environment(
    *,
    product_build_version: str,
    authority_root: Path,
    environ: Mapping[str, str] | None = None,
) -> ProductionRuntimeConfig:
    values = os.environ if environ is None else environ
    document = values.get("TPAA_RUNTIME_CONFIG_FILE", "").strip()
    if document:
        config = load_runtime_config_document(
            Path(document),
            expected_product_build_version=product_build_version,
            expected_authority_root=authority_root,
            environ=values,
        )
        if config.profile is not RuntimeProfile.DESKTOP:
            raise ValueError("Desktop entry requires a DESKTOP runtime configuration")
        return config
    return prepare_desktop_production_config(
        product_build_version=product_build_version,
        authority_root=authority_root,
        data_root=default_desktop_data_root(environ=values),
    )


def _required_text(values: Mapping[str, object], key: str) -> str:
    value = values.get(key)
    if not isinstance(value, str) or not value.strip() or value != value.strip():
        raise ValueError(f"service principal field {key} must be non-empty text")
    return value


def _boolean(values: Mapping[str, object], key: str, *, default: bool) -> bool:
    value = values.get(key, default)
    if not isinstance(value, bool):
        raise ValueError(f"service principal field {key} must be boolean")
    return value


def load_service_principal_bindings(
    path: Path,
) -> tuple[ProductionPrincipalBinding, ...]:
    """Load secret-free bearer fingerprints from one governed JSON document."""

    source = _absolute_path(path, field="TPAA_SERVICE_PRINCIPALS_FILE")
    try:
        raw: object = json.loads(source.read_text(encoding="utf-8"))
    except Exception as exc:
        raise ValueError("service principal configuration is unavailable") from exc
    if not isinstance(raw, Mapping) or raw.get("schema") != SERVICE_PRINCIPALS_SCHEMA:
        raise ValueError("service principal configuration schema mismatch")
    items = raw.get("principals")
    if not isinstance(items, list) or not items:
        raise ValueError("service principal configuration requires principals")

    bindings: list[ProductionPrincipalBinding] = []
    for index, item in enumerate(items):
        if not isinstance(item, Mapping):
            raise ValueError(f"service principal {index} must be an object")
        unexpected = sorted(set(item) - SERVICE_PRINCIPAL_FIELDS)
        if unexpected:
            raise ValueError(f"service principal {index} contains unsupported fields")
        actor = item.get("actor_id")
        if actor is not None and not isinstance(actor, str):
            raise ValueError(f"service principal {index} actor_id must be text or null")
        bindings.append(
            ProductionPrincipalBinding(
                credential_sha256=_required_text(item, "credential_sha256"),
                role=_required_text(item, "role"),
                actor_id=actor,
                scope_match=_boolean(item, "scope_match", default=False),
                validation_only=_boolean(item, "validation_only", default=False),
                privileged_identity_authorized=_boolean(
                    item,
                    "privileged_identity_authorized",
                    default=False,
                ),
                visibility_authorized=_boolean(
                    item,
                    "visibility_authorized",
                    default=False,
                ),
                export_authorized=_boolean(
                    item,
                    "export_authorized",
                    default=False,
                ),
            )
        )
    return tuple(bindings)


def service_production_config_from_environment(
    *,
    product_build_version: str,
    authority_root: Path,
    environ: Mapping[str, str] | None = None,
) -> ProductionRuntimeConfig:
    """Build Service production config with no implicit identity fallback."""

    values = os.environ if environ is None else environ
    document = values.get("TPAA_RUNTIME_CONFIG_FILE", "").strip()
    if not document:
        raise ValueError("TPAA_RUNTIME_CONFIG_FILE is required for Service")
    config = load_runtime_config_document(
        Path(document),
        expected_product_build_version=product_build_version,
        expected_authority_root=authority_root,
        environ=values,
    )
    if config.profile is not RuntimeProfile.SERVICE:
        raise ValueError("Service entry requires a SERVICE runtime configuration")
    return config
