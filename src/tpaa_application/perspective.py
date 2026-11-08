"""G5 Perspective projection unique owner: shooter/target authorized read model.

V04/V05/V08/V20 support shooter and target perspectives; V06/V21 (Strike) are
shooter-only and their target perspective is always fail-closed as not-applicable.
Perspective changes projection and UI only — it never changes events, shooter/target,
or formal adjudication facts.  Missing geometry/series surface as explicit unavailable
states rather than fabricated defaults.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from .weapon_event import WeaponCategory, WeaponEvent

PROJECTION_VERSION = "WE-PERSPECTIVE-1.0.0"


class Perspective(StrEnum):
    SHOOTER = "shooter"
    TARGET = "target"


class PerspectiveDenial(StrEnum):
    NOT_APPLICABLE_STRIKE_TARGET = "NOT_APPLICABLE_STRIKE_TARGET"
    TARGET_PROJECTION_UNAVAILABLE = "TARGET_PROJECTION_UNAVAILABLE"
    CATEGORY_NOT_RECOGNISED = "CATEGORY_NOT_RECOGNISED"


@dataclass(frozen=True, slots=True)
class PerspectiveInput:
    geometry_available: bool
    series_available: bool
    target_side_projection_available: bool


@dataclass(frozen=True, slots=True)
class PerspectiveProjection:
    weapon_event_id: str
    perspective: Perspective
    projection_version: str
    allowed: bool
    denial_reason: str | None
    geometry_available: bool
    series_available: bool


class PerspectiveService:
    """Single owner of shooter/target, individual/team projections for a WE."""

    def project(
        self,
        event: WeaponEvent,
        perspective: Perspective,
        availability: PerspectiveInput,
    ) -> PerspectiveProjection:
        if event.category is WeaponCategory.UNKNOWN:
            return self._deny(event, perspective, PerspectiveDenial.CATEGORY_NOT_RECOGNISED, availability)
        if perspective is Perspective.TARGET:
            if event.category is WeaponCategory.STRIKE:
                # Strike target perspective is always fail-closed as not applicable.
                return self._deny(event, perspective, PerspectiveDenial.NOT_APPLICABLE_STRIKE_TARGET, availability)
            if not availability.target_side_projection_available:
                return self._deny(event, perspective, PerspectiveDenial.TARGET_PROJECTION_UNAVAILABLE, availability)
        return PerspectiveProjection(
            weapon_event_id=event.weapon_event_id,
            perspective=perspective,
            projection_version=PROJECTION_VERSION,
            allowed=True,
            denial_reason=None,
            # Missing geometry/series are surfaced as unavailable, never fabricated.
            geometry_available=availability.geometry_available,
            series_available=availability.series_available,
        )

    @staticmethod
    def _deny(
        event: WeaponEvent,
        perspective: Perspective,
        reason: PerspectiveDenial,
        availability: PerspectiveInput,
    ) -> PerspectiveProjection:
        return PerspectiveProjection(
            weapon_event_id=event.weapon_event_id,
            perspective=perspective,
            projection_version=PROJECTION_VERSION,
            allowed=False,
            denial_reason=reason.value,
            geometry_available=availability.geometry_available,
            series_available=availability.series_available,
        )
