#!/usr/bin/env python3
"""Verify the locally frozen v33 GUI target and G0R runtime evidence."""

from __future__ import annotations

import argparse
import hashlib
import json
from collections.abc import Mapping, Sequence
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[2]
BASELINE_PATH = REPO_ROOT / "docs" / "gui" / "demo-v33" / "DEMO_TARGET_BASELINE.json"
REGISTRY_PATH = REPO_ROOT / "docs" / "gui" / "demo-v33" / "V33_FINAL_VIEW_REGISTRY.json"
MATRIX_PATH = REPO_ROOT / "docs" / "compliance" / "GUI_V33_CONFORMANCE_MATRIX.json"
VERSION_PATH = (
    REPO_ROOT / "docs" / "gui" / "demo-v33" / "G0R_VERSION_AND_COMPATIBILITY_DECISION.json"
)
EVIDENCE_PATH = REPO_ROOT / "evidence" / "gui-g0-v33" / "g0-runtime-spike.json"
EVIDENCE_1280_PATH = (
    REPO_ROOT / "evidence" / "gui-g0-v33" / "v01-1280x720" / "g0-runtime-spike.json"
)
OUTPUT_PATH = REPO_ROOT / "evidence" / "gui-g0-v33" / "g0r-v33-closure.json"
EXPECTED_BASELINE = "GUI-DEMO-V33-2026-11-05"
EXPECTED_VIEWS = tuple(f"V{index:02d}" for index in range(1, 27))
EXPECTED_THEMES = ("tactical", "graphite", "light")
EXPECTED_HASHES = {
    "demo": "7aa5ff433fcaa49c3a54ac592acb43c42ee98fd944d4fb66de6e75bac2401a9a",
    "overall_patch": "abc6b000b846dbe2e367cb5af67efe7f152ebef1a26ab0fc104918a7b37de3bb",
    "engineering_patch": "26be99db27d726bd25830281da0023202bcb7b048be1d02ac81278265666890f",
    "gap_list": "402c3941c9be625b488c8e3425ed8fee7d0c3ba78f4084471e17688f231a6896",
    "r3_3_manifest": "1b70d8149975da0635b79adb1eb72e2f37743739def2ead7ade27bfb3b6db421",
    "cb_1_4_lock": "06fb823c8db79a19a45bb5f1da2c201644945c3967de94a312acd8f93d0ab437",
    "cb_1_5_lock": "ecdb68d0aa17ad49b2b0b3bdbad0e82559cd455725a0eb2a2a4855feba99edab",
    "cb_1_5_provenance": "9f771642b32a2da3d4b5f3b88ba22302fbe05f49e5284d6d85308a6485967ce8",
}


class G0RVerificationError(RuntimeError):
    """A G0R gate failed."""


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _load_object(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise G0RVerificationError(f"cannot load JSON object {path}: {exc}") from exc
    if not isinstance(value, dict):
        raise G0RVerificationError(f"expected JSON object: {path}")
    return value


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise G0RVerificationError(message)


def _check_hash(path: Path, expected: str, label: str) -> dict[str, Any]:
    _require(path.is_file(), f"missing {label}: {path}")
    actual = _sha256(path)
    _require(actual == expected, f"{label} hash mismatch: {actual} != {expected}")
    return {"label": label, "path": str(path), "sha256": actual, "status": "PASS"}


def _verify_package_manifest(path: Path) -> dict[str, Any]:
    root = path.parent
    entries = []
    for line_number, raw_line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        line = raw_line.strip()
        if not line:
            continue
        parts = line.split(maxsplit=1)
        _require(len(parts) == 2 and len(parts[0]) == 64, f"invalid manifest line {line_number}")
        expected, relative = parts[0].lower(), parts[1].strip()
        _require(not Path(relative).is_absolute() and ".." not in Path(relative).parts, "unsafe manifest path")
        artifact = root / relative
        _require(artifact.is_file(), f"missing R3.3 artifact: {artifact}")
        actual = _sha256(artifact)
        _require(actual == expected, f"R3.3 artifact hash mismatch: {relative}")
        entries.append(relative)
    _require(bool(entries), "R3.3 package manifest is empty")
    return {"path": str(path), "artifacts": len(entries), "status": "PASS"}


def _source_paths() -> dict[str, Path]:
    source_root = REPO_ROOT / "docs" / "gui" / "demo-v33" / "source"
    return {
        "demo": source_root / "TPAA_训练复盘交互Demo_v33.html",
        "overall_patch": source_root / "TPAA_V8.0_总体设计方案_Patch_历史多批次总览与攻防双视角_v1.3.md",
        "engineering_patch": source_root / "TPAA_ED-2.0_工程设计方案_Patch_历史多批次聚合与攻防复盘_v1.3.md",
        "gap_list": source_root / "TPAA_V8.0_总体与工程设计方案_Patch差距清单_v1.3.md",
        "r3_3_manifest": REPO_ROOT
        / "docs"
        / "design"
        / "TPAA_V8.0_ED-2.0_Rebaseline_R3.3"
        / "PACKAGE_MANIFEST.sha256",
        "cb_1_4_lock": REPO_ROOT / "baseline" / "CB-1.4.0" / "BASELINE_LOCK.json",
        "cb_1_5_lock": REPO_ROOT / "baseline" / "CB-1.5.0" / "BASELINE_LOCK.json",
        "cb_1_5_provenance": (
            REPO_ROOT / "baseline" / "CB-1.5.0" / "canonical" / "SOURCE_PROVENANCE.json"
        ),
    }


def _verify_output(item: Mapping[str, Any], width: int, height: int) -> None:
    relative = item.get("path")
    if not isinstance(relative, str):
        raise G0RVerificationError(f"invalid screenshot path: {item!r}")
    path = REPO_ROOT / relative
    _require(path.is_file(), f"missing screenshot: {path}")
    _require(item.get("sha256") == _sha256(path), f"screenshot hash mismatch: {path}")
    _require(item.get("bytes") == path.stat().st_size, f"screenshot size mismatch: {path}")
    _require((item.get("width"), item.get("height")) == (width, height), f"bad dimensions: {path}")


def _verify_geometry(item: Mapping[str, Any], expected_scale: float) -> None:
    geometry = item.get("geometry")
    if not isinstance(geometry, dict):
        raise G0RVerificationError(f"missing V01 geometry: {item.get('path')}")
    _require(geometry.get("schema") == "TPAA_V01_ELEMENT_GEOMETRY_V1", "bad geometry schema")
    _require(geometry.get("issues") == [], f"V01 geometry issues: {geometry.get('issues')!r}")
    scale = geometry.get("scale")
    if not isinstance(scale, (int, float)):
        raise G0RVerificationError("missing geometry scale")
    _require(abs(float(scale) - expected_scale) <= 0.002, f"unexpected V01 scale: {scale}")
    children = geometry.get("children")
    if not isinstance(children, dict):
        raise G0RVerificationError("missing V01 child geometry")
    expected_counts = {"kpi": 6, "row_first_panel": 2, "row_second_panel": 3, "row_bottom_panel": 2}
    for key, count in expected_counts.items():
        _require(isinstance(children.get(key), list), f"missing geometry group: {key}")
        _require(len(children[key]) == count, f"bad geometry group count: {key}")


def _verify_manifest(
    path: Path,
    *,
    width: int,
    height: int,
    web_views: Sequence[str],
    qml_views: Sequence[str],
    expected_scale: float,
) -> dict[str, Any]:
    manifest = _load_object(path)
    _require(manifest.get("status") == "PASS", f"runtime evidence is not PASS: {path}")
    _require(manifest.get("baseline_id") == EXPECTED_BASELINE, f"wrong baseline: {path}")
    _require(manifest.get("demo_sha256") == EXPECTED_HASHES["demo"], f"wrong demo hash: {path}")
    _require(manifest.get("viewport") == {"width": width, "height": height}, f"wrong viewport: {path}")
    results = manifest.get("results")
    if not isinstance(results, list):
        raise G0RVerificationError(f"missing results: {path}")
    by_engine = {item.get("engine"): item for item in results if isinstance(item, dict)}
    for engine, required_views in (("webengine", web_views), ("qml", qml_views)):
        if not required_views:
            _require(engine not in by_engine, f"unexpected engine {engine}: {path}")
            continue
        result = by_engine.get(engine)
        if not isinstance(result, dict):
            raise G0RVerificationError(f"missing engine {engine}: {path}")
        outputs = result.get("outputs")
        if not isinstance(outputs, list):
            raise G0RVerificationError(f"missing outputs for {engine}: {path}")
        expected_pairs = {(theme, view) for theme in EXPECTED_THEMES for view in required_views}
        actual_pairs = {(item.get("theme"), item.get("view")) for item in outputs if isinstance(item, dict)}
        _require(actual_pairs == expected_pairs, f"{engine} view/theme coverage mismatch: {path}")
        _require(len(outputs) == len(expected_pairs), f"duplicate {engine} outputs: {path}")
        for item in outputs:
            if not isinstance(item, dict):
                raise G0RVerificationError(f"invalid {engine} output: {path}")
            _verify_output(item, width, height)
            if engine == "webengine" and item.get("view") == "V01":
                _verify_geometry(item, expected_scale)
    return {
        "path": str(path),
        "webengine_outputs": len(web_views) * len(EXPECTED_THEMES),
        "qml_outputs": len(qml_views) * len(EXPECTED_THEMES),
        "status": "PASS",
    }


def verify() -> dict[str, Any]:
    baseline = _load_object(BASELINE_PATH)
    registry = _load_object(REGISTRY_PATH)
    matrix = _load_object(MATRIX_PATH)
    version = _load_object(VERSION_PATH)
    _require(baseline.get("baseline_id") == EXPECTED_BASELINE, "wrong target baseline id")
    _require(tuple(baseline.get("views", ())) == EXPECTED_VIEWS, "baseline view registry drift")
    _require(registry.get("view_count") == 26, "final registry view count drift")
    registry_views = tuple(item.get("id") for item in registry.get("views", ()) if isinstance(item, dict))
    _require(registry_views == EXPECTED_VIEWS, "final registry ids drift")
    _require(matrix.get("baseline") == EXPECTED_BASELINE, "conformance matrix baseline drift")
    _require(matrix.get("coverage", {}).get("mapped_views") == 26, "matrix coverage drift")
    _require(version.get("status") == "APPROVED_LOCAL_FOR_G1_IMPLEMENTATION", "version decision open")
    _require(version.get("release_claim") is False, "G0R must not make a release claim")
    source_checks = [
        _check_hash(_source_paths()[name], expected, name)
        for name, expected in EXPECTED_HASHES.items()
    ]
    predecessor_manifest = _verify_package_manifest(_source_paths()["r3_3_manifest"])
    evidence_checks = [
        _verify_manifest(
            EVIDENCE_PATH,
            width=1600,
            height=900,
            web_views=EXPECTED_VIEWS,
            qml_views=("V01", "V04", "V08", "V26"),
            expected_scale=1.0,
        ),
        _verify_manifest(
            EVIDENCE_1280_PATH,
            width=1280,
            height=720,
            web_views=("V01",),
            qml_views=(),
            expected_scale=0.8,
        ),
    ]
    for adr in (
        "ADR-GUI-001-webengine-product-shell.md",
        "ADR-GUI-002-p-v-view-contract.md",
        "ADR-GUI-003-theme-session-semantics.md",
    ):
        text = (REPO_ROOT / "docs" / "adr" / adr).read_text(encoding="utf-8")
        _require("2026-11-06" in text and ("v33" in text or "V26" in text), f"ADR not revised: {adr}")
    return {
        "schema": "TPAA_G0R_V33_CLOSURE_EVIDENCE_V1",
        "status": "PASS",
        "verified_at": datetime.now(UTC).isoformat(timespec="seconds").replace("+00:00", "Z"),
        "baseline_id": EXPECTED_BASELINE,
        "source_checks": source_checks,
        "predecessor_manifest": predecessor_manifest,
        "runtime_evidence": evidence_checks,
        "view_count": 26,
        "theme_count": 3,
        "webengine_reference_screenshots": 81,
        "qml_contract_screenshots": 12,
        "v01_geometry_viewports": ["1600x900", "1280x720"],
        "runtime_decision": "WEBENGINE_PREFERRED_QML_FALLBACK_PENDING_TARGET_GATES",
        "open_external_gates": [
            "target Windows and Linux GPU/software rendering qualification",
            "offline package SBOM license and renderer recovery qualification",
            "independent G12 release approval",
        ],
        "release_claim": False,
    }


def _parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=OUTPUT_PATH)
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    args = _parse_args(argv)
    result = verify()
    output = args.output.resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"status": "PASS", "output": str(output)}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
