from __future__ import annotations

from tpaa_runtime import (
    ProductAdmissionResolver,
    ProductFeatureAvailability,
    ProductOperationalStatus,
    ProductQualificationStatus,
    RuntimeProfile,
)


def _qualification() -> ProductQualificationStatus:
    resolver = ProductAdmissionResolver()
    availability = ProductFeatureAvailability(
        resolver,
        configured={
            "P1": True,
            "P2": True,
            "P3": True,
            "P4": True,
            "P5": True,
            "P6": True,
        },
    )
    return ProductQualificationStatus(
        feature_availability=availability,
        profile=RuntimeProfile.SERVICE,
        product_build_version="test-build",
    )


def test_b4_qualification_status_is_explicit_and_protected_main_bound() -> None:
    payload = _qualification().execute()

    assert payload["schema"] == "TPAA_PRODUCT_QUALIFICATION_STATUS_V1"
    assert payload["runtime_profile"] == "SERVICE"
    assert payload["db_schema_version"] == "1.9.0"
    data_plane = payload["data_compute_plane"]
    assert isinstance(data_plane, dict)
    assert data_plane == {
        "qualification": "PIQB_B3_QUALIFIED",
        "source_revision": "08e223c8137eb261b43ed7c2ca3612e22770d8ba",
        "run_number": 618,
        "actions_run_id": 37196871134,
        "required_jobs_success": 14,
        "required_jobs_total": 14,
        "protected_main": True,
    }
    capabilities = payload["capability_admission"]
    assert isinstance(capabilities, dict)
    items = capabilities["items"]
    assert isinstance(items, list)
    assert len(items) == 6
    assert {item["state"] for item in items if isinstance(item, dict)} == {
        "AVAILABLE"
    }


def test_b4_operational_status_is_structured_and_secret_safe() -> None:
    payload = ProductOperationalStatus(_qualification()).execute()

    assert payload["component"] == "tpaa-product-runtime"
    assert payload["reason_code"] == "PRODUCT_RUNTIME_STATUS"
    assert payload["runtime_profile"] == "SERVICE"
    assert payload["db_schema_version"] == "1.9.0"
    assert payload["b3_qualification"] == "PIQB_B3_QUALIFIED"
    assert payload["available_phase_count"] == 6
    assert payload["total_phase_count"] == 6
    lowered = repr(payload).lower()
    for forbidden in ("authorization", "cookie", "password", "secret", "token"):
        assert forbidden not in lowered
