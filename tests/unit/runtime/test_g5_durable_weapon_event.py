from __future__ import annotations

from typing import Self

from tpaa_runtime.durable_weapon_event import DurableWeaponEventReadAdapter


class _Rows:
    def __init__(self, rows: tuple[dict[str, object], ...]) -> None:
        self.rows = rows

    def many(
        self,
        table: str,
        *,
        where: dict[str, object],
        columns: tuple[str, ...],
        order_by: tuple[str, ...] = (),
    ) -> tuple[dict[str, object], ...]:
        del columns, order_by
        relation_type = where["relation_type"]
        return tuple(
            row
            for row in self.rows
            if table == "world.world_relation" and row.get("relation_type") == relation_type
        )


class _Uow:
    def __init__(self, rows: tuple[dict[str, object], ...]) -> None:
        self.canonical_rows = _Rows(rows)

    def __enter__(self) -> Self:
        return self

    def __exit__(self, *_args: object) -> None:
        return None


def _factory(rows: tuple[dict[str, object], ...]):
    return lambda: _Uow(rows)


def test_canonical_adapter_reports_honest_empty_without_fabricating_data() -> None:
    adapter = DurableWeaponEventReadAdapter(_factory(()))  # type: ignore[arg-type]
    assert adapter.list_ids("batch-1") == ()
    assert adapter.get("missing") is None


def test_canonical_adapter_reads_exact_relation_subtype() -> None:
    row: dict[str, object] = {
        "relation_id": "we-1",
        "relation_type": "WEAPON_EVENT",
        "release_id": "release-1",
        "episode_id": "episode-1",
        "stage_id": None,
        "subject_ref": "shooter-1",
        "object_ref": "target-1",
        "start_session_time_us": 12170000,
        "properties": {
            "batch_id": "batch-1",
            "category": "WVR",
            "category_rule_version": "WE-CAT-1.0.0",
            "classification_exception": False,
            "target_entity_id": "target-1",
            "weapon_terminal_state": "TERMINAL_UNKNOWN",
            "adjudication_state": "ADJUDICATION_PENDING",
            "observation_window_state": "WINDOW_OPEN",
            "identity_material": "batch-1|L1|shooter-1|12170000|IR",
        },
    }
    adapter = DurableWeaponEventReadAdapter(_factory((row,)))  # type: ignore[arg-type]
    snapshot = adapter.get("we-1")
    assert snapshot is not None
    assert snapshot.event.batch_id == "batch-1"
    assert snapshot.event.t1_session_time_us == 12170000
    assert adapter.list_ids("batch-1") == ("we-1",)
