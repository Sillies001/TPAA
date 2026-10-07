"""PRCB C5 installed Desktop API exact-read and discovery qualification."""

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any, cast

from fastapi.testclient import TestClient

from tpaa_application import M8ViewerContext, M9ViewerContext
from tpaa_gui.discovery import product_items, session_items, session_release_items
from tpaa_runtime import ProductionRuntime, create_production_desktop_app

_SCHEMA = "TPAA_PRCB_C5_DESKTOP_API_DISCOVERY_V1"


@dataclass(frozen=True, slots=True)
class PRCBC5DesktopApiExpectation:
    session_id: str
    p1_release_id: str
    p2_release_id: str
    p2_estimate_id: str
    p3_twin_revision_id: str
    p3_estimate_id: str
    p4_revision_id: str
    p5_revision_id: str
    p6_model_id: str
    p6_forecast_result_id: str
    p6_counterfactual_run_id: str

    def discovery_exact_ids(self) -> dict[str, str]:
        return {
            "P1_RELEASE": self.p1_release_id,
            "P2_ESTIMATE": self.p2_estimate_id,
            "P3_TWIN": self.p3_twin_revision_id,
            "P3_ESTIMATE": self.p3_estimate_id,
            "P4_ASSESSMENT": self.p4_revision_id,
            "P5_ASSESSMENT": self.p5_revision_id,
            "P6_MODEL": self.p6_model_id,
            "P6_FORECAST": self.p6_forecast_result_id,
            "P6_COUNTERFACTUAL": self.p6_counterfactual_run_id,
        }

    def exact_read_paths(self) -> tuple[tuple[str, str, dict[str, str]], ...]:
        return (
            (
                "P1_RELEASE",
                f"/api/v1/products/p1/releases/{self.p1_release_id}",
                {"release_id": self.p1_release_id},
            ),
            (
                "P2_ESTIMATE",
                (
                    "/api/v1/products/p2/releases/"
                    f"{self.p2_release_id}/estimates/{self.p2_estimate_id}"
                ),
                {
                    "p2_release_id": self.p2_release_id,
                    "estimate_id": self.p2_estimate_id,
                },
            ),
            (
                "P3_TWIN",
                f"/api/v1/products/p3/twins/{self.p3_twin_revision_id}",
                {"twin_revision_id": self.p3_twin_revision_id},
            ),
            (
                "P3_ESTIMATE",
                (
                    "/api/v1/products/p3/twins/"
                    f"{self.p3_twin_revision_id}/estimates/{self.p3_estimate_id}"
                ),
                {
                    "twin_revision_id": self.p3_twin_revision_id,
                    "estimate_id": self.p3_estimate_id,
                },
            ),
            (
                "P4_ASSESSMENT",
                f"/api/v1/products/p4/assessments/{self.p4_revision_id}",
                {"actor_assessment_id": self.p4_revision_id},
            ),
            (
                "P5_ASSESSMENT",
                f"/api/v1/products/p5/assessments/{self.p5_revision_id}",
                {"mission_assessment_id": self.p5_revision_id},
            ),
            (
                "P6_MODEL",
                f"/api/v1/products/p6/models/{self.p6_model_id}",
                {"capability_model_id": self.p6_model_id},
            ),
            (
                "P6_FORECAST",
                f"/api/v1/products/p6/forecasts/{self.p6_forecast_result_id}",
                {"forecast_result_id": self.p6_forecast_result_id},
            ),
            (
                "P6_COUNTERFACTUAL",
                (
                    "/api/v1/products/p6/counterfactuals/"
                    f"{self.p6_counterfactual_run_id}"
                ),
                {"counterfactual_run_id": self.p6_counterfactual_run_id},
            ),
        )


class _DesktopQualificationTransport:
    def __init__(self, client: TestClient, bearer_token: str) -> None:
        self._client = client
        self._bearer_token = bearer_token

    @staticmethod
    def _mapping(value: object) -> Mapping[str, object]:
        if not isinstance(value, dict) or not all(
            isinstance(key, str) for key in value
        ):
            raise RuntimeError("PRCB_C5_DESKTOP_API_RESPONSE_INVALID")
        return cast(Mapping[str, object], value)

    def product_request_json(
        self,
        method: str,
        path: str,
        *,
        body: dict[str, object] | None = None,
        headers: dict[str, str] | None = None,
    ) -> tuple[int, Mapping[str, object]]:
        request_headers = {
            "Authorization": f"Bearer {self._bearer_token}",
        }
        if headers is not None:
            request_headers.update(headers)
        response = self._client.request(
            method,
            path,
            json=body,
            headers=request_headers,
        )
        return response.status_code, self._mapping(response.json())


def _stable_hash(value: object) -> str:
    encoded = json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
        allow_nan=False,
    ).encode("ascii")
    return hashlib.sha256(encoded).hexdigest()


def _exact_id_mapping(value: object) -> dict[str, str]:
    if not isinstance(value, Mapping):
        raise RuntimeError("PRCB_C5_PRODUCT_EXACT_IDS_INVALID")
    result: dict[str, str] = {}
    for key, item in value.items():
        if not isinstance(key, str) or not isinstance(item, str) or not item:
            raise RuntimeError("PRCB_C5_PRODUCT_EXACT_IDS_INVALID")
        result[key] = item
    return result


def verify_prcb_c5_desktop_api_discovery(
    runtime: ProductionRuntime,
    expected: PRCBC5DesktopApiExpectation,
    *,
    bearer_token: str,
) -> dict[str, object]:
    """Verify authenticated exact reads plus Desktop discovery on one durable runtime."""

    m8_viewer = M8ViewerContext(
        viewer_role="INSTRUCTOR_EVALUATOR",
        viewer_actor_id=None,
        scope_match=True,
        visibility_authorized=True,
    )
    m9_viewer = M9ViewerContext(
        role="MODEL_REVIEWER",
        actor_id=None,
        scope_match=True,
    )
    app = create_production_desktop_app(
        runtime,
        bearer_token=bearer_token,
        m8_principal_resolver=lambda _request: m8_viewer,
        m9_principal_resolver=lambda _request: m9_viewer,
    )

    response_hashes: dict[str, str] = {}
    selected_exact_ids = expected.discovery_exact_ids()
    with TestClient(app) as client:
        unauthenticated = client.get(
            f"/api/v1/products/p1/releases/{expected.p1_release_id}"
        )
        if unauthenticated.status_code != 401:
            raise RuntimeError("PRCB_C5_DESKTOP_API_AUTHENTICATION_NOT_ENFORCED")

        transport = _DesktopQualificationTransport(client, bearer_token)
        for slot, path, exact_ids in expected.exact_read_paths():
            status_code, payload = transport.product_request_json("GET", path)
            if status_code != 200:
                raise RuntimeError(
                    f"PRCB_C5_API_EXACT_READ_FAILED:{slot}:{status_code}:{payload!r}"
                )
            if payload.get("api_version") != "v1":
                raise RuntimeError(f"PRCB_C5_API_VERSION_MISMATCH:{slot}")
            observed_exact = _exact_id_mapping(payload.get("exact_ids"))
            if observed_exact != exact_ids:
                raise RuntimeError(
                    f"PRCB_C5_API_EXACT_ID_MISMATCH:{slot}:"
                    f"{observed_exact!r}:{exact_ids!r}"
                )
            response_hashes[slot] = _stable_hash(dict(payload))

        latest_status, _latest_payload = transport.product_request_json(
            "GET",
            "/api/v1/products/p1/releases/latest",
        )
        if latest_status != 422:
            raise RuntimeError(
                f"PRCB_C5_LATEST_ALIAS_NOT_REJECTED:{latest_status}"
            )

        sessions = session_items(transport)
        if expected.session_id not in {
            str(item.get("session_id"))
            for item in sessions
            if isinstance(item.get("session_id"), str)
        }:
            raise RuntimeError("PRCB_C5_DESKTOP_SESSION_DISCOVERY_MISSING")

        releases = session_release_items(transport, expected.session_id)
        if expected.p1_release_id not in {
            str(item.get("release_id"))
            for item in releases
            if isinstance(item.get("release_id"), str)
        }:
            raise RuntimeError("PRCB_C5_DESKTOP_RELEASE_DISCOVERY_MISSING")

        release_status, release_payload = transport.product_request_json(
            "GET",
            f"/api/v1/discovery/sessions/{expected.session_id}/releases",
        )
        if (
            release_status != 200
            or release_payload.get("current_latest_fallback_used") is not False
        ):
            raise RuntimeError("PRCB_C5_DESKTOP_RELEASE_DISCOVERY_FALLBACK")

        discovery_counts: dict[str, int] = {}
        for kind, exact_id in selected_exact_ids.items():
            items = product_items(transport, kind)
            discovery_counts[kind] = len(items)
            if exact_id not in {
                str(item.get("exact_id"))
                for item in items
                if isinstance(item.get("exact_id"), str)
            }:
                raise RuntimeError(
                    f"PRCB_C5_DESKTOP_PRODUCT_DISCOVERY_MISSING:{kind}:{exact_id}"
                )
            discovery_status, discovery_payload = transport.product_request_json(
                "GET",
                f"/api/v1/discovery/products/{kind}",
            )
            if (
                discovery_status != 200
                or discovery_payload.get("current_latest_fallback_used") is not False
            ):
                raise RuntimeError(
                    f"PRCB_C5_DESKTOP_PRODUCT_DISCOVERY_FALLBACK:{kind}"
                )

    fingerprint_material: dict[str, Any] = {
        "session_id": expected.session_id,
        "selected_exact_ids": selected_exact_ids,
        "exact_response_sha256": response_hashes,
    }
    return {
        "schema": _SCHEMA,
        "status": "PASS",
        "authentication_required": True,
        "api_exact_read_verified": True,
        "desktop_discovery_verified": True,
        "latest_alias_rejected": True,
        "current_latest_fallback_used": False,
        "session_id": expected.session_id,
        "p1_release_id": expected.p1_release_id,
        "selected_exact_ids": selected_exact_ids,
        "discovery_counts": discovery_counts,
        "exact_response_sha256": response_hashes,
        "logical_fingerprint": _stable_hash(fingerprint_material),
    }
