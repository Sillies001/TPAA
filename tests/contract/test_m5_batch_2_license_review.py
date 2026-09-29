from __future__ import annotations

import json

from tools.manifest.build_artifacts import M5_LICENSE_REVIEW, build_evidence

EXPECTED_REVIEWED = {
    ("colorama", "0.4.6", "BSD-3-Clause"),
    ("jinja2", "3.1.6", "BSD-3-Clause"),
    ("markdown-it-py", "4.2.0", "MIT"),
    ("mdurl", "0.1.2", "MIT"),
    ("tzdata", "2026.4", "Apache-2.0"),
    ("uvloop", "0.22.1", "MIT OR Apache-2.0"),
}


def test_m5_exact_version_license_review_closes_all_unknowns() -> None:
    registry = json.loads(M5_LICENSE_REVIEW.read_text(encoding="utf-8"))
    registry_packages = registry["packages"]
    assert isinstance(registry_packages, list)
    registry_reviewed = {
        (
            str(item["name"]),
            str(item["version"]),
            str(item["spdx_license"]),
        )
        for item in registry_packages
        if isinstance(item, dict)
    }
    assert registry_reviewed == EXPECTED_REVIEWED
    assert all(
        isinstance(item.get("source"), str)
        and item["source"].startswith("https://pypi.org/project/")
        for item in registry_packages
        if isinstance(item, dict)
    )

    evidence = build_evidence("LINUX_DESKTOP_X64")
    packages = evidence["license-report.json"]["packages"]
    assert isinstance(packages, list)
    unknown = [
        item
        for item in packages
        if isinstance(item, dict)
        and item.get("declared_license") == "UNKNOWN_REQUIRES_REVIEW"
    ]
    assert unknown == []

    reviewed = {
        (
            str(item["name"]),
            str(item["version"]),
            str(item["declared_license"]),
        )
        for item in packages
        if isinstance(item, dict)
        and item.get("license_resolution") == "M5_EXACT_VERSION_REVIEW"
    }
    assert reviewed <= EXPECTED_REVIEWED
    assert all(
        isinstance(item.get("license_review_source"), str)
        and item["license_review_source"].startswith("https://pypi.org/project/")
        for item in packages
        if isinstance(item, dict)
        and item.get("license_resolution") == "M5_EXACT_VERSION_REVIEW"
    )
