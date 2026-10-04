from __future__ import annotations

from typing import cast
from uuid import UUID

from fastapi import FastAPI
from fastapi.testclient import TestClient

from tpaa_api import register_product_v1_routes
from tpaa_application import (
    ApplicationService,
    M8P4Query,
    M8ViewerContext,
    M9ViewerContext,
)

_RELEASE_ID = "11111111-1111-4111-8111-111111111111"
_P4_ID = "22222222-2222-4222-8222-222222222222"


class _FakeProductApplication:
    def __init__(self) -> None:
        self.last_m8_viewer: M8ViewerContext | None = None

    def m1_release(self, release_id: str) -> dict[str, object]:
        return {"release_id": release_id, "status": "PUBLISHED"}

    def m8_p4(self, query: M8P4Query) -> dict[str, object]:
        self.last_m8_viewer = query.viewer
        return {
            "actor_assessment_id": query.actor_assessment_id,
            "status": "PUBLISHED",
        }


def _m8_viewer() -> M8ViewerContext:
    return M8ViewerContext(
        viewer_role="INSTRUCTOR_EVALUATOR",
        viewer_actor_id="33333333-3333-4333-8333-333333333333",
        scope_match=True,
        visibility_authorized=True,
    )


def _m9_viewer() -> M9ViewerContext:
    return M9ViewerContext(
        role="MODEL_REVIEWER",
        actor_id=None,
        scope_match=True,
    )


def _app(fake: _FakeProductApplication) -> FastAPI:
    app = FastAPI()
    return register_product_v1_routes(
        app,
        cast(ApplicationService, fake),
        m8_principal_resolver=lambda _request: _m8_viewer(),
        m9_principal_resolver=lambda _request: _m9_viewer(),
    )


def test_product_v1_p1_response_binds_exact_id_and_dto_authority() -> None:
    fake = _FakeProductApplication()
    with TestClient(_app(fake)) as client:
        response = client.get(f"/api/v1/products/p1/releases/{_RELEASE_ID}")

    assert response.status_code == 200
    payload = response.json()
    assert payload["api_version"] == "v1"
    assert payload["phase"] == "P1"
    assert payload["product_kind"] == "P1_SESSION_RELEASE"
    assert payload["exact_ids"] == {"release_id": _RELEASE_ID}
    assert payload["payload"]["release_id"] == _RELEASE_ID
    assert payload["authority"] == {
        "artifact_id": "CROSS_LAYER_DTO_CONTRACTS",
        "artifact_version": "UNVERSIONED_BY_AUTHORITY",
        "core_baseline": "CB-1.4.0",
        "sha256": "28f7209e40709fb4eb53ceffdfee3542e867f060c4e63605cc1ad149a8e3819a",
    }


def test_product_v1_p4_reuses_injected_domain_viewer() -> None:
    fake = _FakeProductApplication()
    with TestClient(_app(fake)) as client:
        response = client.get(f"/api/v1/products/p4/assessments/{_P4_ID}")

    assert response.status_code == 200
    assert response.json()["exact_ids"] == {"actor_assessment_id": _P4_ID}
    assert fake.last_m8_viewer == _m8_viewer()


def test_product_v1_rejects_non_uuid_and_has_no_latest_alias() -> None:
    fake = _FakeProductApplication()
    with TestClient(_app(fake)) as client:
        invalid = client.get("/api/v1/products/p1/releases/not-a-uuid")
        latest = client.get("/api/v1/products/p1/releases/latest")

    assert invalid.status_code == 422
    assert latest.status_code == 422
    assert UUID(_RELEASE_ID).version == 4
