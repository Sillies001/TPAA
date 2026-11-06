"""W2 durable immutable Episode manual-revision service."""

from __future__ import annotations

import json
from uuid import UUID, uuid5

from tpaa_application.service import EpisodeRevisionReceipt

from .durable_repositories import RuntimeUnitOfWorkFactory

_EPISODE_REVISION_NAMESPACE = UUID("c0d56c4a-2d89-4776-bd02-129ab84d6d85")
_EPISODE_COLUMNS = (
    "episode_id",
    "session_id",
    "episode_type",
    "mission_type",
    "context_id",
    "start_session_time_us",
    "end_session_time_us",
    "subject_scope",
    "primary_aircraft_id",
    "primary_pilot_id",
    "primary_team_id",
    "aircraft_configuration_snapshot_id",
    "world_capability_code",
    "episode_status",
    "detector_version",
    "coverage",
    "confidence",
    "data_sufficiency_status",
    "supersedes_episode_id",
)


class DurableEpisodeRevisionError(RuntimeError):
    def __init__(self, code: str, detail: str) -> None:
        self.code = code
        self.detail = detail
        super().__init__(f"{code}:{detail}")


def _integer(value: object, *, field: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise DurableEpisodeRevisionError("W2_EPISODE_ROW_INVALID", field)
    return value


class DurableEpisodeRevisionService:
    """Create linked Episode rows; published history is never updated in place."""

    def __init__(self, write_uow_factory: RuntimeUnitOfWorkFactory) -> None:
        self._write_uow_factory = write_uow_factory

    def revise(
        self,
        *,
        episode_id: str,
        correction_key: str,
        start_session_time_us: int,
        end_session_time_us: int,
    ) -> EpisodeRevisionReceipt:
        try:
            parsed = UUID(episode_id)
        except ValueError as exc:
            raise DurableEpisodeRevisionError("W2_EPISODE_ID_INVALID", episode_id) from exc
        if parsed.int == 0 or str(parsed) != episode_id:
            raise DurableEpisodeRevisionError("W2_EPISODE_ID_INVALID", episode_id)
        if not correction_key or correction_key.strip() != correction_key:
            raise DurableEpisodeRevisionError("W2_EPISODE_CORRECTION_KEY_INVALID", correction_key)
        if (
            isinstance(start_session_time_us, bool)
            or isinstance(end_session_time_us, bool)
            or start_session_time_us >= end_session_time_us
        ):
            raise DurableEpisodeRevisionError(
                "W2_EPISODE_INTERVAL_INVALID",
                f"[{start_session_time_us},{end_session_time_us})",
            )

        with self._write_uow_factory() as uow:
            previous = uow.canonical_rows.one(
                "episode.training_episode",
                where={"episode_id": episode_id},
                columns=_EPISODE_COLUMNS,
            )
            if previous is None:
                raise DurableEpisodeRevisionError("W2_EPISODE_NOT_FOUND", episode_id)
            session_id = str(previous["session_id"])
            session = uow.canonical_rows.one(
                "registry.training_session",
                where={"session_id": session_id},
                columns=("start_session_time_us", "end_session_time_us"),
            )
            if session is None:
                raise DurableEpisodeRevisionError("W2_EPISODE_SESSION_NOT_FOUND", session_id)
            session_start = _integer(
                session["start_session_time_us"], field="session.start_session_time_us"
            )
            session_end = _integer(
                session["end_session_time_us"], field="session.end_session_time_us"
            )
            if start_session_time_us < session_start or end_session_time_us > session_end:
                raise DurableEpisodeRevisionError("W2_EPISODE_INTERVAL_OUTSIDE_SESSION", session_id)
            if start_session_time_us == _integer(
                previous["start_session_time_us"], field="start_session_time_us"
            ) and end_session_time_us == _integer(
                previous["end_session_time_us"], field="end_session_time_us"
            ):
                raise DurableEpisodeRevisionError("W2_EPISODE_REVISION_NO_CHANGE", episode_id)
            identity = json.dumps(
                {
                    "supersedes_episode_id": episode_id,
                    "correction_key": correction_key,
                    "start_session_time_us": start_session_time_us,
                    "end_session_time_us": end_session_time_us,
                    "revision_authority": "MANUAL_REVIEW_V1",
                },
                sort_keys=True,
                separators=(",", ":"),
                ensure_ascii=True,
                allow_nan=False,
            )
            revised_id = str(uuid5(_EPISODE_REVISION_NAMESPACE, identity))
            values = {
                key: previous[key]
                for key in _EPISODE_COLUMNS
                if key not in {"episode_id", "supersedes_episode_id"}
            }
            values.update(
                {
                    "episode_id": revised_id,
                    "start_session_time_us": start_session_time_us,
                    "end_session_time_us": end_session_time_us,
                    "episode_status": "REVIEW_REQUIRED",
                    "detector_version": "MANUAL_REVIEW_V1",
                    "supersedes_episode_id": episode_id,
                }
            )
            existing = uow.canonical_rows.one(
                "episode.training_episode",
                where={"episode_id": revised_id},
                columns=_EPISODE_COLUMNS,
            )
            if existing is None:
                uow.canonical_rows.insert("episode.training_episode", values)
            else:
                expected = {key: values[key] for key in _EPISODE_COLUMNS}
                actual = {key: existing[key] for key in _EPISODE_COLUMNS}
                if {key: str(value) for key, value in actual.items()} != {
                    key: str(value) for key, value in expected.items()
                }:
                    raise DurableEpisodeRevisionError("W2_EPISODE_REVISION_CONFLICT", revised_id)
            uow.commit()
        return EpisodeRevisionReceipt(
            episode_id=revised_id,
            supersedes_episode_id=episode_id,
            session_id=session_id,
            episode_status="REVIEW_REQUIRED",
            detector_version="MANUAL_REVIEW_V1",
            start_session_time_us=start_session_time_us,
            end_session_time_us=end_session_time_us,
            correction_key=correction_key,
        )
