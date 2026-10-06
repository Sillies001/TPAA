from __future__ import annotations

from dataclasses import dataclass

import pytest

from tpaa_runtime.durable_discovery import DurableProductDiscovery


class _Rows:
    def many(
        self,
        table: str,
        *,
        where,
        columns,
        order_by=(),
    ):
        del columns, order_by
        if table == "registry.training_session":
            return (
                {
                    "session_id": "s1",
                    "session_code": "S-001",
                    "session_type": "FLIGHT",
                    "start_session_time_us": 10,
                    "end_session_time_us": 20,
                    "data_status": "READY",
                },
            )
        if table == "registry.analysis_release":
            p1_rows = (
                {
                    "release_id": "r1",
                    "session_id": "s1",
                    "scope_type": "SESSION",
                    "scope_key": "s1",
                    "release_no": 1,
                    "status": "PUBLISHED",
                    "parent_release_id": None,
                    "manifest_hash": "a" * 64,
                    "created_at": "2026-01-01T00:00:00Z",
                    "published_at": "2026-01-01T00:00:00Z",
                },
                {
                    "release_id": "r2",
                    "session_id": "s1",
                    "scope_type": "SESSION",
                    "scope_key": "s1",
                    "release_no": 2,
                    "status": "PUBLISHED",
                    "parent_release_id": "r1",
                    "manifest_hash": "b" * 64,
                    "created_at": "2026-01-02T00:00:00Z",
                    "published_at": "2026-01-02T00:00:00Z",
                },
            )
            p2_row = {
                "release_id": "p2-r1",
                "session_id": "s1",
                "scope_type": "SESSION",
                "scope_key": "P2:o1",
                "release_no": 1,
                "status": "PUBLISHED",
                "parent_release_id": None,
                "manifest_hash": "d" * 64,
                "created_at": "2026-01-03T00:00:00Z",
                "published_at": "2026-01-03T00:00:00Z",
            }
            m4_row = {
                "release_id": "m4-r1",
                "session_id": None,
                "scope_type": "LONGITUDINAL",
                "scope_key": "scope-1",
                "release_no": 1,
                "status": "PUBLISHED",
                "parent_release_id": None,
                "manifest_hash": "e" * 64,
                "created_at": "2026-01-04T00:00:00Z",
                "published_at": "2026-01-04T00:00:00Z",
            }
            if where == {
                "session_id": "s1",
                "scope_type": "SESSION",
            }:
                return (*p1_rows, p2_row)
            if where == {"scope_type": "LONGITUDINAL"}:
                return (m4_row,)
            if where == {}:
                return (*p1_rows, p2_row, m4_row)
            raise AssertionError(where)
        if table == "capability.adjusted_capability_estimate":
            return (
                {
                    "estimate_id": "e1",
                    "source_observation_id": "o1",
                    "aircraft_id": "a1",
                    "capability_type": "BASIC",
                    "status": "AVAILABLE",
                    "created_at": "2026-01-01T00:00:00Z",
                },
            )
        raise AssertionError(table)

    def one(self, table: str, *, where, columns):
        del where, columns
        if table == "capability.adjusted_capability_estimate_revision":
            return {"p2_release_id": "p2-r1"}
        if table == "metric.capability_observation":
            return {"release_id": "r1", "session_id": "s1"}
        raise AssertionError(table)


class _Publication:
    def logical_membership(self, release_id: str) -> dict[str, object]:
        assert release_id == "r1"
        return {
            "evidence_sets": [
                {
                    "evidence_set_id": "ev1",
                    "series_locator": {
                        "canonical_dataset_id": "d1",
                        "canonical_dataset_uri": (
                            "tpaa-parquet://production/canonical-flight/"
                            "d1/part-000.parquet"
                        ),
                        "canonical_logical_content_hash": "c" * 64,
                    },
                }
            ]
        }


@dataclass
class _Uow:
    canonical_rows: _Rows
    publication: _Publication

    def __enter__(self):
        return self

    def __exit__(self, _exc_type, _exc, _tb):
        return None

    def commit(self) -> None:
        return None


def _factory():
    return _Uow(_Rows(), _Publication())


def test_prcb_c4_discovery_is_exact_and_never_latest_alias() -> None:
    discovery = DurableProductDiscovery(_factory)
    sessions = discovery.sessions()
    releases = discovery.releases("s1")
    products = discovery.products("p2_estimate")
    p1_products = discovery.products("p1_release")
    m4_products = discovery.products("m4_release")

    session_items = sessions["items"]
    release_items = releases["items"]
    product_items = products["items"]
    assert isinstance(session_items, list)
    assert isinstance(release_items, list)
    assert isinstance(product_items, list)
    assert "current_release_id" not in session_items[0]
    assert [item["release_id"] for item in release_items] == ["r1", "r2"]
    assert releases["current_latest_fallback_used"] is False
    p1_items = p1_products["items"]
    m4_items = m4_products["items"]
    assert isinstance(p1_items, list)
    assert isinstance(m4_items, list)
    assert [item["exact_id"] for item in p1_items] == ["r1", "r2"]
    assert [item["exact_id"] for item in m4_items] == ["m4-r1"]
    item = product_items[0]
    assert item["exact_id"] == "e1"
    metadata = item["metadata"]
    assert isinstance(metadata, dict)
    assert metadata["p2_release_id"] == "p2-r1"
    assert metadata["source_release_id"] == "r1"
    assert metadata["session_id"] == "s1"
    assert products["current_latest_fallback_used"] is False

    presentation = discovery.release_presentation("r1")
    assert presentation["release_id"] == "r1"
    assert presentation["available"] is False
    assert presentation["reason_code"] == "GEODETIC_SERIES_NOT_PRESENT"
    assert presentation["current_latest_fallback_used"] is False
    assert presentation["business_recompute_performed"] is False

    with pytest.raises(ValueError):
        discovery.products("LATEST")
