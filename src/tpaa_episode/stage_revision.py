"""M1-WORLD-005 immutable Stage revision/supersede behavior."""

from __future__ import annotations

import json
from dataclasses import replace
from uuid import UUID, uuid5

from tpaa_episode.stage_quality import QualifiedBasicFlightStage

STAGE_REVISION_NAMESPACE = UUID("dc7b1880-9156-47f0-980f-828661d946aa")


class StageRevisionError(RuntimeError):
    """Deterministic fail-closed Stage revision error."""

    def __init__(self, code: str, detail: str) -> None:
        super().__init__(f"{code}: {detail}")
        self.code = code
        self.detail = detail


def supersede_stage(
    previous: QualifiedBasicFlightStage,
    *,
    correction_key: str,
    start_session_time_us: int | None = None,
    end_session_time_us: int | None = None,
) -> QualifiedBasicFlightStage:
    """Return a new Stage row linked to ``previous`` without mutating history."""

    if not correction_key.strip():
        raise StageRevisionError("M1_STAGE_CORRECTION_KEY_INVALID", repr(correction_key))
    start = (
        previous.start_session_time_us if start_session_time_us is None else start_session_time_us
    )
    end = previous.end_session_time_us if end_session_time_us is None else end_session_time_us
    if (
        isinstance(start, bool)
        or isinstance(end, bool)
        or not isinstance(start, int)
        or not isinstance(end, int)
    ):
        raise StageRevisionError("M1_STAGE_REVISION_INTERVAL_INVALID", f"[{start!r},{end!r})")
    if start >= end:
        raise StageRevisionError("M1_STAGE_REVISION_INTERVAL_INVALID", f"[{start},{end})")

    identity = {
        "previous_stage_id": previous.stage_id,
        "episode_id": previous.episode_id,
        "stage_type": previous.stage_type,
        "stage_order": previous.stage_order,
        "start_session_time_us": start,
        "end_session_time_us": end,
        "detector_version": previous.detector_version,
        "correction_key": correction_key,
    }
    canonical = json.dumps(
        identity,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
        allow_nan=False,
    )
    revised_id = str(uuid5(STAGE_REVISION_NAMESPACE, canonical))
    return replace(
        previous,
        stage_id=revised_id,
        start_session_time_us=start,
        end_session_time_us=end,
        supersedes_stage_id=previous.stage_id,
    )
