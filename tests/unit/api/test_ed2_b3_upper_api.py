from __future__ import annotations

from typing import cast

from fastapi import FastAPI
from fastapi.testclient import TestClient

from tpaa_api import register_ed2_upper_routes
from tpaa_application import ApplicationService

_SNAPSHOT = "11111111-1111-4111-8111-111111111111"


class _FakeApplication:
    def ed2_upper_list(self, kind: str) -> dict[str, object]:
        return {
            "schema": "TPAA_ED2_UPPER_PRODUCT_INDEX_V1",
            "kind": kind.upper(),
            "items": [{"snapshot_id": _SNAPSHOT}],
            "current_latest_fallback_used": False,
        }

    def ed2_upper_exact(
        self,
        *,
        snapshot_id: str,
        expected_kind: str | None = None,
    ) -> dict[str, object]:
        return {
            "schema": "TPAA_ED2_UPPER_PRODUCT_PROJECTION_V1",
            "snapshot_id": snapshot_id,
            "kind": expected_kind,
            "frozen": True,
            "mutable_alias_resolution": False,
        }


def _app() -> FastAPI:
    app = FastAPI()
    return register_ed2_upper_routes(
        app,
        cast(ApplicationService, _FakeApplication()),
    )


def test_ed2_b3_upper_api_is_exact_id_and_has_no_latest_alias() -> None:
    with TestClient(_app()) as client:
        index = client.get("/api/v1/upper/MEDIA_DEBRIEF")
        exact = client.get(f"/api/v1/upper/MEDIA_DEBRIEF/{_SNAPSHOT}")
        latest = client.get("/api/v1/upper/MEDIA_DEBRIEF/latest")

    assert index.status_code == 200
    assert index.json()["current_latest_fallback_used"] is False
    assert exact.status_code == 200
    assert exact.json()["snapshot_id"] == _SNAPSHOT
    assert latest.status_code == 422
