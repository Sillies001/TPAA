"""Cross-platform PIQB B5 Desktop/replay/visualization qualification."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from collections.abc import Mapping
from pathlib import Path
from typing import Any

from tpaa_gui.diagnostics import EMPTY_DIAGNOSTICS
from tpaa_gui.product_shell import (
    PRODUCT_NAVIGATION,
    PRODUCT_SPINE,
    SEMANTIC_LAYERS,
    create_product_workspace,
    validate_product_navigation,
)
from tpaa_gui.visualization import (
    build_2d_polyline,
    build_cesium_trajectory_packets,
    build_trajectory_presentation,
)

ROOT = Path(__file__).resolve().parents[2]


class _NoRequestTransport:
    """Structural Desktop transport; qualification only constructs the product surface."""

    def _unused(self, method: str, path: str) -> tuple[int, dict[str, Any]]:
        raise AssertionError(f"qualification construction performed HTTP:{method}:{path}")

    def m1_request_json(
        self,
        method: str,
        path: str,
        *,
        body: dict[str, object] | None = None,
        headers: dict[str, str] | None = None,
    ) -> tuple[int, dict[str, Any]]:
        del body, headers
        return self._unused(method, path)

    def m3_request_json(
        self,
        method: str,
        path: str,
        *,
        body: dict[str, object] | None = None,
        headers: dict[str, str] | None = None,
    ) -> tuple[int, dict[str, Any]]:
        del body, headers
        return self._unused(method, path)

    def m4_request_json(
        self,
        method: str,
        path: str,
        *,
        body: dict[str, object] | None = None,
    ) -> tuple[int, dict[str, Any]]:
        del body
        return self._unused(method, path)

    def m6_request_json(
        self,
        method: str,
        path: str,
        *,
        body: Mapping[str, object] | None = None,
    ) -> tuple[int, Mapping[str, object]]:
        del body
        return self._unused(method, path)

    def m7_request_json(
        self,
        method: str,
        path: str,
    ) -> tuple[int, Mapping[str, object]]:
        return self._unused(method, path)

    def m8_request_json(
        self,
        method: str,
        path: str,
    ) -> tuple[int, Mapping[str, object]]:
        return self._unused(method, path)

    def m9_request_json(
        self,
        method: str,
        path: str,
    ) -> tuple[int, Mapping[str, object]]:
        return self._unused(method, path)

    def runtime_request_json(
        self,
        method: str,
        path: str,
    ) -> tuple[int, Mapping[str, object]]:
        return self._unused(method, path)


def _canonical_hash(value: object) -> str:
    raw = json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
        allow_nan=False,
    ).encode("ascii")
    return hashlib.sha256(raw).hexdigest()


def _trajectory_fixture() -> dict[str, object]:
    release_id = "11111111-1111-4111-8111-111111111111"
    return {
        "schema": "TPAA_TRAJECTORY_PRESENTATION_V1",
        "release_id": release_id,
        "time_semantics": "SESSION_TIME",
        "business_recompute": False,
        "persistence_access": False,
        "mutable_alias_resolution": False,
        "samples": [
            {
                "session_time_us": 1_000_000,
                "latitude_deg": 34.0,
                "longitude_deg": -117.0,
                "altitude_m": 1000.0,
                "source_release_id": release_id,
                "evidence_ref": "evidence:1",
            },
            {
                "session_time_us": 2_000_000,
                "latitude_deg": 34.1,
                "longitude_deg": -116.9,
                "altitude_m": 1100.0,
                "source_release_id": release_id,
                "evidence_ref": "evidence:2",
            },
        ],
        "media": [
            {
                "media_id": "media-1",
                "media_type": "VIDEO",
                "uri": "tpaa-media://media-1",
                "source_release_id": release_id,
                "evidence_ref": "evidence:1",
            }
        ],
    }


def qualify(*, platform: str, source_revision: str) -> dict[str, object]:
    if platform not in {"linux", "windows"}:
        raise ValueError("platform must be linux or windows")
    if len(source_revision) != 40:
        raise ValueError("source_revision must be a 40-character git SHA")

    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    from PySide6 import QtCore, QtWidgets

    validate_product_navigation()
    existing = QtWidgets.QApplication.instance()
    app = existing if existing is not None else QtWidgets.QApplication(["tpaa-b5-qualification"])
    workspace = create_product_workspace(
        QtCore,
        QtWidgets,
        None,
        transport=_NoRequestTransport(),
        diagnostics_provider=lambda: EMPTY_DIAGNOSTICS,
    )
    navigation = workspace.findChild(QtWidgets.QListWidget, "tpaaB5ProductNavigation")
    stack = workspace.findChild(QtWidgets.QStackedWidget, "tpaaB5ProductStack")
    tabs = workspace.findChild(QtWidgets.QTabWidget, "tpaaB5LongitudinalVisualTabs")
    spine = workspace.findChild(QtWidgets.QLabel, "tpaaB5ProductSpine")
    semantic = workspace.findChild(QtWidgets.QLabel, "tpaaB5SemanticLegend")

    fixture = _trajectory_fixture()
    release_id = str(fixture["release_id"])
    presentation = build_trajectory_presentation(
        fixture,
        expected_release_id=release_id,
    )
    polyline = build_2d_polyline(presentation)
    cesium = build_cesium_trajectory_packets(presentation)

    navigation_rows = (
        []
        if navigation is None
        else [
            navigation.item(index).text()
            for index in range(navigation.count())
        ]
    )
    logical_product = {
        "navigation": [
            {
                "slot": item.slot,
                "key": item.key,
                "title": item.title,
                "surface": item.surface,
                "semantic_class": item.semantic_class,
            }
            for item in PRODUCT_NAVIGATION
        ],
        "product_spine": list(PRODUCT_SPINE),
        "semantic_layers": list(SEMANTIC_LAYERS),
        "navigation_rows": navigation_rows,
        "stack_page_count": None if stack is None else stack.count(),
        "longitudinal_visual_tab_count": None if tabs is None else tabs.count(),
        "trajectory": {
            "release_id": presentation.release_id,
            "sample_count": len(presentation.samples),
            "media_count": len(presentation.media),
            "polyline": polyline,
            "cesium": cesium,
        },
    }
    document_properties = cesium[0].get("properties") if cesium else None
    trajectory_properties = cesium[1].get("properties") if len(cesium) > 1 else None
    acceptance = {
        "real_qt_product_workspace_created": workspace.objectName() == "tpaaB5ProductWorkspace",
        "navigation_exact_13": navigation is not None and navigation.count() == 13,
        "product_spine_visible": (
            spine is not None
            and all(token in spine.text() for token in PRODUCT_SPINE)
        ),
        "semantic_layers_visible": (
            semantic is not None
            and all(token in semantic.text() for token in SEMANTIC_LAYERS)
        ),
        "existing_surfaces_composed": stack is not None and stack.count() == 8,
        "debrief_trajectory_tabs_composed": tabs is not None and tabs.count() == 2,
        "trajectory_exact_release": presentation.release_id == release_id,
        "trajectory_2d_projection_exact": polyline == ((-117.0, 34.0), (-116.9, 34.1)),
        "cesium_relative_time_guard": (
            len(cesium) == 2
            and isinstance(document_properties, dict)
            and document_properties.get("tpaaTimeSemantics")
            == "SESSION_TIME_RELATIVE_ONLY"
            and isinstance(trajectory_properties, dict)
            and trajectory_properties.get("tpaaRelativeEpochIsNotUtcFact") is True
        ),
        "presentation_has_no_business_authority": (
            presentation.business_recompute is False
            and presentation.persistence_access is False
            and presentation.mutable_alias_resolution is False
        ),
    }
    failed = sorted(key for key, value in acceptance.items() if value is not True)
    result: dict[str, object] = {
        "schema": "TPAA_PIQB_B5_DESKTOP_REPLAY_VISUALIZATION_QUALIFICATION_V1",
        "platform": platform,
        "source_revision": source_revision,
        "status": "PASS" if not failed else "FAIL",
        "qualification_passed": not failed,
        "failed_acceptance": failed,
        "acceptance": acceptance,
        "logical_fingerprint": _canonical_hash(logical_product),
        "logical_product": logical_product,
        "scope": {
            "qt_platform": os.environ.get("QT_QPA_PLATFORM"),
            "desktop_transport_http_calls_during_construction": 0,
            "business_recompute": False,
            "persistence_access": False,
            "mutable_latest_fallback": False,
            "required_job_topology_changed": False,
        },
    }
    workspace.close()
    workspace.deleteLater()
    app.processEvents()
    return result


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--platform", required=True, choices=("linux", "windows"))
    parser.add_argument("--source-revision", required=True)
    parser.add_argument("--evidence", type=Path, required=True)
    args = parser.parse_args()

    result = qualify(platform=args.platform, source_revision=args.source_revision)
    output = args.evidence if args.evidence.is_absolute() else ROOT / args.evidence
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        json.dumps(result, sort_keys=True, indent=2) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(result, sort_keys=True))
    return 0 if result["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
