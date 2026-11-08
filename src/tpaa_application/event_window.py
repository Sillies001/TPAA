"""G5 Event Window unique owner: side-specific, versioned, rebuildable projection.

Each WE has independent shooter/target windows over the half-open interval [start, end).
Windows may overlap within an Episode; they are never force-sliced by a prior event.
Weapon terminal, adjudication and observation-window are three independent state
dimensions.  `TERMINAL_UNKNOWN`, `RESULT_PENDING` and `ALIGNMENT_UNRESOLVED` are distinct.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

WINDOW_RESOLVER_VERSION = "WE-WINDOW-1.0.0"


class WindowPerspective(StrEnum):
    SHOOTER = "shooter"
    TARGET = "target"


class WindowTerminalState(StrEnum):
    TERMINAL_KNOWN = "TERMINAL_KNOWN"
    TERMINAL_UNKNOWN = "TERMINAL_UNKNOWN"


class WindowAdjudicationState(StrEnum):
    ADJUDICATED = "ADJUDICATED"
    ADJUDICATION_PENDING = "ADJUDICATION_PENDING"


class WindowState(StrEnum):
    WINDOW_OPEN = "WINDOW_OPEN"
    WINDOW_PARTIAL = "WINDOW_PARTIAL"
    WINDOW_CLOSED = "WINDOW_CLOSED"


class AlignmentState(StrEnum):
    ALIGNED = "ALIGNED"
    ALIGNMENT_UNRESOLVED = "ALIGNMENT_UNRESOLVED"


class EventWindowError(RuntimeError):
    def __init__(self, code: str, detail: str) -> None:
        self.code = code
        self.detail = detail
        super().__init__(f"{code}:{detail}")


@dataclass(frozen=True, slots=True)
class WindowAnchorInput:
    """Authoritative anchor observations for one WE on one side."""

    t0s_session_time_us: int | None  # shooter-side context start
    t0t_session_time_us: int | None  # target-side threat-context start (not first cue)
    t1_session_time_us: int          # actual launch/release
    t2_session_time_us: int | None   # authoritative weapon termination; None => unknown
    t3_session_time_us: int | None   # result-observation end / coverage boundary
    cue_session_time_us: int | None  # target-side first available threat cue
    response_session_time_us: int | None  # first observable defensive response
    j_session_time_us: int | None    # approved adjudication time (may be after T2)
    alignment_unresolved: bool = False
    clock_gap_after_t1: bool = False


@dataclass(frozen=True, slots=True)
class EventWindow:
    weapon_event_id: str
    perspective: WindowPerspective
    resolver_version: str
    start_session_time_us: int
    end_session_time_us: int | None
    t0s_session_time_us: int | None
    t0t_session_time_us: int | None
    t1_session_time_us: int
    t2_session_time_us: int | None
    t3_session_time_us: int | None
    cue_session_time_us: int | None
    response_session_time_us: int | None
    j_session_time_us: int | None
    terminal_state: WindowTerminalState
    adjudication_state: WindowAdjudicationState
    window_state: WindowState
    alignment_state: AlignmentState
    coverage: str
    reason: str | None

    def contains(self, session_time_us: int) -> bool:
        """Half-open [start, end): start inclusive, end exclusive."""

        if session_time_us < self.start_session_time_us:
            return False
        return self.end_session_time_us is None or session_time_us < self.end_session_time_us


def resolve_window(
    weapon_event_id: str,
    perspective: WindowPerspective,
    anchors: WindowAnchorInput,
) -> EventWindow:
    """Resolve one side-specific window.  Fail-closed on unresolved alignment."""

    if anchors.t1_session_time_us < 0:
        raise EventWindowError("WINDOW_INVALID", "t1 must be non-negative session time")
    if anchors.alignment_unresolved:
        alignment = AlignmentState.ALIGNMENT_UNRESOLVED
    else:
        alignment = AlignmentState.ALIGNED

    # Side-specific start: never treat the first cue as T0-T.
    if perspective is WindowPerspective.SHOOTER:
        start = anchors.t0s_session_time_us if anchors.t0s_session_time_us is not None else anchors.t1_session_time_us
    else:
        start = anchors.t0t_session_time_us if anchors.t0t_session_time_us is not None else (
            anchors.cue_session_time_us if anchors.cue_session_time_us is not None else anchors.t1_session_time_us
        )

    # End: T2 when authoritatively known, else T3 coverage boundary, else open.
    end = anchors.t2_session_time_us
    if end is None:
        end = anchors.t3_session_time_us

    terminal = (
        WindowTerminalState.TERMINAL_KNOWN
        if anchors.t2_session_time_us is not None
        else WindowTerminalState.TERMINAL_UNKNOWN
    )
    adjudication = (
        WindowAdjudicationState.ADJUDICATED
        if anchors.j_session_time_us is not None
        else WindowAdjudicationState.ADJUDICATION_PENDING
    )
    if end is None:
        window_state = WindowState.WINDOW_OPEN
    elif start < end:
        window_state = WindowState.WINDOW_CLOSED
    else:
        window_state = WindowState.WINDOW_PARTIAL

    if alignment is AlignmentState.ALIGNMENT_UNRESOLVED:
        coverage = "UNRESOLVED"
        reason = "ALIGNMENT_UNRESOLVED"
    elif anchors.clock_gap_after_t1:
        coverage = "PARTIAL_GAP"
        reason = "CLOCK_GAP_AFTER_T1"
    elif end is None:
        coverage = "OPEN_END"
        reason = "TERMINAL_UNKNOWN_OPEN"
    else:
        coverage = "FULL"
        reason = None

    return EventWindow(
        weapon_event_id=weapon_event_id,
        perspective=perspective,
        resolver_version=WINDOW_RESOLVER_VERSION,
        start_session_time_us=start,
        end_session_time_us=end,
        t0s_session_time_us=anchors.t0s_session_time_us,
        t0t_session_time_us=anchors.t0t_session_time_us,
        t1_session_time_us=anchors.t1_session_time_us,
        t2_session_time_us=anchors.t2_session_time_us,
        t3_session_time_us=anchors.t3_session_time_us,
        cue_session_time_us=anchors.cue_session_time_us,
        response_session_time_us=anchors.response_session_time_us,
        j_session_time_us=anchors.j_session_time_us,
        terminal_state=terminal,
        adjudication_state=adjudication,
        window_state=window_state,
        alignment_state=alignment,
        coverage=coverage,
        reason=reason,
    )


def windows_overlap(left: EventWindow, right: EventWindow) -> bool:
    """Half-open interval overlap; open-ended windows overlap any point >= start."""

    if left.end_session_time_us is not None and right.start_session_time_us >= left.end_session_time_us:
        return False
    if right.end_session_time_us is not None and left.start_session_time_us >= right.end_session_time_us:
        return False
    return True
