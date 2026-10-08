"""Load the packaged ED-2.0 full-P1 qualification request contract."""

from __future__ import annotations

import json
from pathlib import Path
from typing import cast

ED2_P1_REQUEST_CONTRACT_SCHEMA = "TPAA_ED2_B1_FULL_P1_REQUEST_CONTRACT_V1"


def load_ed2_p1_request_contract(path: Path) -> dict[str, object]:
    """Read one packaged qualification-only request contract fail closed."""

    if not path.is_file():
        raise RuntimeError(
            f"production P1 qualification contract unavailable: {path}"
        )
    try:
        raw: object = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise RuntimeError(
            "production P1 qualification contract is unreadable"
        ) from exc
    if not isinstance(raw, dict) or not all(
        isinstance(key, str) for key in raw
    ):
        raise RuntimeError(
            "production P1 qualification contract must be a JSON object"
        )
    payload = dict(cast(dict[str, object], raw))
    if payload.get("schema") != ED2_P1_REQUEST_CONTRACT_SCHEMA:
        raise RuntimeError("production P1 qualification contract schema drift")
    for field in (
        "p1_catalog_inputs",
        "mission_system_instances",
        "metric_system_bindings",
    ):
        if not isinstance(payload.get(field), dict):
            raise RuntimeError(
                f"production P1 qualification contract field invalid: {field}"
            )
    return payload
