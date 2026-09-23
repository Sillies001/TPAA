from __future__ import annotations

import json
import sys
from pathlib import Path

from tools.manifest.build_artifacts import build_evidence, write_evidence

REPO_ROOT = Path(__file__).resolve().parents[3]


def _profile() -> str:
    return "WINDOWS_DESKTOP_X64" if sys.platform == "win32" else "LINUX_DESKTOP_X64"


def test_build_manifest_sbom_license_and_native_inventory_are_traceable(tmp_path: Path) -> None:
    profile = _profile()
    evidence = build_evidence(profile)

    build = evidence["build-manifest.json"]
    assert build["schema"] == "TPAA_M0_BUILD_MANIFEST_V1"
    assert build["qualification"] == "DEVELOPMENT_NOT_M5_QUALIFIED"
    assert build["platform_profile"] == profile
    assert build["core_baseline"] == "CB-1.4.0"
    assert build["db_schema_version"] == "1.6.0"
    assert len(str(build["source_revision"])) == 40
    assert len(str(build["baseline_lock_sha256"])) == 64
    assert len(str(build["dependency_lock_sha256"])) == 64

    sbom = evidence["sbom.cdx.json"]
    assert sbom["bomFormat"] == "CycloneDX"
    assert sbom["specVersion"] == "1.6"
    assert isinstance(sbom["components"], list)
    assert sbom["components"]

    licenses = evidence["license-report.json"]
    assert licenses["qualification"] == "ENGINEERING_INVENTORY_NOT_LEGAL_APPROVAL"
    assert len(licenses["packages"]) == len(sbom["components"])

    native = evidence["native-dependencies.json"]
    assert native["schema"] == "TPAA_M0_NATIVE_DEPENDENCIES_V1"
    native_names = {item["name"] for item in native["dependencies"]}
    assert "pyside6" in native_names
    assert "psycopg-binary" in native_names

    written = write_evidence(profile, tmp_path)
    assert set(written) == {
        "build-manifest.json",
        "license-report.json",
        "native-dependencies.json",
        "sbom.cdx.json",
        "third-party-dependencies.json",
    }
    for name, digest in written.items():
        assert len(digest) == 64
        assert json.loads((tmp_path / name).read_text(encoding="utf-8"))


def test_manifest_outputs_never_serialize_common_secret_fields(tmp_path: Path) -> None:
    write_evidence(_profile(), tmp_path)
    combined = "\n".join(
        path.read_text(encoding="utf-8").casefold()
        for path in sorted(tmp_path.glob("*.json"))
    )
    for forbidden in (
        "authorization: bearer",
        "bearer_token",
        "password=",
        "private_key",
        "credential=",
    ):
        assert forbidden not in combined
