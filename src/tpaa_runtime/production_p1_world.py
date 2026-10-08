"""Frozen ED2-CONFORMANCE B1 World authority policy for production P1."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Final, cast

from tpaa_ingest import SourceFamily

PRODUCTION_P1_WORLD_POLICY_SCHEMA: Final = (
    "TPAA_ED2_P1_WORLD_AUTHORITY_POLICY_V1"
)
PRODUCTION_P1_WORLD_POLICY_VERSION: Final = "1.0.0"
PRODUCTION_P1_WORLD_CAPABILITY_CODE: Final = "BASIC_CORE"
PRODUCTION_P1_REQUIRED_WORLD_LETTERS: Final = ("C", "W", "A", "M")
PRODUCTION_P1_WORLD_KIND_BY_LETTER: Final = {
    "C": "CONTEXT",
    "W": "TRUTH",
    "A": "ACTION",
    "M": "MACHINE",
}
PRODUCTION_P1_WORLD_SOURCE_FAMILIES: Final = {
    "CONTEXT": frozenset({SourceFamily.SCENARIO}),
    "TRUTH": frozenset(
        {
            SourceFamily.FLIGHT,
            SourceFamily.RANGE_ACMI,
            SourceFamily.SCENARIO,
        }
    ),
    "ACTION": frozenset({SourceFamily.FLIGHT}),
    "MACHINE": frozenset(
        {
            SourceFamily.MISSION_AVIONICS,
            SourceFamily.TDL,
            SourceFamily.RANGE_ACMI,
            SourceFamily.SCENARIO,
        }
    ),
}


class ProductionP1WorldPolicyError(RuntimeError):
    """Fail-closed frozen World authority error."""

    def __init__(self, code: str, detail: str) -> None:
        self.code = code
        self.detail = detail
        super().__init__(f"{code}:{detail}")


def _mapping(value: object, *, field: str) -> dict[str, object]:
    if not isinstance(value, dict) or not all(
        isinstance(key, str) for key in value
    ):
        raise ProductionP1WorldPolicyError(
            "ED2_P1_WORLD_AUTHORITY_INVALID",
            field,
        )
    return cast(dict[str, object], value)


def validate_production_p1_world_authority(
    authority_root: Path,
) -> None:
    """Require CB-1.4.0 BASIC_CORE to remain exact C/W/A/M."""

    path = authority_root / "WORLD_CAPABILITY_REGISTRY.json"
    try:
        raw: object = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise ProductionP1WorldPolicyError(
            "ED2_P1_WORLD_AUTHORITY_INVALID",
            path.as_posix(),
        ) from exc
    registry = _mapping(raw, field="WORLD_CAPABILITY_REGISTRY")
    if (
        registry.get("registry_id") != "WORLD_CAPABILITY_REGISTRY"
        or registry.get("version") != "1.0.0"
        or registry.get("core_baseline") != "CB-1.4.0"
    ):
        raise ProductionP1WorldPolicyError(
            "ED2_P1_WORLD_AUTHORITY_DRIFT",
            repr(
                (
                    registry.get("registry_id"),
                    registry.get("version"),
                    registry.get("core_baseline"),
                )
            ),
        )
    capabilities = _mapping(
        registry.get("capabilities"),
        field="WORLD_CAPABILITY_REGISTRY.capabilities",
    )
    basic = _mapping(
        capabilities.get(PRODUCTION_P1_WORLD_CAPABILITY_CODE),
        field=(
            "WORLD_CAPABILITY_REGISTRY.capabilities."
            f"{PRODUCTION_P1_WORLD_CAPABILITY_CODE}"
        ),
    )
    required = basic.get("required")
    if (
        not isinstance(required, list)
        or tuple(required) != PRODUCTION_P1_REQUIRED_WORLD_LETTERS
    ):
        raise ProductionP1WorldPolicyError(
            "ED2_P1_WORLD_CAPABILITY_DRIFT",
            repr(required),
        )
