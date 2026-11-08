"""G7 V26 Batch-events exit-gate tests."""

from __future__ import annotations

import pytest

from tpaa_application.batch_events import (
    BatchEventRecord,
    BatchEventsError,
    BatchEventsQuery,
)


def _record(
    weapon_event_id: str,
    batch_id: str,
    *,
    t1: int,
    category: str = "BVR",
    adjudication: str = "ADJUDICATION_PENDING",
    cluster_id: str | None = None,
    exception: bool = False,
    shooter: str = "shooter-1",
    target: str | None = "target-1",
    episode: str | None = "episode-1",
) -> BatchEventRecord:
    return BatchEventRecord(
        weapon_event_id=weapon_event_id,
        revision_no=1,
        batch_id=batch_id,
        t1_session_time_us=t1,
        category=category,
        classification_exception=exception,
        shooter_entity_id=shooter,
        target_entity_id=target,
        episode_id=episode,
        weapon_terminal_state="TERMINAL_KNOWN",
        adjudication_state=adjudication,
        observation_window_state="WINDOW_CLOSED",
        cluster_id=cluster_id,
    )


class _FixtureSource:
    def __init__(self) -> None:
        cluster = "cluster-1"
        self._events = (
            _record("we-1", "b-1", t1=300, category="WVR", adjudication="ADJUDICATED"),
            _record("we-2", "b-1", t1=100, category="BVR", adjudication="ADJUDICATED", cluster_id=cluster),
            _record("we-3", "b-1", t1=200, category="BVR", adjudication="ADJUDICATION_PENDING", cluster_id=cluster),
            _record(
                "we-4", "b-1", t1=400, category="STRIKE", exception=True,
                shooter="shooter-2", target=None, episode="episode-2",
            ),
            _record("we-5", "b-2", t1=150, category="BVR", adjudication="ADJUDICATED"),
        )

    def batch_ids(self):
        return ("b-1", "b-2")

    def batch_context(self, batch_id):
        return None

    def events(self, batch_id):
        return tuple(record for record in self._events if record.batch_id == batch_id)

    def cluster_of(self, batch_id, weapon_event_id):
        for record in self.events(batch_id):
            if record.weapon_event_id == weapon_event_id:
                return record.cluster_id
        return None


def _workbench(batch_id: str = "b-1", **kwargs) -> dict[str, object]:
    options = {"cursor": None, "limit": 25, "request_id": "req-1"}
    options.update(kwargs)
    return BatchEventsQuery(_FixtureSource()).workbench(batch_id, {}, **options)


def test_exact_batch_scope_never_borrows_from_other_batches() -> None:
    payload = _workbench()
    assert payload["batch_id"] == "b-1"
    assert payload["total_count"] == 4
    assert all(item["batch_id"] == "b-1" for item in payload["items"])
    assert "we-5" not in {item["weapon_event_id"] for item in payload["items"]}
    assert payload["provenance"]["single_exact_batch_scope"] is True
    assert payload["provenance"]["latest_fallback"] is False


def test_unknown_batch_fails_closed_404() -> None:
    with pytest.raises(BatchEventsError) as excinfo:
        _workbench("missing-batch")
    assert excinfo.value.code == "BATCH_NOT_FOUND"
    assert excinfo.value.http_status == 404


def test_items_sorted_by_t1_and_summary_tracks_filters() -> None:
    payload = _workbench()
    order = [item["weapon_event_id"] for item in payload["items"]]
    assert order == ["we-2", "we-3", "we-1", "we-4"]
    summary = payload["summary"]
    assert summary["weapon_event_count"] == 4
    assert summary["cluster_count"] == 1
    assert summary["category_counts"] == {"WVR": 1, "BVR": 2, "STRIKE": 1, "UNKNOWN": 0}
    assert summary["adjudication_counts"] == {"ADJUDICATED": 2, "ADJUDICATION_PENDING": 2}
    assert summary["classification_exception_count"] == 1


def test_category_and_adjudication_filters_narrow_workset() -> None:
    payload = BatchEventsQuery(_FixtureSource()).workbench(
        "b-1", {"category": "BVR", "adjudication": "ADJUDICATED"}, cursor=None, limit=25, request_id="r"
    )
    assert payload["total_count"] == 1
    assert payload["items"][0]["weapon_event_id"] == "we-2"
    assert payload["summary"]["weapon_event_count"] == 1


def test_cluster_filter_groups_salvo() -> None:
    payload = BatchEventsQuery(_FixtureSource()).workbench(
        "b-1", {"cluster_id": "cluster-1"}, cursor=None, limit=25, request_id="r"
    )
    assert payload["total_count"] == 2
    assert {item["weapon_event_id"] for item in payload["items"]} == {"we-2", "we-3"}


def test_entity_episode_and_half_closed_time_filters_bind_exact_workset() -> None:
    query = BatchEventsQuery(_FixtureSource())
    entity = query.workbench(
        "b-1", {"entity_id": "shooter-2"}, cursor=None, limit=25, request_id="r"
    )
    assert [item["weapon_event_id"] for item in entity["items"]] == ["we-4"]
    episode = query.workbench(
        "b-1", {"episode_id": "episode-1"}, cursor=None, limit=25, request_id="r"
    )
    assert {item["weapon_event_id"] for item in episode["items"]} == {
        "we-1", "we-2", "we-3"
    }
    time_range = query.workbench(
        "b-1",
        {"start_time_us": "150", "end_time_us": "300"},
        cursor=None,
        limit=25,
        request_id="r",
    )
    assert [item["weapon_event_id"] for item in time_range["items"]] == ["we-3", "we-1"]
    assert time_range["filter"]["start_time_us"] == "150"
    assert time_range["filter"]["end_time_us"] == "300"


def test_cursor_pagination_walks_and_rejects_tampering() -> None:
    query = BatchEventsQuery(_FixtureSource())
    first = query.workbench("b-1", {}, cursor=None, limit=2, request_id="r")
    assert len(first["items"]) == 2
    assert first["next_cursor"] is not None
    second = query.workbench(
        "b-1", {}, cursor=first["next_cursor"], limit=2, request_id="r"
    )
    assert [item["weapon_event_id"] for item in second["items"]] == ["we-1", "we-4"]
    assert second["next_cursor"] is None
    with pytest.raises(BatchEventsError, match="CURSOR_INVALID"):
        query.workbench("b-1", {}, cursor=first["next_cursor"][:-2] + "AA", limit=2, request_id="r")
    with pytest.raises(BatchEventsError, match="CURSOR_INVALID"):
        query.workbench(
            "b-1", {"category": "BVR"}, cursor=first["next_cursor"], limit=2, request_id="r"
        )


def test_invalid_limit_and_filter_fail_closed() -> None:
    with pytest.raises(BatchEventsError, match="CURSOR_INVALID"):
        _workbench(limit=0)
    with pytest.raises(BatchEventsError, match="CURSOR_INVALID"):
        _workbench(limit=101)
    with pytest.raises(BatchEventsError, match="FILTER_INVALID"):
        BatchEventsQuery(_FixtureSource()).workbench(
            "b-1", {"category": "DOGFIGHT"}, cursor=None, limit=25, request_id="r"
        )
    with pytest.raises(BatchEventsError, match="FILTER_INVALID"):
        BatchEventsQuery(_FixtureSource()).workbench(
            "b-1",
            {"start_time_us": "400", "end_time_us": "100"},
            cursor=None,
            limit=25,
            request_id="r",
        )
    with pytest.raises(BatchEventsError, match="FILTER_INVALID"):
        BatchEventsQuery(_FixtureSource()).workbench(
            "b-1", {"start_time_us": "not-an-int"}, cursor=None, limit=25, request_id="r"
        )
