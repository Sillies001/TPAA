"""PIQB B4 product qualification and structured operational status."""

from __future__ import annotations

from dataclasses import dataclass

from tpaa_audit import structured_record

from .admission import ProductFeatureAvailability
from .config import RuntimeProfile

_B3_PROTECTED_MAIN_SHA = "08e223c8137eb261b43ed7c2ca3612e22770d8ba"
_B3_RUN_NUMBER = 618
_B3_ACTIONS_RUN_ID = 37196871134


@dataclass(frozen=True, slots=True)
class ProductQualificationStatus:
    """Machine-readable product qualification state; no CI inference at runtime."""

    feature_availability: ProductFeatureAvailability
    profile: RuntimeProfile
    product_build_version: str

    def execute(self) -> dict[str, object]:
        return {
            "schema": "TPAA_PRODUCT_QUALIFICATION_STATUS_V1",
            "runtime_profile": self.profile.value,
            "product_build_version": self.product_build_version,
            "db_schema_version": "1.9.0",
            "data_compute_plane": {
                "qualification": "PIQB_B3_QUALIFIED",
                "source_revision": _B3_PROTECTED_MAIN_SHA,
                "run_number": _B3_RUN_NUMBER,
                "actions_run_id": _B3_ACTIONS_RUN_ID,
                "required_jobs_success": 14,
                "required_jobs_total": 14,
                "protected_main": True,
            },
            "capability_admission": self.feature_availability.execute(),
        }


@dataclass(frozen=True, slots=True)
class ProductOperationalStatus:
    """Secret-safe structured runtime status built from explicit qualification state."""

    qualification: ProductQualificationStatus

    def execute(self) -> dict[str, object]:
        status = self.qualification.execute()
        availability = status["capability_admission"]
        if not isinstance(availability, dict):
            raise RuntimeError("capability admission projection invalid")
        items = availability.get("items")
        if not isinstance(items, list):
            raise RuntimeError("capability admission items invalid")
        available = sum(
            1
            for item in items
            if isinstance(item, dict) and item.get("state") == "AVAILABLE"
        )
        return structured_record(
            component="tpaa-product-runtime",
            product_version=self.qualification.product_build_version,
            reason_code="PRODUCT_RUNTIME_STATUS",
            fields={
                "runtime_profile": self.qualification.profile.value,
                "db_schema_version": "1.9.0",
                "b3_qualification": "PIQB_B3_QUALIFIED",
                "b3_protected_main": True,
                "available_phase_count": available,
                "total_phase_count": 6,
            },
        )


_PRCB_SOURCE_PROTECTED_MAIN_SHA = "0ed48a85944699e0bbac1fe76b84c88a319121c1"
_PRCB_SOURCE_RUN_NUMBER = 636
_PRCB_SOURCE_ACTIONS_RUN_ID = 37271874369


@dataclass(frozen=True, slots=True)
class PRCBQualificationStatus:
    """Truthful TPAA 1.0.1 pre-qualification state during PRCB closure."""

    feature_availability: ProductFeatureAvailability
    profile: RuntimeProfile
    product_build_version: str

    def execute(self) -> dict[str, object]:
        return {
            "schema": "TPAA_PRCB_PRODUCT_QUALIFICATION_STATUS_V1",
            "runtime_profile": self.profile.value,
            "product_build_version": self.product_build_version,
            "canonical_baseline": "CB-1.4.0",
            "db_schema_version": "1.9.0",
            "historical_release": {
                "product_version": "1.0.0",
                "qualification": "PIQB_1_0_QUALIFIED",
                "source_revision": _PRCB_SOURCE_PROTECTED_MAIN_SHA,
                "run_number": _PRCB_SOURCE_RUN_NUMBER,
                "actions_run_id": _PRCB_SOURCE_ACTIONS_RUN_ID,
                "required_jobs_success": 14,
                "required_jobs_total": 14,
                "protected_main": True,
            },
            "target_release": {
                "product_version": self.product_build_version,
                "qualification": "TPAA_1_0_1_NOT_YET_QUALIFIED",
                "formal_release_claimed": False,
            },
            "capability_admission": self.feature_availability.execute(),
        }


@dataclass(frozen=True, slots=True)
class PRCBOperationalStatus:
    """Secret-safe operational status for the not-yet-qualified PRCB runtime."""

    qualification: PRCBQualificationStatus

    def execute(self) -> dict[str, object]:
        status = self.qualification.execute()
        availability = status["capability_admission"]
        if not isinstance(availability, dict):
            raise RuntimeError("PRCB capability admission projection invalid")
        items = availability.get("items")
        if not isinstance(items, list):
            raise RuntimeError("PRCB capability admission items invalid")
        available = sum(
            1
            for item in items
            if isinstance(item, dict) and item.get("state") == "AVAILABLE"
        )
        return structured_record(
            component="tpaa-production-runtime",
            product_version=self.qualification.product_build_version,
            reason_code="PRCB_RUNTIME_STATUS",
            fields={
                "runtime_profile": self.qualification.profile.value,
                "db_schema_version": "1.9.0",
                "historical_qualification": "PIQB_1_0_QUALIFIED",
                "target_qualification": "TPAA_1_0_1_NOT_YET_QUALIFIED",
                "formal_release_claimed": False,
                "available_phase_count": available,
                "total_phase_count": 6,
            },
        )
