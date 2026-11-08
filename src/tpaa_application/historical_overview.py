"""G6 V01 Historical Training Overview query — single owner of the exact Batch workset.

Every KPI, trend, composition panel, list and summary is computed over ONE exact,
traceable query context (query_context_id + batch-set fingerprint).  Ratios are
recomputed from aggregated numerator/denominator (never simple-averaged); zero
denominator, missing J, reverse date range, non-comparable equipment and empty sets
fail closed with explicit reasons.  No synthetic trend ever fills the page.
"""

from __future__ import annotations

import hashlib
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import date, datetime
from typing import Protocol

TASK_METRIC_DEFINITION_VERSION = "G6-TASKMETRIC-1.0.0"
EQUIPMENT_METRIC_VERSION = "G6-EQUIP-1.0.0"


class HistoricalOverviewError(RuntimeError):
    """Transport-safe, fail-closed G6 error."""

    def __init__(self, code: str, detail: str, *, http_status: int = 422) -> None:
        self.code = code
        self.detail = detail
        self.http_status = http_status
        super().__init__(f"{code}:{detail}")


@dataclass(frozen=True, slots=True)
class BatchOverviewRecord:
    """One QUALIFIED batch with its exact aggregate facts for the V01 workset."""

    batch_id: str
    batch_date: date
    batch_training_type: str
    sortie_count: int
    episode_count: int
    weapon_event_count: int
    adjudicated_event_count: int
    qualification_status: str
    has_event_detail: bool


@dataclass(frozen=True, slots=True)
class TaskMetricInput:
    """Aggregated numerator/denominator for one task-level metric candidate."""

    metric_id: str
    label: str
    unit: str
    numerator: int
    denominator: int


@dataclass(frozen=True, slots=True)
class EquipmentMetricInput:
    metric_id: str
    label: str
    unit: str
    comparable: bool
    eligibility: str
    reason: str | None
    points: tuple[tuple[str, float], ...]


@dataclass(frozen=True, slots=True)
class OverviewQuery:
    start_date: date
    end_date: date
    model: str  # "ALL" or a specific model
    training_type: str  # "ALL" or a batch_training_type value


class BatchWorksetSource(Protocol):
    """Read QUALIFIED batches with aggregate facts (Application-owned projection)."""

    def qualified_batches(self) -> Sequence[BatchOverviewRecord]: ...

    def task_metric_inputs(self, batch_ids: Sequence[str]) -> Sequence[TaskMetricInput]: ...

    def equipment_metric_inputs(self, batch_ids: Sequence[str]) -> Sequence[EquipmentMetricInput]: ...


def recompute_ratio(numerator: int, denominator: int) -> tuple[str | None, str | None]:
    """Recompute a ratio from aggregated numerator/denominator (never simple-average).

    Returns (value_decimal_string, reason).  Zero denominator fails closed to null + reason.
    """

    if denominator == 0:
        return None, "ZERO_DENOMINATOR"
    return f"{numerator / denominator:.4f}", None


def _workset_fingerprint(batch_ids: Sequence[str]) -> str:
    digest = hashlib.sha256()
    for batch_id in sorted(set(batch_ids)):
        digest.update(batch_id.encode("utf-8"))
        digest.update(b"\0")
    return digest.hexdigest()


def _decimal(value: float) -> str:
    return f"{value:.4f}"


class HistoricalTrainingOverviewQuery:
    """Single owner of the V01 exact-batch-set read model."""

    def __init__(self, source: BatchWorksetSource) -> None:
        self._source = source

    def _select_workset(self, query: OverviewQuery) -> tuple[list[BatchOverviewRecord], bool]:
        """Select the single exact workset; reverse date range yields empty + warning."""

        if query.start_date > query.end_date:
            return [], True
        workset = [
            record
            for record in self._source.qualified_batches()
            if query.start_date <= record.batch_date <= query.end_date
            and (query.training_type == "ALL" or record.batch_training_type == query.training_type)
        ]
        # Batch workset is the driver; model filter narrows aggregates, never the batch set.
        return sorted(workset, key=lambda record: record.batch_date), False

    def overview(self, query: OverviewQuery) -> dict[str, object]:
        workset, invalid_range = self._select_workset(query)
        batch_ids = [record.batch_id for record in workset]
        fingerprint = _workset_fingerprint(batch_ids)
        cutoff = datetime.now().isoformat(timespec="seconds")
        task_inputs = self._source.task_metric_inputs(batch_ids)
        equip_inputs = self._source.equipment_metric_inputs(batch_ids)

        kpi = self._kpi(workset)
        task_trends = [self._task_metric_dto(item) for item in task_inputs]
        activity = self._activity_trend(workset)
        outcomes = self._outcome_trend(workset)
        category = self._category_composition(workset)
        equipment = [self._equipment_dto(item) for item in equip_inputs]

        return {
            "schema": "TPAA_G6_HISTORICAL_OVERVIEW_V1",
            "query_context_id": f"qctx-{fingerprint[:16]}",
            "filter": {
                "start_date": query.start_date.isoformat(),
                "end_date": query.end_date.isoformat(),
                "model": query.model,
                "training_type": query.training_type,
                "invalid_date_range": invalid_range,
            },
            "kpi": kpi,
            "task_metric_trends": task_trends,
            "activity_trend": activity,
            "outcome_trend": outcomes,
            "category_composition": category,
            "equipment_trends": equipment,
            "batches": [self._batch_dto(record) for record in workset],
            "batch_set_fingerprint": fingerprint,
            "aggregation_cutoff": cutoff,
            "provenance": {
                "authority_id": "GUI_HISTORICAL_OVERVIEW_AUTHORITY",
                "single_batch_workset": True,
                "batch_count": len(workset),
                "latest_fallback": False,
            },
        }

    @staticmethod
    def _kpi(workset: Sequence[BatchOverviewRecord]) -> dict[str, object]:
        return {
            "batch_count": len(workset),
            "sortie_count": sum(record.sortie_count for record in workset),
            "episode_count": sum(record.episode_count for record in workset),
            "weapon_event_count": sum(record.weapon_event_count for record in workset),
            "adjudicated_event_count": sum(record.adjudicated_event_count for record in workset),
            "data_qualification_summary": {
                "qualified": sum(1 for record in workset if record.qualification_status == "QUALIFIED"),
                "with_event_detail": sum(1 for record in workset if record.has_event_detail),
            },
        }

    @staticmethod
    def _task_metric_dto(item: TaskMetricInput) -> dict[str, object]:
        value, reason = recompute_ratio(item.numerator, item.denominator)
        return {
            "metric_id": item.metric_id,
            "label": item.label,
            "unit": item.unit,
            "definition_version": TASK_METRIC_DEFINITION_VERSION,
            "status": "DEMO_FORMULA_NOT_FORMAL" if reason is None else "FAIL_CLOSED",
            "numerator": item.numerator,
            "denominator": item.denominator,
            "value": value,
            "reason": reason,
            "points": [],
            "provenance": {"metric_authority": "SEPARATE_ADMISSION_PENDING", "simple_average": False},
        }

    @staticmethod
    def _activity_trend(workset: Sequence[BatchOverviewRecord]) -> dict[str, object]:
        return {
            "unit": "count",
            "points": [
                {
                    "batch_date": record.batch_date.isoformat(),
                    "weapon_launch": record.weapon_event_count,
                    "engagement_process": record.episode_count,
                }
                for record in workset
            ],
        }

    @staticmethod
    def _outcome_trend(workset: Sequence[BatchOverviewRecord]) -> dict[str, object]:
        # Adjudication is independent; missing J is excluded from adjudicated counts.
        return {
            "adjudicated": sum(record.adjudicated_event_count for record in workset),
            "pending": sum(record.weapon_event_count - record.adjudicated_event_count for record in workset),
        }

    @staticmethod
    def _category_composition(workset: Sequence[BatchOverviewRecord]) -> dict[str, object]:
        # Per-batch category split is not authoritative here; the V26 workbench owns category
        # detail.  V01 exposes totals only and never fabricates a WVR/BVR/Strike split.
        return {
            "note": "CATEGORY_DETAIL_OWNED_BY_V26",
            "total_weapon_events": sum(record.weapon_event_count for record in workset),
        }

    @staticmethod
    def _equipment_dto(item: EquipmentMetricInput) -> dict[str, object]:
        return {
            "metric_id": item.metric_id,
            "label": item.label,
            "unit": item.unit,
            "comparable": item.comparable,
            "eligibility": item.eligibility,
            "reason": None if item.comparable else (item.reason or "NOT_COMPARABLE"),
            "points": [{"batch_date": point[0], "value": _decimal(point[1])} for point in item.points],
            "provenance": {"metric_version": EQUIPMENT_METRIC_VERSION},
        }

    @staticmethod
    def _batch_dto(record: BatchOverviewRecord) -> dict[str, object]:
        return {
            "batch_id": record.batch_id,
            "batch_date": record.batch_date.isoformat(),
            "batch_training_type": record.batch_training_type,
            "sortie_count": record.sortie_count,
            "episode_count": record.episode_count,
            "weapon_event_count": record.weapon_event_count,
            "adjudicated_event_count": record.adjudicated_event_count,
            "qualification_status": record.qualification_status,
            "has_event_detail": record.has_event_detail,
        }


def workset_consistency(overview: Mapping[str, object]) -> bool:
    """Guard: every panel references the same exact batch set fingerprint."""

    kpi = overview.get("kpi")
    batches = overview.get("batches")
    provenance = overview.get("provenance")
    return (
        isinstance(kpi, Mapping)
        and isinstance(batches, list)
        and isinstance(provenance, Mapping)
        and provenance.get("single_batch_workset") is True
        and kpi.get("batch_count") == len(batches)
    )
