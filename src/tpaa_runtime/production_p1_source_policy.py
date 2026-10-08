"""Frozen ED2-CONFORMANCE B1 source-family policy for production P1."""

from __future__ import annotations

from typing import Final

from tpaa_ingest import SourceFamily

PRODUCTION_P1_SOURCE_POLICY_SCHEMA: Final = (
    "TPAA_ED2_P1_SOURCE_FAMILY_POLICY_V1"
)
PRODUCTION_P1_SOURCE_POLICY_VERSION: Final = "1.0.0"

_POLICY: Final = {
    "REFERENCE_TRUTH": frozenset(
        {
            SourceFamily.FLIGHT,
            SourceFamily.RANGE_ACMI,
            SourceFamily.SCENARIO,
        }
    ),
    "TIME_ALIGNMENT": frozenset(
        {
            SourceFamily.FLIGHT,
            SourceFamily.RANGE_ACMI,
            SourceFamily.SCENARIO,
        }
    ),
    "AIRCRAFT_FLIGHT": frozenset(
        {SourceFamily.FLIGHT, SourceFamily.SCENARIO}
    ),
    "AIRCRAFT_ENERGY": frozenset(
        {SourceFamily.FLIGHT, SourceFamily.SCENARIO}
    ),
    "AIRCRAFT_CONTROL_RESPONSE": frozenset(
        {SourceFamily.FLIGHT, SourceFamily.SCENARIO}
    ),
    "AIRCRAFT_HANDLING": frozenset(
        {SourceFamily.FLIGHT, SourceFamily.SCENARIO}
    ),
    "AIRCRAFT_PERSISTENCE": frozenset(
        {SourceFamily.FLIGHT, SourceFamily.SCENARIO}
    ),
    "SENSOR_DETECTION": frozenset(
        {
            SourceFamily.MISSION_AVIONICS,
            SourceFamily.RANGE_ACMI,
            SourceFamily.SCENARIO,
        }
    ),
    "SENSOR_ACCURACY": frozenset(
        {
            SourceFamily.MISSION_AVIONICS,
            SourceFamily.RANGE_ACMI,
            SourceFamily.SCENARIO,
        }
    ),
    "TRACK_PERFORMANCE": frozenset(
        {
            SourceFamily.MISSION_AVIONICS,
            SourceFamily.RANGE_ACMI,
            SourceFamily.SCENARIO,
        }
    ),
    "ASSOCIATION_IDENTIFICATION": frozenset(
        {
            SourceFamily.MISSION_AVIONICS,
            SourceFamily.RANGE_ACMI,
            SourceFamily.SCENARIO,
        }
    ),
    "PASSIVE_SENSOR": frozenset(
        {
            SourceFamily.MISSION_AVIONICS,
            SourceFamily.RANGE_ACMI,
            SourceFamily.SCENARIO,
        }
    ),
    "RWR_ESM": frozenset(
        {
            SourceFamily.MISSION_AVIONICS,
            SourceFamily.RANGE_ACMI,
            SourceFamily.SCENARIO,
        }
    ),
    "DATALINK": frozenset(
        {
            SourceFamily.TDL,
            SourceFamily.RANGE_ACMI,
            SourceFamily.SCENARIO,
        }
    ),
    "SENSOR_FUSION": frozenset(
        {
            SourceFamily.MISSION_AVIONICS,
            SourceFamily.RANGE_ACMI,
            SourceFamily.SCENARIO,
        }
    ),
}


def production_p1_source_family_policy() -> dict[str, frozenset[SourceFamily]]:
    """Return an immutable-value copy of the frozen B1 family policy."""

    return dict(_POLICY)


def production_p1_required_source_families(
    metric_family: str,
) -> frozenset[SourceFamily]:
    """Resolve one Catalog family or fail without a fallback."""

    try:
        return _POLICY[metric_family]
    except KeyError as exc:
        raise KeyError(
            f"ED2_P1_SOURCE_LINEAGE_POLICY_MISSING:{metric_family}"
        ) from exc
