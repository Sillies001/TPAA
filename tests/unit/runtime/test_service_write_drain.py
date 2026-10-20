from __future__ import annotations

from dataclasses import dataclass

import pytest

from tpaa_runtime.service_drain import (
    PostgreSQLServiceWriteDrain,
    ServiceWriteDrainError,
)
from tpaa_storage import SERVICE_WRITE_GATE_LOCK_ID


@dataclass
class FakeCursor:
    connection: FakeConnection
    row: tuple[object, ...] | None = None

    def __enter__(self) -> FakeCursor:
        return self

    def __exit__(self, *_: object) -> None:
        return None

    def execute(self, sql: str, parameters: tuple[object, ...] = ()) -> None:
        self.connection.executed.append((sql, parameters))
        if "pg_try_advisory_lock" in sql:
            available = self.connection.acquire_results.pop(0)
            self.row = (available,)
        elif "current_database" in sql:
            self.row = ("tpaa-private", "10:20:", "0/16B6C50")
        elif "pg_advisory_unlock" in sql:
            self.row = (True,)

    def fetchone(self) -> tuple[object, ...] | None:
        return self.row


class FakeConnection:
    def __init__(self, acquire_results: list[bool]) -> None:
        self.acquire_results = acquire_results
        self.executed: list[tuple[str, tuple[object, ...]]] = []
        self.commits = 0
        self.closes = 0

    def cursor(self) -> FakeCursor:
        return FakeCursor(self)

    def commit(self) -> None:
        self.commits += 1

    def close(self) -> None:
        self.closes += 1


def test_managed_write_drain_retries_records_watermark_and_releases() -> None:
    connection = FakeConnection([False, True])
    drain = PostgreSQLServiceWriteDrain(
        "password=must-not-appear",
        timeout_seconds=1,
        poll_interval_seconds=0.001,
        connection_factory=lambda _conninfo: connection,
    )
    with drain as receipt:
        assert receipt.schema == "TPAA_SERVICE_WRITE_DRAIN_V1"
        assert receipt.state == "MANAGED_WRITES_BLOCKED"
        assert receipt.lock_id == SERVICE_WRITE_GATE_LOCK_ID
        assert len(receipt.database_identity_sha256) == 64
        assert "tpaa-private" not in str(receipt.record())
        assert "must-not-appear" not in str(receipt.record())
        assert drain.receipt == receipt

    assert connection.closes == 1
    assert connection.executed[-1] == (
        "SELECT pg_advisory_unlock(%s)",
        (SERVICE_WRITE_GATE_LOCK_ID,),
    )


def test_managed_write_drain_times_out_without_false_receipt() -> None:
    connection = FakeConnection([False])
    drain = PostgreSQLServiceWriteDrain(
        "dbname=tpaa",
        timeout_seconds=0,
        connection_factory=lambda _conninfo: connection,
    )
    with pytest.raises(ServiceWriteDrainError, match="timed out"):
        with drain:
            pass
    assert connection.closes == 1
    with pytest.raises(ServiceWriteDrainError, match="not active"):
        _ = drain.receipt


def test_managed_write_drain_validates_timeout_configuration() -> None:
    with pytest.raises(ValueError, match="non-negative"):
        PostgreSQLServiceWriteDrain("dbname=tpaa", timeout_seconds=-1)
    with pytest.raises(ValueError, match="positive"):
        PostgreSQLServiceWriteDrain("dbname=tpaa", poll_interval_seconds=0)
