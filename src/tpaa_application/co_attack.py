"""G8 V24 Co-attack analysis query — single owner of the exact Cluster read model.

The analysis is scoped to ONE exact ATTACK_CLUSTER relation (never a cross-batch
cluster, never latest fallback).  BVR clusters only: Strike clusters are rejected
fail-closed.  Missing force-formation context yields an honest EMPTY formation block,
never a fabricated one.  No total score is ever produced.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping, Sequence
from typing import Protocol


class CoAttackError(RuntimeError):
    """Transport-safe, fail-closed G8 error."""

    def __init__(self, code: str, detail: str, *, http_status: int = 422) -> None:
        self.code = code
        self.detail = detail
        self.http_status = http_status
        super().__init__(f"{code}:{detail}")


class CoAttackEventSource(Protocol):
    """Read exact cluster/WE/context facts for the V24 workbench."""

    def cluster(self, cluster_id: str) -> Mapping[str, object] | None: ...

    def events(self, batch_id: str, weapon_event_ids: Sequence[str]) -> Sequence[Mapping[str, object]]: ...

    def formation(self, context_id: str) -> Mapping[str, object] | None: ...


def _context_id(cluster_id: str, query_context: str | None) -> str:
    material = json.dumps(
        {"cluster": cluster_id, "context": query_context}, sort_keys=True, separators=(",", ":")
    ).encode("utf-8")
    return f"qctx-{hashlib.sha256(material).hexdigest()[:16]}"


class CoAttackAnalysisQuery:
    """Single owner of the V24 exact-cluster co-attack read model."""

    def __init__(self, source: CoAttackEventSource) -> None:
        self._source = source

    def analysis(
        self,
        cluster_id: str,
        raw_query: Mapping[str, object],
        *,
        request_id: str,
    ) -> dict[str, object]:
        context_query = raw_query.get("context_id")
        context_id = None if context_query in (None, "") else str(context_query)
        if context_id is None:
            raise CoAttackError(
                "CONTEXT_REQUIRED",
                "V24 requires the exact V08 release/context grant",
                http_status=422,
            )
        cluster = self._source.cluster(cluster_id)
        if cluster is None:
            raise CoAttackError(
                "CLUSTER_NOT_FOUND", f"cluster {cluster_id} is absent", http_status=404
            )
        batch_id = str(cluster.get("batch_id") or "")
        weapon_event_ids = cluster.get("weapon_event_ids")
        if not batch_id or not isinstance(weapon_event_ids, list) or not weapon_event_ids:
            raise CoAttackError("CLUSTER_INVALID", "cluster relation is malformed", http_status=422)
        events = [
            dict(event)
            for event in self._source.events(batch_id, [str(value) for value in weapon_event_ids])
        ]
        requested_ids = {str(value) for value in weapon_event_ids}
        returned_ids = {str(event.get("weapon_event_id")) for event in events}
        if returned_ids != requested_ids:
            raise CoAttackError(
                "CLUSTER_EVENT_SET_INCOMPLETE",
                "the exact Cluster event set cannot be fully resolved",
                http_status=503,
            )
        if any(str(event.get("batch_id")) != batch_id for event in events):
            raise CoAttackError(
                "CROSS_BATCH_CLUSTER_FORBIDDEN",
                "cluster spans batches (cross-batch borrowing forbidden)",
                http_status=422,
            )
        categories = {str(event.get("category", "UNKNOWN")) for event in events}
        if categories != {"BVR"}:
            raise CoAttackError(
                "BVR_CLUSTER_REQUIRED",
                "V24 co-attack analysis accepts only a pure BVR Cluster",
                http_status=422,
            )
        ordered = sorted(
            events,
            key=lambda item: (int(str(item.get("t1_session_time_us", "0"))), str(item.get("weapon_event_id"))),
        )
        formation = self._source.formation(context_id)
        event_times = [int(str(event.get("t1_session_time_us", "0"))) for event in ordered]
        if formation is not None and event_times:
            valid_from = int(str(formation.get("valid_from_session_time_us", "0")))
            valid_to_raw = formation.get("valid_to_session_time_us")
            valid_to = None if valid_to_raw in (None, "") else int(str(valid_to_raw))
            if min(event_times) < valid_from or (
                valid_to is not None and max(event_times) >= valid_to
            ):
                raise CoAttackError(
                    "FORMATION_CONTEXT_OUT_OF_RANGE",
                    "formation revision does not cover the exact Cluster event times",
                    http_status=409,
                )
        target_ids = {
            str(event.get("target_entity_id"))
            for event in ordered
            if event.get("target_entity_id") not in (None, "")
        }
        shooter_ids = {str(event.get("shooter_entity_id", "")) for event in ordered}
        gaps = [
            event_times[index] - event_times[index - 1]
            for index in range(1, len(event_times))
        ]
        members_value = formation.get("members", []) if formation is not None else []
        members = (
            members_value
            if isinstance(members_value, Sequence)
            and not isinstance(members_value, (str, bytes))
            else []
        )
        member_rows = [dict(row) for row in members if isinstance(row, Mapping)]
        member_by_aircraft = {str(row.get("aircraft_id")): row for row in member_rows}
        missing_shooters = sorted(shooter_ids - set(member_by_aircraft))
        dimension_facts = [
            {
                "dimension_id": "target_information_formation",
                "status": "NOT_ADMITTED",
                "reason": "感知/目标信息形成证据未准入；不造图、不评分。",
            },
            {
                "dimension_id": "perception_attack_relation",
                "status": "NOT_ADMITTED",
                "reason": "感知—攻击关系证据未准入；不造图、不评分。",
            },
            {
                "dimension_id": "attack_support",
                "status": "NOT_ADMITTED",
                "reason": "攻击支援证据未准入；不造图、不评分。",
            },
            {
                "dimension_id": "co_target_attack_timing",
                "status": "FACTS_ONLY",
                "reason": "以下事实来自精确 Cluster 的 WE 时间序列。",
                "facts": {
                    "event_count": len(ordered),
                    "first_t1_session_time_us": str(min(event_times)),
                    "last_t1_session_time_us": str(max(event_times)),
                    "salvo_span_us": str(max(event_times) - min(event_times)),
                    "inter_event_gap_us": [str(value) for value in gaps],
                    "same_target": len(target_ids) == 1 and len(ordered) > 1,
                    "target_entity_ids": sorted(target_ids),
                },
            },
            {
                "dimension_id": "role_relation",
                "status": "FACTS_ONLY" if formation is not None else "N_A",
                "reason": (
                    "以下事实来自覆盖 Cluster 时间范围的编队上下文修订。"
                    if formation is not None
                    else "精确 Context 没有可用编队修订；不推测成员角色。"
                ),
                "facts": {
                    "formation_revision_no": (
                        None if formation is None else int(str(formation.get("revision_no", 1)))
                    ),
                    "shooter_roles": [
                        {
                            "aircraft_id": shooter,
                            "formation_id": member_by_aircraft[shooter].get("formation_id"),
                            "side": member_by_aircraft[shooter].get("side"),
                            "member_role": member_by_aircraft[shooter].get("member_role"),
                        }
                        for shooter in sorted(shooter_ids & set(member_by_aircraft))
                    ],
                    "missing_shooter_ids": missing_shooters,
                },
            },
        ]
        return {
            "schema": "TPAA_G8_CO_ATTACK_ANALYSIS_V1",
            "request_id": request_id,
            "provenance": {
                "authority_id": "GUI_CO_ATTACK_AUTHORITY",
                "core_baseline": "CB-1.13.0",
                "cluster_scope": "EXACT_CLUSTER_RELATION_ONLY",
                "latest_fallback": False,
                "no_total_score": True,
            },
            "query_context_id": _context_id(cluster_id, context_id),
            "cluster_id": cluster_id,
            "batch_id": batch_id,
            "context_id": context_id,
            "filter": {"context_id": context_id},
            "weapon_events": [
                {
                    "weapon_event_id": str(event.get("weapon_event_id")),
                    "category": str(event.get("category", "UNKNOWN")),
                    "t1_session_time_us": str(event.get("t1_session_time_us", "0")),
                    "shooter_entity_id": str(event.get("shooter_entity_id", "")),
                    "target_entity_id": event.get("target_entity_id"),
                    "weapon_terminal_state": str(event.get("weapon_terminal_state", "TERMINAL_UNKNOWN")),
                    "adjudication_state": str(event.get("adjudication_state", "ADJUDICATION_PENDING")),
                    "observation_window_state": str(event.get("observation_window_state", "WINDOW_OPEN")),
                }
                for event in ordered
            ],
            "formation": (
                {
                    "context_id": str(formation.get("context_id", context_id)),
                    "revision_no": int(str(formation.get("revision_no", 1))),
                    "valid_from_session_time_us": str(formation.get("valid_from_session_time_us", "0")),
                    "valid_to_session_time_us": formation.get("valid_to_session_time_us"),
                    "members": formation.get("members", []),
                }
                if formation is not None
                else {
                    "context_id": context_id,
                    "revision_no": None,
                    "members": [],
                    "reason_code": "FORMATION_CONTEXT_NOT_PROVIDED_OR_ABSENT",
                }
            ),
            "dimensions": dimension_facts,
        }
