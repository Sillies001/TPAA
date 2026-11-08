"""G7 V26 Batch-events workbench query — single owner of the exact Batch workset.

Every list, summary, cluster badge and timeline entry is scoped to ONE exact Batch
(identity, no latest fallback, no cross-batch borrowing).  Unknown batches fail closed
with HTTP 404 semantics under a READY backend; cursors are opaque, versioned and
checksummed.  No synthetic event ever fills the workbench.
"""

from __future__ import annotations

import base64
import hashlib
import json
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Protocol

CATEGORIES = ("WVR", "BVR", "STRIKE", "UNKNOWN")
ADJUDICATION_STATES = ("ADJUDICATED", "ADJUDICATION_PENDING")
DEFAULT_LIMIT = 25
MAXIMUM_LIMIT = 100
_CURSOR_VERSION = 1
_CURSOR_SALT = b"tpaa-g7-batch-events-cursor-v1"


class BatchEventsError(RuntimeError):
    """Transport-safe, fail-closed G7 error."""

    def __init__(self, code: str, detail: str, *, http_status: int = 422) -> None:
        self.code = code
        self.detail = detail
        self.http_status = http_status
        super().__init__(f"{code}:{detail}")


@dataclass(frozen=True, slots=True)
class BatchEventRecord:
    """One exact weapon event inside the V26 batch workset."""

    weapon_event_id: str
    revision_no: int
    batch_id: str
    t1_session_time_us: int
    category: str
    classification_exception: bool
    shooter_entity_id: str
    target_entity_id: str | None
    episode_id: str | None
    weapon_terminal_state: str
    adjudication_state: str
    observation_window_state: str
    cluster_id: str | None


@dataclass(frozen=True, slots=True)
class BatchEventsFilter:
    category: str  # "ALL" or one of CATEGORIES
    adjudication: str  # "ALL" or one of ADJUDICATION_STATES
    cluster_id: str | None  # None = all clusters
    entity_id: str | None  # shooter or target exact identity
    episode_id: str | None
    start_time_us: int | None
    end_time_us: int | None


class BatchEventSource(Protocol):
    """Read exact batch registrations and their WE/cluster relations."""

    def batch_ids(self) -> Sequence[str]: ...

    def batch_context(self, batch_id: str) -> str | None: ...

    def events(self, batch_id: str) -> Sequence[BatchEventRecord]: ...

    def cluster_of(self, batch_id: str, weapon_event_id: str) -> str | None: ...


def _filter_fingerprint(batch_id: str, query_filter: BatchEventsFilter) -> str:
    material = json.dumps(
        {
            "batch_id": batch_id,
            "category": query_filter.category,
            "adjudication": query_filter.adjudication,
            "cluster_id": query_filter.cluster_id,
            "entity_id": query_filter.entity_id,
            "episode_id": query_filter.episode_id,
            "start_time_us": query_filter.start_time_us,
            "end_time_us": query_filter.end_time_us,
        },
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(material).hexdigest()


def _encode_cursor(batch_id: str, query_filter: BatchEventsFilter, offset: int) -> str:
    payload = json.dumps(
        {
            "v": _CURSOR_VERSION,
            "f": _filter_fingerprint(batch_id, query_filter),
            "o": offset,
        },
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    checksum = hashlib.sha256(payload + _CURSOR_SALT).hexdigest()[:16]
    wrapped = json.dumps(
        {"p": base64.urlsafe_b64encode(payload).decode("ascii"), "c": checksum},
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return base64.urlsafe_b64encode(wrapped).decode("ascii").rstrip("=")


def _decode_cursor(
    cursor: str, batch_id: str, query_filter: BatchEventsFilter
) -> int:
    try:
        padded = cursor + "=" * (-len(cursor) % 4)
        wrapped = json.loads(base64.urlsafe_b64decode(padded).decode("utf-8"))
        payload = base64.urlsafe_b64decode(wrapped["p"])
        checksum = hashlib.sha256(payload + _CURSOR_SALT).hexdigest()[:16]
        if wrapped["c"] != checksum:
            raise ValueError("checksum")
        value = json.loads(payload)
    except (KeyError, TypeError, ValueError, json.JSONDecodeError) as exc:
        raise BatchEventsError("CURSOR_INVALID", "cursor is not authentic", http_status=400) from exc
    if (
        value.get("v") != _CURSOR_VERSION
        or value.get("f") != _filter_fingerprint(batch_id, query_filter)
        or not isinstance(value.get("o"), int)
        or value["o"] < 0
    ):
        raise BatchEventsError("CURSOR_INVALID", "cursor context drifted", http_status=400)
    return int(value["o"])


class BatchEventsQuery:
    """Single owner of the V26 exact-batch events read model."""

    def __init__(self, source: BatchEventSource) -> None:
        self._source = source

    @staticmethod
    def _parse_filter(raw: Mapping[str, object]) -> BatchEventsFilter:
        category = str(raw.get("category", "ALL"))
        adjudication = str(raw.get("adjudication", "ALL"))
        cluster_raw = raw.get("cluster_id")
        if category != "ALL" and category not in CATEGORIES:
            raise BatchEventsError("FILTER_INVALID", f"category={category!r}", http_status=422)
        if adjudication != "ALL" and adjudication not in ADJUDICATION_STATES:
            raise BatchEventsError(
                "FILTER_INVALID", f"adjudication={adjudication!r}", http_status=422
            )
        cluster_id = None if cluster_raw in (None, "") else str(cluster_raw)
        entity_raw = raw.get("entity_id")
        episode_raw = raw.get("episode_id")
        entity_id = None if entity_raw in (None, "") else str(entity_raw)
        episode_id = None if episode_raw in (None, "") else str(episode_raw)

        def optional_time(name: str) -> int | None:
            value = raw.get(name)
            if value in (None, ""):
                return None
            try:
                parsed = int(str(value))
            except ValueError as exc:
                raise BatchEventsError(
                    "FILTER_INVALID", f"{name} must be an integer", http_status=422
                ) from exc
            if parsed < 0:
                raise BatchEventsError(
                    "FILTER_INVALID", f"{name} must be non-negative", http_status=422
                )
            return parsed

        start_time_us = optional_time("start_time_us")
        end_time_us = optional_time("end_time_us")
        if start_time_us is not None and end_time_us is not None and start_time_us > end_time_us:
            raise BatchEventsError(
                "FILTER_INVALID", "start_time_us must not exceed end_time_us", http_status=422
            )
        return BatchEventsFilter(
            category,
            adjudication,
            cluster_id,
            entity_id,
            episode_id,
            start_time_us,
            end_time_us,
        )

    def _workset(self, batch_id: str, query_filter: BatchEventsFilter) -> list[BatchEventRecord]:
        records = [
            record
            for record in self._source.events(batch_id)
            if query_filter.category == "ALL" or record.category == query_filter.category
        ]
        if query_filter.adjudication != "ALL":
            records = [
                record
                for record in records
                if record.adjudication_state == query_filter.adjudication
            ]
        if query_filter.cluster_id is not None:
            records = [
                record
                for record in records
                if record.cluster_id == query_filter.cluster_id
            ]
        if query_filter.entity_id is not None:
            records = [
                record
                for record in records
                if query_filter.entity_id
                in {record.shooter_entity_id, record.target_entity_id}
            ]
        if query_filter.episode_id is not None:
            records = [
                record for record in records if record.episode_id == query_filter.episode_id
            ]
        if query_filter.start_time_us is not None:
            records = [
                record
                for record in records
                if record.t1_session_time_us >= query_filter.start_time_us
            ]
        if query_filter.end_time_us is not None:
            records = [
                record
                for record in records
                if record.t1_session_time_us <= query_filter.end_time_us
            ]
        return sorted(records, key=lambda item: (item.t1_session_time_us, item.weapon_event_id))

    def workbench(
        self,
        batch_id: str,
        raw_filter: Mapping[str, object],
        *,
        cursor: str | None,
        limit: int,
        request_id: str,
    ) -> dict[str, object]:
        if limit < 1 or limit > MAXIMUM_LIMIT:
            raise BatchEventsError(
                "CURSOR_INVALID", f"limit must be 1..{MAXIMUM_LIMIT}", http_status=400
            )
        if batch_id not in set(self._source.batch_ids()):
            raise BatchEventsError(
                "BATCH_NOT_FOUND",
                f"batch {batch_id} is not an exact registered batch",
                http_status=404,
            )
        query_filter = self._parse_filter(raw_filter)
        workset = self._workset(batch_id, query_filter)
        offset = 0 if cursor is None else _decode_cursor(cursor, batch_id, query_filter)
        page = workset[offset : offset + limit]
        next_offset = offset + len(page)
        next_cursor = (
            _encode_cursor(batch_id, query_filter, next_offset)
            if next_offset < len(workset)
            else None
        )
        clusters = {record.cluster_id for record in workset if record.cluster_id is not None}
        summary = {
            "weapon_event_count": len(workset),
            "cluster_count": len(clusters),
            "category_counts": {
                category: sum(1 for record in workset if record.category == category)
                for category in CATEGORIES
            },
            "adjudication_counts": {
                state: sum(1 for record in workset if record.adjudication_state == state)
                for state in ADJUDICATION_STATES
            },
            "classification_exception_count": sum(
                1 for record in workset if record.classification_exception
            ),
        }
        fingerprint = _filter_fingerprint(batch_id, query_filter)
        batch_context = self._source.batch_context(batch_id)
        return {
            "schema": "TPAA_G7_BATCH_EVENT_WORKBENCH_V1",
            "request_id": request_id,
            "provenance": {
                "authority_id": "GUI_BATCH_EVENTS_AUTHORITY",
                "core_baseline": "CB-1.12.0",
                "single_exact_batch_scope": True,
                "latest_fallback": False,
            },
            "query_context_id": f"qctx-{fingerprint[:16]}",
            "batch_id": batch_id,
            "batch_context_id": batch_context,
            "filter": {
                "category": query_filter.category,
                "adjudication": query_filter.adjudication,
                "cluster_id": query_filter.cluster_id,
                "entity_id": query_filter.entity_id,
                "episode_id": query_filter.episode_id,
                "start_time_us": (
                    None if query_filter.start_time_us is None else str(query_filter.start_time_us)
                ),
                "end_time_us": (
                    None if query_filter.end_time_us is None else str(query_filter.end_time_us)
                ),
            },
            "summary": summary,
            "items": [
                {
                    "schema": "TPAA_G7_BATCH_EVENT_LIST_ITEM_V1",
                    "weapon_event_id": record.weapon_event_id,
                    "revision_no": record.revision_no,
                    "batch_id": record.batch_id,
                    "cluster_id": record.cluster_id,
                    "category": record.category,
                    "t1_session_time_us": str(record.t1_session_time_us),
                    "shooter_entity_id": record.shooter_entity_id,
                    "target_entity_id": record.target_entity_id,
                    "episode_id": record.episode_id,
                    "weapon_terminal_state": record.weapon_terminal_state,
                    "adjudication_state": record.adjudication_state,
                    "observation_window_state": record.observation_window_state,
                    "classification_exception": record.classification_exception,
                }
                for record in page
            ],
            "next_cursor": next_cursor,
            "total_count": len(workset),
        }
