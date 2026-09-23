from __future__ import annotations

import copy
import json

from tools.testing.fixture_harness import (
    DEFAULT_BUNDLE,
    fixture_evidence,
    platform_equivalence_evidence,
    platform_product,
)


def test_m0_fixture_harness_evidence_and_platform_diff(tmp_path) -> None:
    return_code, evidence = fixture_evidence(DEFAULT_BUNDLE)
    assert return_code == 0
    assert evidence["status"] == "PASS"
    assert evidence["fixture_id"] == "M0_BASIC_TRANSPORT_V1"
    assert evidence["failure_classification"] is None

    base = platform_product(DEFAULT_BUNDLE)
    windows = copy.deepcopy(base)
    linux = copy.deepcopy(base)
    windows["platform"] = {"logical": "windows", "system": "Windows", "machine": "AMD64"}
    linux["platform"] = {"logical": "linux", "system": "Linux", "machine": "x86_64"}

    windows_path = tmp_path / "windows.json"
    linux_path = tmp_path / "linux.json"
    output = tmp_path / "logical-equivalence.json"
    windows_path.write_text(json.dumps(windows), encoding="utf-8")
    linux_path.write_text(json.dumps(linux), encoding="utf-8")

    compare_code, compare_evidence = platform_equivalence_evidence(windows_path, linux_path)
    output.write_text(json.dumps(compare_evidence), encoding="utf-8")

    assert compare_code == 0
    assert compare_evidence["status"] == "PASS"
    assert compare_evidence["mismatches"] == []
    assert output.is_file()
