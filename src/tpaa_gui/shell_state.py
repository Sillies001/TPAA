"""Qt-independent global selection state for the W4 application shell."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, replace
from typing import Any, cast

from .page_contract import page_contract


class ShellStateError(ValueError):
    """Stable fail-closed shell-state error."""


@dataclass(frozen=True, slots=True)
class ShellSelection:
    page_id: str = "P01"
    session_id: str | None = None
    episode_id: str | None = None
    stage_id: str | None = None
    context_id: str | None = None
    context_version: str | None = None
    revision_no: int | None = None
    time_start_us: int | None = None
    time_end_us: int | None = None
    truth_entity_id: str | None = None
    observer_id: str | None = None
    actor_id: str | None = None
    aircraft_id: str | None = None
    configuration_id: str | None = None
    objective_id: str | None = None
    event_id: str | None = None
    metric_instance_id: str | None = None
    observation_id: str | None = None
    attribution_id: str | None = None
    relation_id: str | None = None
    chain_id: str | None = None
    release_id: str | None = None
    playback: str = "PAUSED"

    def validate(self) -> None:
        page_contract(self.page_id)
        if self.episode_id is not None and self.session_id is None:
            raise ShellStateError("W4_EPISODE_REQUIRES_SESSION")
        if self.stage_id is not None and self.episode_id is None:
            raise ShellStateError("W4_STAGE_REQUIRES_EPISODE")
        if (self.context_version is not None or self.revision_no is not None) and self.context_id is None:
            raise ShellStateError("W4_CONTEXT_VERSION_REQUIRES_EXACT_ID")
        time_values = (self.time_start_us, self.time_end_us)
        if (time_values[0] is None) != (time_values[1] is None):
            raise ShellStateError("W4_TIME_RANGE_INCOMPLETE")
        if time_values[0] is not None and time_values[1] is not None:
            if time_values[0] < 0 or time_values[1] <= time_values[0]:
                raise ShellStateError("W4_TIME_RANGE_INVALID")
        if self.playback not in {"PAUSED", "PLAYING", "SCRUBBING"}:
            raise ShellStateError("W4_PLAYBACK_INVALID")


ShellStateListener = Callable[[ShellSelection, frozenset[str]], None]


class ApplicationShellState:
    """Single observable state shared by navigation, workspace, and evidence drawer."""

    def __init__(self, initial: ShellSelection | None = None) -> None:
        self._selection = initial or ShellSelection()
        self._selection.validate()
        self._listeners: list[ShellStateListener] = []

    @property
    def selection(self) -> ShellSelection:
        return self._selection

    def subscribe(self, listener: ShellStateListener) -> Callable[[], None]:
        self._listeners.append(listener)

        def unsubscribe() -> None:
            if listener in self._listeners:
                self._listeners.remove(listener)

        return unsubscribe

    def update(self, **changes: object) -> ShellSelection:
        unknown = set(changes) - set(ShellSelection.__dataclass_fields__)
        if unknown:
            raise ShellStateError(f"W4_SELECTION_FIELD_UNKNOWN:{','.join(sorted(unknown))}")
        replace_selection = cast(Any, replace)
        candidate = cast(ShellSelection, replace_selection(self._selection, **changes))
        candidate.validate()
        changed = frozenset(
            name
            for name in ShellSelection.__dataclass_fields__
            if getattr(candidate, name) != getattr(self._selection, name)
        )
        if not changed:
            return self._selection
        self._selection = candidate
        for listener in tuple(self._listeners):
            listener(candidate, changed)
        return candidate

    def select_page(self, page_id: str) -> ShellSelection:
        return self.update(page_id=page_id)

    def select_session(self, session_id: str | None) -> ShellSelection:
        return self.update(
            session_id=session_id,
            episode_id=None,
            stage_id=None,
            time_start_us=None,
            time_end_us=None,
            event_id=None,
            metric_instance_id=None,
            observation_id=None,
            attribution_id=None,
            relation_id=None,
            chain_id=None,
            release_id=None,
        )

    def select_episode(self, episode_id: str | None) -> ShellSelection:
        if episode_id is not None and self._selection.session_id is None:
            raise ShellStateError("W4_EPISODE_REQUIRES_SESSION")
        return self.update(
            episode_id=episode_id,
            stage_id=None,
            time_start_us=None,
            time_end_us=None,
            event_id=None,
            metric_instance_id=None,
            observation_id=None,
            attribution_id=None,
            relation_id=None,
            chain_id=None,
        )

    def select_stage(self, stage_id: str | None) -> ShellSelection:
        if stage_id is not None and self._selection.episode_id is None:
            raise ShellStateError("W4_STAGE_REQUIRES_EPISODE")
        return self.update(stage_id=stage_id)


__all__ = ["ApplicationShellState", "ShellSelection", "ShellStateError"]
