from __future__ import annotations

import json
import os
from pathlib import Path

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from tpaa_gui.shell_state import ApplicationShellState
from tpaa_gui.w5_pages import (
    create_p01_page,
    create_p02_page,
    create_p03_page,
    create_p12_page,
    create_p13_page,
)
from tpaa_gui.w5_projection import (
    W5ProjectionError,
    build_session_overview,
    observation_quality_rows,
    status_meaning,
    verify_exact_replay,
)

RELEASE = "81000000-0000-4000-8000-000000000001"
SESSION = "81000000-0000-4000-8000-000000000002"
CONTEXT = "81000000-0000-4000-8000-000000000003"
EPISODE = "81000000-0000-4000-8000-000000000004"
STAGE = "81000000-0000-4000-8000-000000000005"
METRIC = "81000000-0000-4000-8000-000000000006"
OBSERVATION = "81000000-0000-4000-8000-000000000007"


def _bundle() -> dict[str, dict[str, object]]:
    return {
        "release": {
            "release_id": RELEASE,
            "session_id": SESSION,
            "context_id": CONTEXT,
            "context_version": "CTX-1",
            "status": "PUBLISHED",
            "release_no": 1,
            "catalog_version": "1.14.0",
            "catalog_hash": "a" * 64,
            "manifest_hash": "b" * 64,
        },
        "context": {
            "context_id": CONTEXT,
            "session_id": SESSION,
            "context_version": "CTX-1",
            "revision_no": 1,
            "metric_profile_version": "PROFILE-1",
            "status": "ACTIVE",
        },
        "topology": {
            "release_id": RELEASE,
            "session": {
                "session_id": SESSION,
                "start_session_time_us": "0",
                "end_session_time_us": "2000000",
            },
            "episode": {"episode_id": EPISODE, "session_id": SESSION},
            "stages": [
                {
                    "stage_id": STAGE,
                    "episode_id": EPISODE,
                    "stage_type": "EXECUTION",
                    "stage_order": 1,
                    "start_session_time_us": "0",
                    "end_session_time_us": "2000000",
                    "stage_status": "VALID",
                    "coverage": 0.95,
                    "confidence": 0.9,
                }
            ],
        },
        "metrics": {
            "release_id": RELEASE,
            "items": [
                {
                    "metric_instance_id": METRIC,
                    "metric_code": "P1-AIR-001",
                    "definition_hash": "c" * 64,
                    "subject_type": "AIRCRAFT",
                    "observation_lane": "AIRCRAFT_PERFORMANCE",
                    "status": "VALID",
                    "unit": "deg/s",
                    "value_kind": "NUMERIC",
                },
                {
                    "metric_instance_id": "81000000-0000-4000-8000-000000000008",
                    "metric_code": "P1-SNS-001",
                    "definition_hash": "d" * 64,
                    "subject_type": "MISSION_SYSTEM_INSTANCE",
                    "observation_lane": "MISSION_SYSTEM_PERFORMANCE",
                    "status": "INSUFFICIENT_DATA",
                    "unit": "m",
                    "value_kind": "NUMERIC",
                },
                {
                    "metric_instance_id": "81000000-0000-4000-8000-000000000009",
                    "metric_code": "P1-QA-REFERENCE-UNCERTAINTY",
                    "definition_hash": "e" * 64,
                    "subject_type": "AIRCRAFT",
                    "observation_lane": "REFERENCE_QUALITY",
                    "status": "N_A",
                    "unit": "m",
                    "value_kind": "STRUCTURED",
                },
            ],
        },
        "observations": {
            "release_id": RELEASE,
            "items": [
                {
                    "observation_id": OBSERVATION,
                    "observed_metric_instance_id": METRIC,
                    "metric_code": "P1-AIR-001",
                    "aircraft_id": "aircraft-1",
                    "coverage": 0.95,
                    "confidence": 0.9,
                    "eligibility_status": "REVIEW_REQUIRED",
                    "exclusion_reason_code": "PILOT_TAG_REVIEW",
                    "evidence_set_id": "evidence-1",
                }
            ],
        },
        "world": {
            "release_id": RELEASE,
            "world_products": [
                {
                    "world_product_id": "world-1",
                    "world_kind": "MACHINE",
                    "status": "READY",
                    "coverage": 0.9,
                    "confidence": 0.8,
                    "reason_codes": [],
                }
            ],
            "world_relations": [],
            "tpaa_m_chains": [],
        },
    }


class _Transport:
    def __init__(self) -> None:
        self.bundle = _bundle()
        self.staged: dict[str, object] | None = None

    def product_request_json(self, method: str, path: str, **_kwargs: object):
        assert method == "GET"
        if path == "/api/v1/discovery/sessions":
            return 200, {
                "items": [
                    {
                        "session_id": SESSION,
                        "session_code": "W5-001",
                        "session_type": "SIM",
                        "data_status": "READY",
                    }
                ]
            }
        if path == f"/api/v1/discovery/sessions/{SESSION}/releases":
            return 200, {"release_id": RELEASE, "items": [self.bundle["release"]]}
        if path == "/api/v1/discovery/products/P1_RELEASE":
            return 200, {
                "items": [
                    {
                        "exact_id": RELEASE,
                        "metadata": {
                            "session_id": SESSION,
                            "release_no": 1,
                            "status": "PUBLISHED",
                        },
                    }
                ]
            }
        if path.startswith("/api/v1/discovery/products/"):
            return 200, {"items": []}
        if path == f"/api/v1/discovery/releases/{RELEASE}/presentation":
            return 200, {
                "release_id": RELEASE,
                "available": True,
                "presentation": {
                    "schema": "TPAA_TRAJECTORY_PRESENTATION_V1",
                    "release_id": RELEASE,
                    "time_semantics": "SESSION_TIME",
                    "business_recompute": False,
                    "persistence_access": False,
                    "mutable_alias_resolution": False,
                    "samples": [
                        {
                            "session_time_us": 0,
                            "latitude_deg": 34.0,
                            "longitude_deg": -117.0,
                            "altitude_m": 1000.0,
                            "source_release_id": RELEASE,
                            "evidence_ref": "evidence-1",
                        },
                        {
                            "session_time_us": 1000000,
                            "latitude_deg": 34.1,
                            "longitude_deg": -116.9,
                            "altitude_m": 1100.0,
                            "source_release_id": RELEASE,
                            "evidence_ref": "evidence-1",
                        },
                    ],
                    "media": [],
                },
            }
        raise AssertionError(path)

    def m1_request_json(self, method: str, path: str, **_kwargs: object):
        base = f"/m1/releases/{RELEASE}"
        if path == base:
            return 200, self.bundle["release"]
        if path == f"{base}/context":
            return 200, self.bundle["context"]
        if path == f"{base}/topology":
            return 200, self.bundle["topology"]
        if path == f"{base}/metrics":
            return 200, self.bundle["metrics"]
        if path == f"{base}/observations":
            return 200, self.bundle["observations"]
        if path == f"{base}/world-graph":
            return 200, self.bundle["world"]
        if path == f"{base}/replay" and method == "POST":
            return 200, {
                "release_id": RELEASE,
                "status": "EXACT_REPLAY",
                "manifest_hash": "b" * 64,
                "current_latest_fallback_used": False,
            }
        if path.startswith(f"{base}/series?"):
            return 200, {
                "release_id": RELEASE,
                "returned": 2,
                "rows": [
                    {"session_time_us": "0", "nz_g": 1.0},
                    {"session_time_us": "1000000", "nz_g": 1.2},
                ],
            }
        if path == f"{base}/metrics/P1-AIR-001":
            return 200, {
                "release_id": RELEASE,
                "metric_instance_id": METRIC,
                "metric_code": "P1-AIR-001",
                "status": "VALID",
            }
        if path == f"{base}/metrics/P1-AIR-001/evidence":
            return 200, {
                "release_id": RELEASE,
                "metric_instance_id": METRIC,
                "metric_code": "P1-AIR-001",
                "evidence_set_id": "evidence-1",
            }
        raise AssertionError((method, path))

    def source_request_bytes(self, path: str, *, data: bytes, content_type: str):
        assert path.endswith("/p1-request/stage")
        assert content_type == "application/json"
        raw = json.loads(data)
        self.staged = {**raw, "source_documents": []}
        return 201, {
            "status": "STAGED",
            "source_document_count": 1,
            "source_families": ["FLIGHT"],
            "payload": self.staged,
        }

    def job_request_json(self, method: str, path: str, **_kwargs: object):
        if method == "POST" and path == "/jobs":
            return 202, {"job_id": "job-w5", "status": "SUCCEEDED"}
        if method == "GET" and path == "/jobs/job-w5":
            return 200, {"job_id": "job-w5", "status": "SUCCEEDED"}
        raise AssertionError((method, path))

    def security_request_json(self, method: str, path: str):
        assert (method, path) == ("GET", "/security/approvals")
        return 200, {"items": []}

    def runtime_request_json(self, method: str, path: str):
        assert method == "GET"
        return 200, {"status": "PASS", "path": path}


def test_w5_status_semantics_and_exact_release_binding() -> None:
    assert status_meaning("N_A").kind == "not_applicable"
    assert status_meaning(None).kind == "unknown"
    assert status_meaning("FAILED").kind == "failure"
    assert status_meaning("REVIEW_REQUIRED").kind == "review"
    projection = build_session_overview(
        release=_bundle()["release"],
        context=_bundle()["context"],
        topology=_bundle()["topology"],
        metrics_payload=_bundle()["metrics"],
        observations_payload=_bundle()["observations"],
        world_graph=_bundle()["world"],
    )
    assert len(projection.aircraft_metrics) == 1
    assert len(projection.mission_system_metrics) == 1
    assert len(projection.reference_quality_metrics) == 1
    assert observation_quality_rows(projection)[0]["eligibility"] == "REVIEW_REQUIRED"
    assert verify_exact_replay(
        {"release_id": RELEASE, "status": "EXACT_REPLAY"}, RELEASE
    ) == "EXACT_REPLAY"
    with pytest.raises(W5ProjectionError, match="RELEASE_BINDING_DRIFT"):
        verify_exact_replay({"release_id": "latest", "status": "PASS"}, RELEASE)


def test_w5_five_pages_complete_linked_workflows(tmp_path: Path) -> None:
    pytest.importorskip("PySide6")
    from PySide6 import QtCore, QtWidgets

    app = QtWidgets.QApplication.instance() or QtWidgets.QApplication(["w5-test"])
    transport = _Transport()
    state = ApplicationShellState()
    manifest = tmp_path / "p1-request.json"
    manifest.write_text(
        json.dumps(
            {
                "schema": "TPAA_ED2_B1_FULL_P1_REQUEST_CONTRACT_V1",
                "source_documents": [{"source_json": "{}"}],
            }
        ),
        encoding="utf-8",
    )

    p01 = create_p01_page(QtCore, QtWidgets, None, transport=transport, state=state)
    p01.findChild(QtWidgets.QLineEdit, "tpaaP01ManifestPath").setText(str(manifest))
    p01._tpaa_stage_manifest()
    assert p01.findChild(QtWidgets.QPushButton, "tpaaP01PublishRelease").isEnabled()
    p01._tpaa_publish_release()
    assert p01.findChild(QtWidgets.QLineEdit, "tpaaP01JobId").text() == "job-w5"

    p02 = create_p02_page(QtCore, QtWidgets, None, transport=transport, state=state)
    p02._tpaa_refresh_releases()
    p02._tpaa_load_overview()
    assert state.selection.release_id == RELEASE
    assert p02.findChild(QtWidgets.QTabWidget, "tpaaP02SubjectLanes").count() == 3

    p03 = create_p03_page(QtCore, QtWidgets, None, transport=transport, state=state)
    p03._tpaa_refresh_releases()
    p03._tpaa_load_replay()
    metric_table = p03.findChild(QtWidgets.QTableWidget, "tpaaP03MetricTable")
    metric_table.cellClicked.emit(0, 0)
    assert state.selection.metric_instance_id == METRIC
    assert state.selection.observation_id == OBSERVATION
    assert "evidence-1" in p03.findChild(
        QtWidgets.QPlainTextEdit, "tpaaP03EvidenceDetail"
    ).toPlainText()

    p12 = create_p12_page(QtCore, QtWidgets, None, transport=transport, state=state)
    p12._tpaa_refresh_releases()
    p12._tpaa_load_quality()
    assert p12.findChild(QtWidgets.QTableWidget, "tpaaP12ObservationEligibility").rowCount() == 1

    p13 = create_p13_page(QtCore, QtWidgets, None, transport=transport, state=state)
    p13._tpaa_refresh_governance()
    p13._tpaa_load_governance()
    assert "current_latest_fallback_used" in p13.findChild(
        QtWidgets.QPlainTextEdit, "tpaaP13ReleasePanel"
    ).toPlainText()
    for widget in (p01, p02, p03, p12, p13):
        widget.close()
    app.processEvents()
