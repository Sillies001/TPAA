"""SQLite/PostgreSQL stored timestamp parity for ED2 B2 durable reads."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest

from tpaa_runtime.production_downstream import (
    ProductionDownstreamError,
    _stored_utc_text,
)


def test_ed2_b2_stored_time_normalizes_sqlite_and_postgres_utc() -> None:
    assert (
        _stored_utc_text("2026-10-10 05:00:00", "world.created_at")
        == "2026-10-10T05:00:00Z"
    )
    assert (
        _stored_utc_text(
            datetime(2026, 10, 10, 5, 0, tzinfo=UTC),
            "world.created_at",
        )
        == "2026-10-10T05:00:00Z"
    )
    assert (
        _stored_utc_text("2026-10-10T05:00:00Z", "world.created_at")
        == "2026-10-10T05:00:00Z"
    )


@pytest.mark.parametrize(
    "raw",
    [
        "2026-10-10T05:00:00",
        "2026-10-10 05:00:00+00:00",
        "not-a-time",
        None,
    ],
)
def test_ed2_b2_stored_time_rejects_unapproved_representations(
    raw: object,
) -> None:
    with pytest.raises(
        ProductionDownstreamError,
        match="ED2_B2_TIME_INVALID",
    ):
        _stored_utc_text(raw, "world.created_at")
