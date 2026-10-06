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
    assert "formal_release_claimed" in runtime
