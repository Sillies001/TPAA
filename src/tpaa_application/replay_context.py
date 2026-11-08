"""G9 V03 exact replay-context read model and presentation boundary.

The replay context is scoped to one exact Weapon Event. Window anchors come
from the G5 owners. An optional exact-release presentation source may provide
governed trajectory/media references; missing data remains explicit and no
``latest`` alias, random track, or raw media path is accepted.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Protocol, cast

from .weapon_event_application import WeaponEventApplicationError, WeaponEventApplicationService


class ReplayPresentationSource(Protocol):
    """Exact-release presentation projection consumed by the G9 owner."""

    def release_presentation(self, release_id: str) -> dict[str, object]: ...


class ReplayContextError(RuntimeError):
    """Transport-safe, fail-closed G9 error."""

    def __init__(self, code: str, detail: str, *, http_status: int = 422) -> None:
        self.code = code
        self.detail = detail
        self.http_status = http_status
        super().__init__(f"{code}:{detail}")


class ReplayContextApplicationService:
    """Single transport-facing owner of the V03 replay-context read model."""

    def __init__(
        self,
        weapon_events: WeaponEventApplicationService,
        *,
        capability_enabled: bool = True,
        adapter_ready: bool = True,
        presentation_source: ReplayPresentationSource | None = None,
    ) -> None:
        self._weapon_events = weapon_events
        self._capability_enabled = capability_enabled
        self._adapter_ready = adapter_ready
        self._presentation_source = presentation_source

    def capability_state(self) -> str:
        if not self._capability_enabled:
            return "CAPABILITY_DISABLED"
        if not self._adapter_ready:
            return "ADAPTER_UNAVAILABLE"
        return "READY"

    def _require_ready(self) -> None:
        if not self._capability_enabled:
            raise ReplayContextError(
                "CAPABILITY_DISABLED",
                "replay capability is not active for this backend",
                http_status=403,
            )
        if not self._adapter_ready:
            raise ReplayContextError(
                "ADAPTER_UNAVAILABLE",
                "replay backend adapter is not configured",
                http_status=503,
            )

    @staticmethod
    def _mapping(value: object, field: str) -> Mapping[str, object]:
        if not isinstance(value, Mapping):
            raise ReplayContextError(
                "REPLAY_PRESENTATION_INVALID",
                f"{field} must be an object",
                http_status=503,
            )
        return cast(Mapping[str, object], value)

    @staticmethod
    def _session_time(value: object, field: str) -> int:
        if isinstance(value, bool) or not isinstance(value, int) or value < 0:
            raise ReplayContextError(
                "REPLAY_PRESENTATION_INVALID",
                f"{field} must be a non-negative integer Session Time",
                http_status=503,
            )
        return value

    def _presentation_ranges(
        self,
        release_id: str,
        *,
        anchors: tuple[int, ...],
    ) -> tuple[dict[str, object], list[dict[str, object]], str]:
        """Validate and narrow one exact-release presentation projection."""

        if self._presentation_source is None:
            # Preserve the G9 authority's honest pre-admission state for unit
            # compositions that intentionally omit the durable source.
            reason = "MEDIA_PIPELINE_NOT_ADMITTED"
            return ({"state": "N_A", "samples": [], "reason_code": reason}, [], reason)
        try:
            binding = self._presentation_source.release_presentation(release_id)
        except (OSError, RuntimeError, ValueError) as exc:
            raise ReplayContextError(
                "REPLAY_PRESENTATION_UNAVAILABLE",
                "exact-release presentation projection could not be read",
                http_status=503,
            ) from exc
        if binding.get("schema") != "TPAA_RELEASE_PRESENTATION_BINDING_V1":
            raise ReplayContextError(
                "REPLAY_PRESENTATION_INVALID",
                "presentation binding schema is invalid",
                http_status=503,
            )
        if binding.get("release_id") != release_id:
            raise ReplayContextError(
                "REPLAY_PRESENTATION_SCOPE_MISMATCH",
                "presentation binding belongs to another release",
                http_status=503,
            )
        if binding.get("current_latest_fallback_used") is not False:
            raise ReplayContextError(
                "REPLAY_LATEST_FALLBACK_FORBIDDEN",
                "presentation binding used a mutable latest alias",
                http_status=503,
            )
        if binding.get("available") is not True:
            reason = str(binding.get("reason_code") or "REPLAY_PRESENTATION_EMPTY")
            return ({"state": "EMPTY", "samples": [], "reason_code": reason}, [], reason)

        presentation = self._mapping(binding.get("presentation"), "presentation")
        if (
            presentation.get("schema") != "TPAA_TRAJECTORY_PRESENTATION_V1"
            or presentation.get("release_id") != release_id
            or presentation.get("time_semantics") != "SESSION_TIME"
            or presentation.get("business_recompute") is not False
            or presentation.get("persistence_access") is not False
            or presentation.get("mutable_alias_resolution") is not False
        ):
            raise ReplayContextError(
                "REPLAY_PRESENTATION_INVALID",
                "exact-release presentation invariants are invalid",
                http_status=503,
            )
        raw_samples = presentation.get("samples")
        if not isinstance(raw_samples, list):
            raise ReplayContextError(
                "REPLAY_PRESENTATION_INVALID",
                "presentation samples must be a list",
                http_status=503,
            )
        lower = min(anchors)
        upper = max(anchors)
        samples: list[dict[str, object]] = []
        previous: int | None = None
        for index, raw in enumerate(raw_samples):
            sample = self._mapping(raw, f"samples[{index}]")
            session_time = self._session_time(
                sample.get("session_time_us"), f"samples[{index}].session_time_us"
            )
            if previous is not None and session_time < previous:
                raise ReplayContextError(
                    "REPLAY_PRESENTATION_INVALID",
                    "trajectory samples are not ordered by Session Time",
                    http_status=503,
                )
            previous = session_time
            if sample.get("source_release_id") != release_id:
                raise ReplayContextError(
                    "REPLAY_PRESENTATION_SCOPE_MISMATCH",
                    "trajectory sample belongs to another release",
                    http_status=503,
                )
            latitude = sample.get("latitude_deg")
            longitude = sample.get("longitude_deg")
            if (
                isinstance(latitude, bool)
                or not isinstance(latitude, (int, float))
                or isinstance(longitude, bool)
                or not isinstance(longitude, (int, float))
                or not -90.0 <= float(latitude) <= 90.0
                or not -180.0 <= float(longitude) <= 180.0
            ):
                raise ReplayContextError(
                    "REPLAY_PRESENTATION_INVALID",
                    "trajectory coordinate is invalid",
                    http_status=503,
                )
            if lower <= session_time <= upper:
                samples.append(
                    {
                        "session_time_us": str(session_time),
                        "latitude_deg": float(latitude),
                        "longitude_deg": float(longitude),
                        "altitude_m": sample.get("altitude_m"),
                        "evidence_ref": sample.get("evidence_ref"),
                    }
                )

        raw_media = presentation.get("media")
        if not isinstance(raw_media, list):
            raise ReplayContextError(
                "REPLAY_PRESENTATION_INVALID",
                "presentation media must be a list",
                http_status=503,
            )
        media: list[dict[str, object]] = []
        for index, raw in enumerate(raw_media):
            item = self._mapping(raw, f"media[{index}]")
            if item.get("source_release_id") != release_id:
                raise ReplayContextError(
                    "REPLAY_PRESENTATION_SCOPE_MISMATCH",
                    "media reference belongs to another release",
                    http_status=503,
                )
            media_id = item.get("media_id")
            media_type = item.get("media_type")
            if not isinstance(media_id, str) or not media_id or not isinstance(media_type, str):
                raise ReplayContextError(
                    "REPLAY_PRESENTATION_INVALID",
                    "media identity is invalid",
                    http_status=503,
                )
            # Raw paths/URLs never cross the Application boundary. Playback must
            # obtain a separately authorized, opaque, short-lived range ticket.
            media.append(
                {
                    "media_id": media_id,
                    "media_type": media_type,
                    "evidence_ref": item.get("evidence_ref"),
                    "ticket_required": True,
                }
            )
        state = "READY" if samples else "EMPTY"
        reason = "READY" if samples or media else "REPLAY_WINDOW_HAS_NO_PRESENTATION_DATA"
        return (
            {
                "state": state,
                "samples": samples,
                "time_semantics": "SESSION_TIME",
                "reason_code": reason,
            },
            media,
            reason,
        )

    def context(
        self,
        weapon_event_id: str,
        *,
        request_id: str,
        release_id: str,
        context_id: str,
        perspective: str,
    ) -> dict[str, object]:
        self._require_ready()
        if self._weapon_events.capability_state() != "READY":
            raise ReplayContextError(
                "ADAPTER_UNAVAILABLE",
                "weapon-event read model is not READY",
                http_status=503,
            )
        try:
            scope = self._weapon_events.resource_scope(weapon_event_id)
            if not release_id or not context_id:
                raise ReplayContextError(
                    "REPLAY_EXACT_CONTEXT_REQUIRED",
                    "release_id and context_id are required",
                    http_status=422,
                )
            if scope.release_id is None or scope.context_id is None:
                raise ReplayContextError(
                    "REPLAY_SOURCE_CONTEXT_UNBOUND",
                    "weapon event is not bound to an exact release/context",
                    http_status=409,
                )
            if scope.release_id != release_id or scope.context_id != context_id:
                raise ReplayContextError(
                    "REPLAY_SCOPE_MISMATCH",
                    "requested release/context does not own this weapon event",
                    http_status=422,
                )
            detail = self._weapon_events.detail(weapon_event_id)
            window = self._weapon_events.window(weapon_event_id, perspective)
        except ReplayContextError:
            raise
        except WeaponEventApplicationError as exc:
            code = exc.code if exc.code == "WEAPON_EVENT_NOT_FOUND" else "REPLAY_SOURCE_INVALID"
            raise ReplayContextError(code, exc.detail, http_status=exc.http_status) from exc

        anchor_values = [int(str(detail["t1_session_time_us"]))]
        for value in (window["t2_session_time_us"], window["t3_session_time_us"]):
            if value is not None:
                anchor_values.append(int(str(value)))
        trajectory, media_ranges, reason = self._presentation_ranges(
            release_id,
            anchors=tuple(anchor_values),
        )
        presentation_ready = trajectory["state"] == "READY" or bool(media_ranges)
        return {
            "schema": "TPAA_G9_REPLAY_CONTEXT_V1",
            "reason_code": reason,
            "request_id": request_id,
            "provenance": {
                "authority_id": "GUI_REPLAY_AUTHORITY",
                "core_baseline": "CB-1.14.0",
                "exact_we_scope": True,
                "latest_fallback": False,
                "media_available": bool(media_ranges),
                "trajectory_available": trajectory["state"] == "READY",
            },
            "weapon_event_id": str(detail["weapon_event_id"]),
            "batch_id": str(detail["batch_id"]),
            "release_id": release_id,
            "context_id": context_id,
            "perspective": perspective,
            "t1_session_time_us": str(detail["t1_session_time_us"]),
            "t2_session_time_us": window["t2_session_time_us"],
            "t3_session_time_us": window["t3_session_time_us"],
            "window_state": str(window["window_state"]),
            "ranges": {
                "trajectory": trajectory,
                "media_ranges": media_ranges,
                "reason_code": reason,
                "note": "仅呈现精确 Release 的 Session Time 数据；缺失和漂移显式暴露。",
            },
            "media_ranges": {
                "items": media_ranges,
                "reason_code": "READY" if media_ranges else reason,
                "ticket_required": bool(media_ranges),
            },
            "presentation_state": "READY" if presentation_ready else trajectory["state"],
        }
