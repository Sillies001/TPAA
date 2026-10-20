from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def test_desktop_child_uses_only_durable_production_composition() -> None:
    source = (ROOT / "src" / "tpaa_api" / "local_backend_child.py").read_text(encoding="utf-8")
    assert "from tpaa_desktop import create_app" in source
    assert "build_desktop_production_runtime" not in source
    assert "create_production_desktop_app" not in source
    assert "prepare_desktop_production_config" not in source
    assert "ProductRuntimeConfig" not in source
    assert "build_desktop_application" not in source
    assert "tests/fixtures" not in source


def test_piqb_entry_has_no_qualification_runtime_fallback() -> None:
    source = (ROOT / "tools" / "packaging" / "piqb_runtime_entry.py").read_text(encoding="utf-8")
    for forbidden in (
        "ProductRuntimeConfig",
        "build_desktop_application",
        "build_service_application",
        "create_full_desktop_app",
        "create_full_service_app",
        "tests/fixtures",
        'role="SYSTEM"',
        "PIQB-DESKTOP-LOCAL-BEARER-QUALIFICATION-ONLY",
    ):
        assert forbidden not in source
    for forbidden in (
        "build_desktop_production_runtime",
        "build_service_production_runtime",
        "create_production_desktop_app",
        "create_production_service_app",
    ):
        assert forbidden not in source
    assert "from tpaa_desktop import create_app as create_desktop_app" in source
    assert "from tpaa_service import create_app as create_service_app" in source
    assert "desktop_main((), app_root=APP_ROOT)" in source
    assert "app_root=APP_ROOT" in source


def test_piqb_packager_rejects_test_material() -> None:
    source = (ROOT / "tools" / "packaging" / "piqb_release_bundle.py").read_text(encoding="utf-8")
    assert "shutil.copytree" not in source
    assert "production package contains forbidden test material" in source
    assert "_assert_production_payload(stage)" in source
    assert '"build_desktop_production_runtime"' in source
    assert '"build_service_production_runtime"' in source


def test_public_service_entry_uses_production_factory() -> None:
    source = (ROOT / "src" / "tpaa_service" / "__init__.py").read_text(encoding="utf-8")
    assert "build_service_production_runtime" in source
    assert "create_production_service_app" in source
    assert "build_service_application" not in source


def test_public_desktop_entry_uses_production_factory() -> None:
    source = (ROOT / "src" / "tpaa_desktop" / "__init__.py").read_text(
        encoding="utf-8"
    )
    assert "build_desktop_production_runtime" in source
    assert "create_production_desktop_app" in source
    assert "build_desktop_application" not in source
    assert "create_full_desktop_app" not in source


def test_gui_module_delegates_to_public_desktop_entry() -> None:
    source = (ROOT / "src" / "tpaa_gui" / "__main__.py").read_text(
        encoding="utf-8"
    )
    assert "from tpaa_desktop.__main__ import main" in source
    assert "LocalBackendController" not in source


def test_production_principal_policy_has_one_runtime_owner() -> None:
    config = (ROOT / "src" / "tpaa_runtime" / "config.py").read_text(
        encoding="utf-8"
    )
    identity = (ROOT / "src" / "tpaa_runtime" / "identity.py").read_text(
        encoding="utf-8"
    )
    policy = (ROOT / "src" / "tpaa_runtime" / "principal_policy.py").read_text(
        encoding="utf-8"
    )

    assert "_PRODUCTION_ROLES" not in config
    assert "_APPROVED_ROLES" not in identity
    assert "validate_production_principal_policy" in config
    assert "validate_production_principal_policy" in identity
    assert "class ProductionRole" in policy
    assert '"MODEL_REVIEWER"' in policy
    assert '"APPROVED_W3_LOCAL_BASELINE"' in policy
    assert '"status": "COMPLETE"' in policy
