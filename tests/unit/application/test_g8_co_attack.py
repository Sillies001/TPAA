"""G8 V24 Co-attack analysis exit-gate tests."""

from __future__ import annotations

import pytest

from tpaa_application.co_attack import CoAttackAnalysisQuery, CoAttackError


class _FixtureSource:
    def __init__(self) -> None:
        self._clusters = {
            "cluster-bvr": {"cluster_id": "cluster-bvr", "batch_id": "b-1", "weapon_event_ids": ["we-2", "we-3"]},
            "cluster-strike": {"cluster_id": "cluster-strike", "batch_id": "b-1", "weapon_event_ids": ["we-4"]},
            "cluster-cross": {"cluster_id": "cluster-cross", "batch_id": "b-1", "weapon_event_ids": ["we-2", "we-9"]},
            "cluster-missing": {"cluster_id": "cluster-missing", "batch_id": "b-1", "weapon_event_ids": ["we-2", "we-404"]},
        }
        self._events = {
            "we-2": {"weapon_event_id": "we-2", "batch_id": "b-1", "category": "BVR", "t1_session_time_us": "100", "shooter_entity_id": "a-1", "target_entity_id": "t-1"},
            "we-3": {"weapon_event_id": "we-3", "batch_id": "b-1", "category": "BVR", "t1_session_time_us": "200", "shooter_entity_id": "a-2", "target_entity_id": "t-1"},
            "we-4": {"weapon_event_id": "we-4", "batch_id": "b-1", "category": "STRIKE", "t1_session_time_us": "300", "shooter_entity_id": "a-1", "target_entity_id": None},
            "we-9": {"weapon_event_id": "we-9", "batch_id": "b-2", "category": "BVR", "t1_session_time_us": "50", "shooter_entity_id": "a-9", "target_entity_id": "t-9"},
        }
        self._formation = {
            "context_id": "ctx-1",
            "revision_no": 2,
            "valid_from_session_time_us": "0",
            "valid_to_session_time_us": None,
            "members": [
                {"aircraft_id": "a-1", "formation_id": "BLUE-1", "side": "BLUE", "member_role": "LEAD", "independent_target": False},
                {"aircraft_id": "a-2", "formation_id": "BLUE-1", "side": "BLUE", "member_role": "WING", "independent_target": False},
            ],
        }

    def cluster(self, cluster_id):
        return self._clusters.get(cluster_id)

    def events(self, batch_id, weapon_event_ids):
        return tuple(
            self._events[we]
            for we in weapon_event_ids
            if we in self._events
        )

    def formation(self, context_id):
        return self._formation if context_id == "ctx-1" else None


def _analysis(cluster_id: str = "cluster-bvr", **kwargs) -> dict[str, object]:
    options = {"context_id": "ctx-1", "request_id": "req-1"}
    options.update(kwargs)
    query = options.pop("query", {"context_id": options.pop("context_id")})
    return CoAttackAnalysisQuery(_FixtureSource()).analysis(cluster_id, query, request_id=options["request_id"])


def test_exact_cluster_scope_orders_events_by_t1() -> None:
    payload = _analysis()
    assert payload["schema"] == "TPAA_G8_CO_ATTACK_ANALYSIS_V1"
    assert payload["cluster_id"] == "cluster-bvr"
    assert payload["batch_id"] == "b-1"
    order = [item["weapon_event_id"] for item in payload["weapon_events"]]
    assert order == ["we-2", "we-3"]
    assert payload["provenance"]["no_total_score"] is True


def test_formation_facts_come_from_context_revision() -> None:
    payload = _analysis()
    formation = payload["formation"]
    assert formation["revision_no"] == 2
    assert len(formation["members"]) == 2
    assert formation["members"][0]["member_role"] == "LEAD"
    dimensions = {item["dimension_id"]: item["status"] for item in payload["dimensions"]}
    assert dimensions["co_target_attack_timing"] == "FACTS_ONLY"
    assert dimensions["role_relation"] == "FACTS_ONLY"
    assert dimensions["attack_support"] == "NOT_ADMITTED"
    detail = {item["dimension_id"]: item for item in payload["dimensions"]}
    timing = detail["co_target_attack_timing"]["facts"]
    assert timing["event_count"] == 2
    assert timing["salvo_span_us"] == "100"
    assert timing["inter_event_gap_us"] == ["100"]
    assert timing["same_target"] is True
    roles = detail["role_relation"]["facts"]
    assert roles["formation_revision_no"] == 2
    assert roles["missing_shooter_ids"] == []
    assert [item["member_role"] for item in roles["shooter_roles"]] == ["LEAD", "WING"]


def test_unknown_cluster_fails_closed_404() -> None:
    with pytest.raises(CoAttackError) as excinfo:
        _analysis("missing-cluster")
    assert excinfo.value.code == "CLUSTER_NOT_FOUND"
    assert excinfo.value.http_status == 404


def test_strike_cluster_rejected_fail_closed() -> None:
    with pytest.raises(CoAttackError) as excinfo:
        _analysis("cluster-strike")
    assert excinfo.value.code == "BVR_CLUSTER_REQUIRED"
    assert excinfo.value.http_status == 422


def test_cross_batch_cluster_rejected() -> None:
    with pytest.raises(CoAttackError) as excinfo:
        _analysis("cluster-cross")
    assert excinfo.value.code == "CROSS_BATCH_CLUSTER_FORBIDDEN"


def test_missing_context_yields_honest_empty_formation() -> None:
    payload = _analysis(query={"context_id": "missing"})
    formation = payload["formation"]
    assert formation["members"] == []
    assert formation["reason_code"] == "FORMATION_CONTEXT_NOT_PROVIDED_OR_ABSENT"


def test_context_id_is_mandatory_and_exact_cluster_set_must_resolve() -> None:
    with pytest.raises(CoAttackError) as context_exc:
        _analysis(query={})
    assert context_exc.value.code == "CONTEXT_REQUIRED"
    with pytest.raises(CoAttackError) as event_exc:
        _analysis("cluster-missing")
    assert event_exc.value.code == "CLUSTER_EVENT_SET_INCOMPLETE"
    assert event_exc.value.http_status == 503


def test_formation_revision_must_cover_cluster_time_range() -> None:
    source = _FixtureSource()
    source._formation["valid_from_session_time_us"] = "150"
    with pytest.raises(CoAttackError) as excinfo:
        CoAttackAnalysisQuery(source).analysis(
            "cluster-bvr", {"context_id": "ctx-1"}, request_id="r"
        )
    assert excinfo.value.code == "FORMATION_CONTEXT_OUT_OF_RANGE"
    assert excinfo.value.http_status == 409
