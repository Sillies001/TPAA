"""PRCB C4 immutable DB 1.9 product discovery projections."""

from __future__ import annotations

import json
from datetime import date, datetime
from typing import Final

from .durable_repositories import RuntimeUnitOfWorkFactory

_SCHEMA = "TPAA_PRODUCT_DISCOVERY_V1"

_PRODUCT_SPECS: Final[dict[str, tuple[str, str, tuple[str, ...]]]] = {
    "P1_RELEASE": (
        "registry.analysis_release",
        "release_id",
        (
            "release_id",
            "session_id",
            "scope_type",
            "scope_key",
            "release_no",
            "status",
            "parent_release_id",
            "published_at",
        ),
    ),
    "M4_RELEASE": (
        "registry.analysis_release",
        "release_id",
        (
            "release_id",
            "session_id",
            "scope_type",
            "scope_key",
            "release_no",
            "status",
            "parent_release_id",
            "published_at",
        ),
    ),
    "P2_ESTIMATE": (
        "capability.adjusted_capability_estimate",
        "estimate_id",
        (
            "estimate_id",
            "source_observation_id",
            "aircraft_id",
            "capability_type",
            "status",
            "created_at",
        ),
    ),
    "P3_TWIN": (
        "capability.aircraft_twin_revision",
        "twin_revision_id",
        (
            "twin_revision_id",
            "aircraft_id",
            "revision_no",
            "status",
            "published_at",
        ),
    ),
    "P3_ESTIMATE": (
        "capability.intrinsic_capability_estimate",
        "estimate_id",
        (
            "estimate_id",
            "twin_revision_id",
            "capability_type",
            "validity_domain_status",
            "created_at",
        ),
    ),
    "P4_ASSESSMENT": (
        "assessment.actor_assessment",
        "actor_assessment_id",
        (
            "actor_assessment_id",
            "session_id",
            "actor_id",
            "status",
            "created_at",
        ),
    ),
    "P5_ASSESSMENT": (
        "assessment.mission_assessment",
        "mission_assessment_id",
        (
            "mission_assessment_id",
            "session_id",
            "team_id",
            "status",
            "created_at",
        ),
    ),
    "P6_MODEL": (
        "capability.capability_model",
        "capability_model_id",
        (
            "capability_model_id",
            "subject_id",
            "capability_type",
            "status",
            "published_at",
        ),
    ),
    "P6_FORECAST": (
        "intelligence.forecast_result",
        "forecast_result_id",
        (
            "forecast_result_id",
            "forecast_run_id",
            "target_code",
            "status",
        ),
    ),
    "P6_COUNTERFACTUAL": (
        "intelligence.counterfactual_run",
        "counterfactual_run_id",
        (
            "counterfactual_run_id",
            "scenario_definition_id",
            "status",
            "created_at",
        ),
    ),
    "P6_RECOMMENDATION": (
        "intelligence.training_recommendation",
        "recommendation_id",
        (
            "recommendation_id",
            "subject_id",
            "status",
            "approval_state",
            "created_at",
        ),
    ),
}


def _strings(value: object) -> list[str]:
    if isinstance(value, list):
        if not all(isinstance(item, str) for item in value):
            raise ValueError("discovery string-array contains non-text item")
        return list(value)
    if isinstance(value, tuple):
        if not all(isinstance(item, str) for item in value):
            raise ValueError("discovery string-array contains non-text item")
        return list(value)
    if isinstance(value, str):
        parsed = json.loads(value)
        if not isinstance(parsed, list) or not all(
            isinstance(item, str) for item in parsed
        ):
            raise ValueError("discovery string-array JSON is invalid")
        return list(parsed)
    raise ValueError("discovery string-array is invalid")


def _safe(value: object) -> object:
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    return str(value)


class DurableProductDiscovery:
    """Read-only navigation index; exact product repositories remain authoritative."""

    def __init__(self, read_uow_factory: RuntimeUnitOfWorkFactory) -> None:
        self._read_uow_factory = read_uow_factory

    def sessions(self) -> dict[str, object]:
        with self._read_uow_factory() as uow:
            rows = uow.canonical_rows.many(
                "registry.training_session",
                where={},
                columns=(
                    "session_id",
                    "session_code",
                    "session_type",
                    "start_session_time_us",
                    "end_session_time_us",
                    "data_status",
                ),
                order_by=("start_session_time_us", "session_id"),
            )
            uow.commit()
        return {
            "schema": _SCHEMA,
            "entity": "SESSION",
            "items": [
                {key: _safe(value) for key, value in row.items()}
                for row in rows
            ],
        }

    def releases(self, session_id: str) -> dict[str, object]:
        if not session_id.strip():
            raise ValueError("session_id must be non-empty")
        with self._read_uow_factory() as uow:
            raw_rows = uow.canonical_rows.many(
                "registry.analysis_release",
                where={
                    "session_id": session_id,
                    "scope_type": "SESSION",
                },
                columns=(
                    "release_id",
                    "session_id",
                    "scope_type",
                    "scope_key",
                    "release_no",
                    "status",
                    "parent_release_id",
                    "manifest_hash",
                    "created_at",
                    "published_at",
                ),
                order_by=("release_no", "release_id"),
            )
            rows = tuple(
                row
                for row in raw_rows
                if str(row["scope_key"]) == session_id
            )
            uow.commit()
        return {
            "schema": _SCHEMA,
            "entity": "RELEASE",
            "session_id": session_id,
            "current_latest_fallback_used": False,
            "items": [
                {key: _safe(value) for key, value in row.items()}
                for row in rows
            ],
        }

    def products(self, kind: str) -> dict[str, object]:
        normalized = kind.strip().upper()
        try:
            table, id_column, columns = _PRODUCT_SPECS[normalized]
        except KeyError as exc:
            raise ValueError(
                f"unsupported discovery product kind: {kind}"
            ) from exc
        with self._read_uow_factory() as uow:
            rows = uow.canonical_rows.many(
                table,
                where=(
                    {"scope_type": "LONGITUDINAL"}
                    if normalized == "M4_RELEASE"
                    else {}
                ),
                columns=columns,
                order_by=(id_column,),
            )
            items: list[dict[str, object]] = []
            for row in rows:
                if normalized == "P1_RELEASE" and (
                    row.get("scope_type") != "SESSION"
                    or row.get("scope_key") != row.get("session_id")
                ):
                    continue
                metadata = {
                    key: _safe(value)
                    for key, value in row.items()
                    if key != id_column
                }
                if normalized == "P2_ESTIMATE":
                    revision = uow.canonical_rows.one(
                        "capability.adjusted_capability_estimate_revision",
                        where={"estimate_id": row[id_column]},
                        columns=("p2_release_id",),
                    )
                    observation = uow.canonical_rows.one(
                        "metric.capability_observation",
                        where={"observation_id": row["source_observation_id"]},
                        columns=("release_id", "session_id"),
                    )
                    if revision is not None:
                        metadata["p2_release_id"] = _safe(
                            revision["p2_release_id"]
                        )
                    if observation is not None:
                        metadata["source_release_id"] = _safe(
                            observation["release_id"]
                        )
                        metadata["session_id"] = _safe(
                            observation["session_id"]
                        )
                elif normalized == "P6_RECOMMENDATION":
                    revision = uow.canonical_rows.one(
                        "intelligence.training_recommendation_revision",
                        where={"recommendation_id": row[id_column]},
                        columns=(
                            "source_forecast_result_ids",
                            "source_counterfactual_run_ids",
                        ),
                    )
                    if revision is not None:
                        metadata["source_forecast_result_ids"] = _strings(
                            revision["source_forecast_result_ids"]
                        )
                        metadata["source_counterfactual_run_ids"] = _strings(
                            revision["source_counterfactual_run_ids"]
                        )
                items.append(
                    {
                        "kind": normalized,
                        "exact_id": str(row[id_column]),
                        "metadata": metadata,
                    }
                )
            uow.commit()
        return {
            "schema": _SCHEMA,
            "entity": "PRODUCT",
            "kind": normalized,
            "current_latest_fallback_used": False,
            "items": items,
        }


    def release_presentation(self, release_id: str) -> dict[str, object]:
        if not release_id.strip():
            raise ValueError("release_id must be non-empty")
        with self._read_uow_factory() as uow:
            membership = uow.publication.logical_membership(release_id)
            uow.commit()
        evidence_raw = membership.get("evidence_sets")
        if not isinstance(evidence_raw, list):
            raise RuntimeError("release evidence projection invalid")
        source_series: list[dict[str, object]] = []
        geodetic_available = False
        for raw in evidence_raw:
            if not isinstance(raw, dict):
                raise RuntimeError("release evidence entry invalid")
            locator = raw.get("series_locator")
            if not isinstance(locator, dict):
                continue
            fields = locator.get("fields")
            if isinstance(fields, list) and {
                "latitude_deg",
                "longitude_deg",
            }.issubset({str(item) for item in fields}):
                geodetic_available = True
            source_series.append(
                {
                    "evidence_set_id": raw.get("evidence_set_id"),
                    "canonical_dataset_id": locator.get(
                        "canonical_dataset_id"
                    ),
                    "canonical_dataset_uri": locator.get(
                        "canonical_dataset_uri"
                    ),
                    "canonical_logical_content_hash": locator.get(
                        "canonical_logical_content_hash"
                    ),
                }
            )
        return {
            "schema": "TPAA_RELEASE_PRESENTATION_BINDING_V1",
            "release_id": release_id,
            "available": False,
            "reason_code": (
                "GEODETIC_PRESENTATION_READER_NOT_YET_BOUND"
                if geodetic_available
                else "GEODETIC_SERIES_NOT_PRESENT"
            ),
            "presentation": None,
            "source_series": source_series,
            "media": [],
            "current_latest_fallback_used": False,
            "business_recompute_performed": False,
        }
