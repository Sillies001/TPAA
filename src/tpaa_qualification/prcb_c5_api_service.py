"""PRCB C5 installed Service API exact-read, identity and RBAC qualification."""

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping
from typing import Any, cast

from fastapi.testclient import TestClient

from tpaa_runtime import ProductionRuntime, create_production_service_app

from .prcb_c5_api_desktop import PRCBC5DesktopApiExpectation

_SCHEMA = "TPAA_PRCB_C5_SERVICE_API_IDENTITY_V1"


def _stable_hash(value: object) -> str:
    encoded = json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
        allow_nan=False,
    ).encode("ascii")
    return hashlib.sha256(encoded).hexdigest()


def _mapping(value: object) -> Mapping[str, object]:
    if not isinstance(value, dict) or not all(isinstance(key, str) for key in value):
        raise RuntimeError("PRCB_C5_SERVICE_API_RESPONSE_INVALID")
    return cast(Mapping[str, object], value)


def _get(
    client: TestClient,
    path: str,
    *,
    bearer_token: str,
) -> tuple[int, Mapping[str, object]]:
    response = client.get(
        path,
        headers={"Authorization": f"Bearer {bearer_token}"},
    )
    return response.status_code, _mapping(response.json())


def _exact_ids(value: object) -> dict[str, str]:
    if not isinstance(value, Mapping):
        raise RuntimeError("PRCB_C5_SERVICE_EXACT_IDS_INVALID")
    result: dict[str, str] = {}
    for key, item in value.items():
        if not isinstance(key, str) or not isinstance(item, str) or not item:
            raise RuntimeError("PRCB_C5_SERVICE_EXACT_IDS_INVALID")
        result[key] = item
    return result


def verify_prcb_c5_service_api(
    runtime: ProductionRuntime,
    expected: PRCBC5DesktopApiExpectation,
    *,
    instructor_token: str,
    analyst_token: str,
) -> dict[str, object]:
    """Verify configured Service identity plus exact P1-P6 reads without fallback."""

    if runtime.service_principal_resolver is None:
        raise RuntimeError("PRCB_C5_SERVICE_IDENTITY_PROVIDER_MISSING")
    configured_roles = tuple(
        binding.role for binding in runtime.config.service_principals
    )
    if set(configured_roles) != {"INSTRUCTOR_EVALUATOR", "ANALYST"}:
        raise RuntimeError(
            f"PRCB_C5_SERVICE_ROLE_SET_INVALID:{configured_roles!r}"
        )
    if "MODEL_REVIEWER" in configured_roles:
        raise RuntimeError("PRCB_C5_SERVICE_MODEL_REVIEWER_ROLE_EXPANSION")

    app = create_production_service_app(runtime)
    response_hashes: dict[str, str] = {}
    with TestClient(app) as client:
        unauthenticated = client.get(
            f"/api/v1/products/p1/releases/{expected.p1_release_id}"
        )
        if unauthenticated.status_code != 401:
            raise RuntimeError("PRCB_C5_SERVICE_AUTHENTICATION_NOT_ENFORCED")

        rejected, _ = _get(
            client,
            f"/api/v1/products/p1/releases/{expected.p1_release_id}",
            bearer_token="prcb-c5-unknown-service-credential",
        )
        if rejected != 401:
            raise RuntimeError("PRCB_C5_SERVICE_UNKNOWN_CREDENTIAL_NOT_REJECTED")

        for slot, path, exact_ids in expected.exact_read_paths():
            token = (
                instructor_token
                if slot in {"P4_ASSESSMENT", "P5_ASSESSMENT"}
                else analyst_token
            )
            status_code, payload = _get(client, path, bearer_token=token)
            if status_code != 200:
                raise RuntimeError(
                    f"PRCB_C5_SERVICE_API_EXACT_READ_FAILED:{slot}:"
                    f"{status_code}:{payload!r}"
                )
            if payload.get("api_version") != "v1":
                raise RuntimeError(f"PRCB_C5_SERVICE_API_VERSION_MISMATCH:{slot}")
            observed = _exact_ids(payload.get("exact_ids"))
            if observed != exact_ids:
                raise RuntimeError(
                    f"PRCB_C5_SERVICE_API_EXACT_ID_MISMATCH:{slot}:"
                    f"{observed!r}:{exact_ids!r}"
                )
            response_hashes[slot] = _stable_hash(dict(payload))

        instructor_status, instructor_p4 = _get(
            client,
            f"/api/v1/products/p4/assessments/{expected.p4_revision_id}",
            bearer_token=instructor_token,
        )
        if instructor_status != 200:
            raise RuntimeError("PRCB_C5_SERVICE_INSTRUCTOR_P4_READ_FAILED")
        instructor_payload = _mapping(instructor_p4.get("payload"))
        if not isinstance(instructor_payload.get("actor_id"), str):
            raise RuntimeError("PRCB_C5_SERVICE_INSTRUCTOR_SCOPE_PROJECTION_MISSING")

        analyst_status, analyst_p4 = _get(
            client,
            f"/api/v1/products/p4/assessments/{expected.p4_revision_id}",
            bearer_token=analyst_token,
        )
        if analyst_status != 200:
            raise RuntimeError("PRCB_C5_SERVICE_ANALYST_P4_READ_FAILED")
        analyst_p4_payload = _mapping(analyst_p4.get("payload"))
        if analyst_p4_payload.get("actor_id") is not None:
            raise RuntimeError("PRCB_C5_SERVICE_ANALYST_DIRECT_IDENTITY_LEAK")

        model_status, analyst_model = _get(
            client,
            f"/api/v1/products/p6/models/{expected.p6_model_id}",
            bearer_token=analyst_token,
        )
        if model_status != 200:
            raise RuntimeError("PRCB_C5_SERVICE_ANALYST_P6_READ_FAILED")
        analyst_model_payload = _mapping(analyst_model.get("payload"))
        if "subject_id" in analyst_model_payload:
            raise RuntimeError("PRCB_C5_SERVICE_ANALYST_P6_IDENTITY_LEAK")

        latest_status, _ = _get(
            client,
            "/api/v1/products/p1/releases/latest",
            bearer_token=analyst_token,
        )
        if latest_status != 422:
            raise RuntimeError(
                f"PRCB_C5_SERVICE_LATEST_ALIAS_NOT_REJECTED:{latest_status}"
            )

    fingerprint_material: dict[str, Any] = {
        "session_id": expected.session_id,
        "exact_ids": expected.discovery_exact_ids(),
        "exact_response_sha256": response_hashes,
        "configured_roles": sorted(configured_roles),
    }
    return {
        "schema": _SCHEMA,
        "status": "PASS",
        "authentication_required": True,
        "unknown_credential_rejected": True,
        "api_exact_read_verified": True,
        "service_rbac_verified": True,
        "analyst_direct_identity_omitted": True,
        "model_reviewer_not_configured": True,
        "latest_alias_rejected": True,
        "current_latest_fallback_used": False,
        "configured_roles": sorted(configured_roles),
        "exact_response_sha256": response_hashes,
        "logical_fingerprint": _stable_hash(fingerprint_material),
    }
