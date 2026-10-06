from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
BASE = ROOT / "docs" / "baseline" / "PRCB-1.0"


def test_prcb_c5_release_contract_freezes_four_production_profiles() -> None:
    contract = json.loads(
        (BASE / "C5_RELEASE_CONTRACT.json").read_text(encoding="utf-8")
    )
    assert contract["schema"] == "TPAA_PRCB_C5_RELEASE_CONTRACT_V1"
    assert contract["target_product_version"] == "1.0.1"
    assert contract["db_schema_version"] == "1.9.0"
    assert contract["mandatory_profiles"] == [
        "LINUX_DESKTOP_X64",
        "LINUX_SERVICE_X64",
        "WINDOWS_DESKTOP_X64",
        "WINDOWS_SERVICE_X64",
    ]
    policy = contract["package_policy"]
    assert policy["tests_packaged"] is False
    assert policy["fixtures_packaged"] is False
    assert policy["formal_release_claimed"] is False


def test_prcb_c5_package_path_is_separate_from_historical_piqb() -> None:
    packager = (ROOT / "tools" / "packaging" / "prcb_release_bundle.py").read_text(
        encoding="utf-8"
    )
    runtime = (ROOT / "tools" / "packaging" / "prcb_runtime_entry.py").read_text(
        encoding="utf-8"
    )
    assert "TPAA_1_0_1_CANDIDATE_NOT_QUALIFIED" in packager
    assert "prcb-release" in packager
    assert "app/tests/" in packager
    assert "/fixtures/" in packager
    assert "ProductRuntimeConfig" not in runtime
    assert "ProductionRuntimeConfig" in runtime
    assert "build_desktop_production_runtime" in runtime
    assert "build_service_production_runtime" in runtime
    assert "m1_fixture_root" not in runtime
    assert "desktop-p1-e2e" in runtime
    assert "P2_ATTRIBUTION" in runtime
    assert "prepare_prcb_c5_p2_workspace" in runtime
    assert "bootstrap_sqlite" in runtime
    assert "create_desktop_production_backup" in runtime
    assert "restore_desktop_production_backup" in runtime
    assert "SQLiteDesktopUnitOfWork" in runtime
    assert "formal_release_claimed" in runtime
    assert "PRCB_C2_NOMINAL_FLIGHT.json" in packager
    assert '%~1' in packager
    assert 'goto default' in packager
    assert '$#' in packager
    assert 'then set --' in packager


def test_prcb_c5_installed_desktop_qualification_runs_inside_existing_jobs() -> None:
    workflow = (ROOT / ".github" / "workflows" / "cross-platform-ci.yml").read_text(
        encoding="utf-8"
    )
    tool = (
        ROOT
        / "tools"
        / "testing"
        / "prcb_c5_installed_desktop_qualification.py"
    ).read_text(encoding="utf-8")
    assert "Execute PRCB C5 installed Desktop P1 qualification" in workflow
    assert "prcb_c5_installed_desktop_qualification.py" in workflow
    assert "dist/prcb-c5/${{ matrix.platform }}" in workflow
    assert "TPAA_PRCB_C5_INSTALLED_DESKTOP_QUALIFICATION_V1" in tool
    assert "build_prcb_release_bundle" in tool
    assert "desktop-p1-e2e" in tool
    assert "package_sha256" in tool
    assert "logical_product_sha256" in tool
    assert "app/tests/" in tool
    assert "/fixtures/" in tool


def test_prcb_c5_p2_qualification_seed_is_product_code_not_test_fixture() -> None:
    source = (
        ROOT / "src" / "tpaa_qualification" / "prcb_c5_p2.py"
    ).read_text(encoding="utf-8")
    assert "prepare_prcb_c5_p2_workspace" in source
    assert "P2PersistenceRepository" in source
    assert "register_workspace_inputs" in source
    assert "exact_compute_input" in source
    assert "tests/fixtures" not in source
    assert "tools.testing" not in source
