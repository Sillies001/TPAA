"""M9 Batch 2 exact P6 model/forecast longitudinal replay and validation lineage."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING
from uuid import UUID, uuid5

from tpaa_context.p6_governance import (
    P6AuthorityPolicy,
    P6GovernanceError,
    canonical_hash,
    exact_uuid,
    utc,
)

if TYPE_CHECKING:
    from tpaa_capability.p3_twin import P3CapabilityEstimate
    from tpaa_capability.p6_forecast import (
        P6ForecastRevision,
        P6ModelRevision,
    )

_VALIDATION_NAMESPACE = UUID("a5727e4f-084a-54e0-9734-76fca77f67b7")


@dataclass(frozen=True, slots=True)
class P6ProjectionValidation:
    validation_id: str
    forecast_result_id: str
    forecast_logical_content_hash: str
    observed_p3_estimate_id: str
    target_session_order: int
    projected_value: float
    observed_value: float
    absolute_error: float
    validated_at_utc: str
    data_hash: str


class InMemoryP6ReplayRepository:
    """Exact-ID immutable replay registry; no current/latest/default resolution."""

    def __init__(self) -> None:
        self._models: dict[str, P6ModelRevision] = {}
        self._forecasts: dict[str, P6ForecastRevision] = {}
        self._validations: dict[str, P6ProjectionValidation] = {}

    def add_model(self, model: P6ModelRevision) -> P6ModelRevision:
        existing = self._models.get(model.capability_model_id)
        if existing is not None and existing != model:
            raise P6GovernanceError(
                "FAIL_CLOSED_P6_EXACT_IDENTITY_REQUIRED",
                "model identity collision",
            )
        self._models[model.capability_model_id] = model
        return model

    def add_forecast(self, forecast: P6ForecastRevision) -> P6ForecastRevision:
        if forecast.model_revision_id not in self._models:
            raise P6GovernanceError(
                "FAIL_CLOSED_P6_MODEL_PROFILE_REQUIRED",
                "forecast model revision is not registered by exact ID",
            )
        existing = self._forecasts.get(forecast.forecast_result_id)
        if existing is not None and existing != forecast:
            raise P6GovernanceError(
                "FAIL_CLOSED_P6_EXACT_IDENTITY_REQUIRED",
                "forecast identity collision",
            )
        self._forecasts[forecast.forecast_result_id] = forecast
        return forecast

    def replay_model(
        self,
        capability_model_id: str,
        *,
        as_of_utc: str,
        policy: P6AuthorityPolicy | None = None,
    ) -> P6ModelRevision:
        p = policy or P6AuthorityPolicy.from_canonical()
        exact_uuid(
            capability_model_id,
            field="capability_model_id",
            policy=p,
        )
        model = self._models.get(capability_model_id)
        if model is None:
            raise P6GovernanceError(
                "FAIL_CLOSED_P6_EXACT_IDENTITY_REQUIRED",
                capability_model_id,
            )
        if utc(model.trained_at, field="model.trained_at") > utc(
            as_of_utc,
            field="as_of_utc",
        ):
            raise P6GovernanceError(
                "FAIL_CLOSED_P6_FUTURE_INFORMATION",
                capability_model_id,
            )
        return model

    def replay_forecast(
        self,
        forecast_result_id: str,
        *,
        as_of_utc: str,
        policy: P6AuthorityPolicy | None = None,
    ) -> P6ForecastRevision:
        p = policy or P6AuthorityPolicy.from_canonical()
        exact_uuid(
            forecast_result_id,
            field="forecast_result_id",
            policy=p,
        )
        forecast = self._forecasts.get(forecast_result_id)
        if forecast is None:
            raise P6GovernanceError(
                "FAIL_CLOSED_P6_EXACT_IDENTITY_REQUIRED",
                forecast_result_id,
            )
        if utc(forecast.published_at_utc, field="forecast.published_at_utc") > utc(
            as_of_utc,
            field="as_of_utc",
        ):
            raise P6GovernanceError(
                "FAIL_CLOSED_P6_FUTURE_INFORMATION",
                forecast_result_id,
            )
        return forecast

    def validate_observed_outcome(
        self,
        forecast_result_id: str,
        observed: P3CapabilityEstimate,
        *,
        validated_at_utc: str,
        policy: P6AuthorityPolicy | None = None,
    ) -> P6ProjectionValidation:
        p = policy or P6AuthorityPolicy.from_canonical()
        forecast = self.replay_forecast(
            forecast_result_id,
            as_of_utc=validated_at_utc,
            policy=p,
        )
        if (
            forecast.applicability_status != "APPLICABLE"
            or forecast.target_session_order is None
        ):
            raise P6GovernanceError(
                "FAIL_CLOSED_P6_APPLICABILITY_REQUIRED",
                forecast.applicability_status,
            )
        point = forecast.distribution.get("point")
        if isinstance(point, bool) or not isinstance(point, (int, float)):
            raise P6GovernanceError(
                "FAIL_CLOSED_P6_APPLICABILITY_REQUIRED",
                "forecast has no numeric projection",
            )
        condition = dict(observed.condition_point)
        session_order = condition.get("session_order")
        if (
            isinstance(session_order, bool)
            or not isinstance(session_order, int)
            or session_order != forecast.target_session_order
        ):
            raise P6GovernanceError(
                "FAIL_CLOSED_P6_EXACT_IDENTITY_REQUIRED",
                "observed outcome target session mismatch",
            )
        exact_uuid(
            observed.estimate_id,
            field="observed.estimate_id",
            policy=p,
        )
        if (
            observed.validity_domain_status != "IN_DOMAIN"
            or observed.value is None
        ):
            raise P6GovernanceError(
                "FAIL_CLOSED_P6_APPLICABILITY_REQUIRED",
                "observed outcome is not an in-domain numeric P3 estimate",
            )
        model = self._models[forecast.model_revision_id]
        reference_id = condition.get("reference_condition_id")
        if (
            observed.capability_type != model.capability_type
            or observed.unit != model.validity_domain.get("unit")
            or reference_id != model.validity_domain.get("reference_condition_id")
        ):
            raise P6GovernanceError(
                "FAIL_CLOSED_P6_APPLICABILITY_REQUIRED",
                "observed outcome domain does not match forecast model",
            )
        if utc(observed.created_at, field="observed.created_at") > utc(
            validated_at_utc,
            field="validated_at_utc",
        ):
            raise P6GovernanceError(
                "FAIL_CLOSED_P6_FUTURE_INFORMATION",
                observed.estimate_id,
            )
        projected = float(point)
        observed_value = float(observed.value)
        absolute_error = abs(projected - observed_value)
        material = {
            "forecast_result_id": forecast.forecast_result_id,
            "forecast_logical_content_hash": forecast.logical_content_hash,
            "observed_p3_estimate_id": observed.estimate_id,
            "target_session_order": session_order,
            "projected_value": projected,
            "observed_value": observed_value,
            "absolute_error": absolute_error,
            "validated_at_utc": validated_at_utc,
        }
        digest = canonical_hash(material)
        validation = P6ProjectionValidation(
            validation_id=str(uuid5(_VALIDATION_NAMESPACE, digest)),
            forecast_result_id=forecast.forecast_result_id,
            forecast_logical_content_hash=forecast.logical_content_hash,
            observed_p3_estimate_id=observed.estimate_id,
            target_session_order=session_order,
            projected_value=projected,
            observed_value=observed_value,
            absolute_error=absolute_error,
            validated_at_utc=validated_at_utc,
            data_hash=digest,
        )
        existing = self._validations.get(validation.validation_id)
        if existing is not None and existing != validation:
            raise P6GovernanceError(
                "FAIL_CLOSED_P6_EXACT_IDENTITY_REQUIRED",
                "validation identity collision",
            )
        self._validations[validation.validation_id] = validation
        return validation

    def get_validation(
        self,
        validation_id: str,
        *,
        policy: P6AuthorityPolicy | None = None,
    ) -> P6ProjectionValidation:
        p = policy or P6AuthorityPolicy.from_canonical()
        exact_uuid(validation_id, field="validation_id", policy=p)
        value = self._validations.get(validation_id)
        if value is None:
            raise P6GovernanceError(
                "FAIL_CLOSED_P6_EXACT_IDENTITY_REQUIRED",
                validation_id,
            )
        return value
