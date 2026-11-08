"""G6 Historical Training Overview exit-gate tests."""

from __future__ import annotations

from datetime import date

from tpaa_application.historical_overview import (
    BatchOverviewRecord,
    EquipmentMetricInput,
    HistoricalTrainingOverviewQuery,
    OverviewQuery,
    TaskMetricInput,
    recompute_ratio,
    workset_consistency,
)


class _FixtureSource:
    def __init__(self) -> None:
        self._batches = [
            BatchOverviewRecord("b-001", date(2026, 10, 20), "COMPREHENSIVE_OPPOSITION", 6, 4, 9, 7, "QUALIFIED", True),
            BatchOverviewRecord("b-002", date(2026, 10, 22), "SIMPLE_OPPOSITION", 4, 3, 5, 5, "QUALIFIED", False),
            BatchOverviewRecord("b-003", date(2026, 10, 25), "COMPREHENSIVE_OPPOSITION", 8, 6, 12, 0, "QUALIFIED", True),
        ]

    def qualified_batches(self):
        return tuple(self._batches)

    def task_metric_inputs(self, batch_ids):
        ids = set(batch_ids)
        num_batches = len(ids)
        return (
            TaskMetricInput("kill_ratio", "击杀比", "ratio", 7 * num_batches, 10 * num_batches),
            TaskMetricInput("zero_metric", "零分母指标", "ratio", 0, 0),
        )

    def equipment_metric_inputs(self, batch_ids):
        return (
            EquipmentMetricInput("sustained_turn", "持续盘旋角速度", "deg/s", True, "ELIGIBLE", None, (("2026-10-20", 13.2),)),
            EquipmentMetricInput("mixed_config", "混构指标", "deg/s", False, "NOT_COMPARABLE", "CONFIG_MISMATCH", ()),
        )


def _query() -> OverviewQuery:
    return OverviewQuery(date(2026, 10, 1), date(2026, 10, 31), "ALL", "ALL")


def test_single_batch_workset_drives_all_panels() -> None:
    overview = HistoricalTrainingOverviewQuery(_FixtureSource()).overview(_query())
    assert workset_consistency(overview)
    assert overview["kpi"]["batch_count"] == 3
    assert len(overview["batches"]) == 3
    assert overview["provenance"]["batch_count"] == 3
    fingerprint = overview["batch_set_fingerprint"]
    assert isinstance(fingerprint, str) and len(fingerprint) == 64


def test_ratio_recomputed_from_aggregated_numerator_denominator() -> None:
    value, reason = recompute_ratio(7, 10)
    assert value == "0.7000"
    assert reason is None
    zero, zero_reason = recompute_ratio(0, 0)
    assert zero is None and zero_reason == "ZERO_DENOMINATOR"


def test_task_metric_zero_denominator_fails_closed() -> None:
    overview = HistoricalTrainingOverviewQuery(_FixtureSource()).overview(_query())
    metrics = {item["metric_id"]: item for item in overview["task_metric_trends"]}
    assert metrics["kill_ratio"]["value"] == "0.7000"
    assert metrics["zero_metric"]["value"] is None
    assert metrics["zero_metric"]["status"] == "FAIL_CLOSED"
    assert metrics["zero_metric"]["reason"] == "ZERO_DENOMINATOR"


def test_missing_j_excluded_from_adjudicated_outcome() -> None:
    overview = HistoricalTrainingOverviewQuery(_FixtureSource()).overview(_query())
    # b-003 has 12 WEs but 0 adjudicated; pending must reflect missing J explicitly.
    assert overview["outcome_trend"]["adjudicated"] == 12
    assert overview["outcome_trend"]["pending"] == (9 - 7) + (5 - 5) + (12 - 0)


def test_reverse_date_range_fails_closed_empty_with_warning() -> None:
    bad = OverviewQuery(date(2026, 10, 31), date(2026, 10, 1), "ALL", "ALL")
    overview = HistoricalTrainingOverviewQuery(_FixtureSource()).overview(bad)
    assert overview["filter"]["invalid_date_range"] is True
    assert overview["kpi"]["batch_count"] == 0
    assert overview["batches"] == []
    assert workset_consistency(overview)


def test_training_type_filter_selects_exact_workset() -> None:
    query = OverviewQuery(date(2026, 10, 1), date(2026, 10, 31), "ALL", "COMPREHENSIVE_OPPOSITION")
    overview = HistoricalTrainingOverviewQuery(_FixtureSource()).overview(query)
    assert overview["kpi"]["batch_count"] == 2
    assert all(b["batch_training_type"] == "COMPREHENSIVE_OPPOSITION" for b in overview["batches"])


def test_equipment_comparability_fails_closed() -> None:
    overview = HistoricalTrainingOverviewQuery(_FixtureSource()).overview(_query())
    equipment = {item["metric_id"]: item for item in overview["equipment_trends"]}
    assert equipment["sustained_turn"]["comparable"] is True
    assert equipment["mixed_config"]["comparable"] is False
    assert equipment["mixed_config"]["reason"] == "CONFIG_MISMATCH"


def test_empty_workset_is_honest_not_fabricated() -> None:
    query = OverviewQuery(date(2027, 1, 1), date(2027, 1, 31), "ALL", "ALL")
    overview = HistoricalTrainingOverviewQuery(_FixtureSource()).overview(query)
    assert overview["kpi"]["batch_count"] == 0
    assert overview["activity_trend"]["points"] == []
    assert overview["provenance"]["latest_fallback"] is False
