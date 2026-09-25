from __future__ import annotations

from pathlib import Path
from typing import Never

from fastapi.testclient import TestClient

from tpaa_api import create_desktop_app
from tpaa_application import ApplicationService, M1PublicationService, build_trusted_runtime_status_use_case
from tpaa_application.m1_repository import InMemorySessionPublicationRepository

ROOT = Path(__file__).resolve().parents[2]
WORKSPACE = ROOT / "src" / "tpaa_gui" / "m1_workspace.py"


class _UnusedStorage:
    def execute(self) -> Never:
        raise AssertionError("storage status is not used by this Desktop contract")


def _application() -> ApplicationService:
    publication = M1PublicationService(
        fixture_root=ROOT / "tests" / "fixtures" / "m1",
        authority_root=ROOT / "baseline" / "CB-1.4.0" / "canonical",
        repository=InMemorySessionPublicationRepository(),
    )
    return ApplicationService(
        get_storage_baseline_status=_UnusedStorage(),
        get_runtime_baseline_status=build_trusted_runtime_status_use_case(
            product_build_version="0.0.0"
        ),
        m1_publication=publication,
    )


def test_desktop_m1_routes_reuse_bearer_origin_and_path_security_boundary() -> None:
    app = create_desktop_app(application=_application(), bearer_token="desktop-test")
    with TestClient(app) as client:
        unauthorized = client.post(
            "/m1/commands/import-session",
            json={"fixture_id": "BF_M1_NOMINAL_V1"},
            headers={"Idempotency-Key": "import-1"},
        )
        origin = client.post(
            "/m1/commands/import-session",
            json={"fixture_id": "BF_M1_NOMINAL_V1"},
            headers={
                "Authorization": "Bearer desktop-test",
                "Idempotency-Key": "import-1",
                "Origin": "https://example.invalid",
            },
        )
        imported = client.post(
            "/m1/commands/import-session",
            json={"fixture_id": "BF_M1_NOMINAL_V1"},
            headers={
                "Authorization": "Bearer desktop-test",
                "Idempotency-Key": "import-1",
            },
        )
        unrelated = client.get(
            "/jobs",
            headers={"Authorization": "Bearer desktop-test"},
        )

    assert unauthorized.status_code == 401
    assert origin.status_code == 403
    assert imported.status_code == 200
    assert imported.json()["session_id"] == "11111111-1111-4111-8111-111111111111"
    assert unrelated.status_code == 404
    assert unrelated.json() == {"detail": "PATH_NOT_ALLOWED"}


def test_workspace_is_projection_only_and_requires_explicit_publication_bindings() -> None:
    source = WORKSPACE.read_text(encoding="utf-8")
    assert "tpaa_metric" not in source
    assert "tpaa_world" not in source
    assert "compute_representative_metrics" not in source
    assert "project_minimal_p1_world" not in source
    assert "Explicit upstream/test binding required" in source
    for field in (
        "tpaaM1AircraftModelId",
        "tpaaM1AircraftInstanceId",
        "tpaaM1SubjectEntityId",
        "tpaaM1CapabilityDimension",
        "tpaaM1CapabilityType",
    ):
        assert field in source


def test_workspace_has_stable_objects_for_all_batch_3_gui_rows() -> None:
    source = WORKSPACE.read_text(encoding="utf-8")
    for name in (
        "tpaaM1SessionBrowser",
        "tpaaM1ContextHeader",
        "tpaaM1TimelineSlider",
        "tpaaM1StageLane",
        "tpaaM1MetricList",
        "tpaaM1MetricDetail",
        "tpaaM1EvidenceDetail",
        "tpaaM1StateNA",
        "tpaaM1StateINSUFFICIENT",
        "tpaaM1StateINVALID",
        "tpaaM1StateSYSTEMERROR",
    ):
        assert name in source
