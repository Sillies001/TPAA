from __future__ import annotations

import pytest

from tpaa_gui.ed2_upper import (
    ED2LinkedDebriefError,
    build_linked_debrief_projection,
)

_SNAPSHOT = "11111111-1111-4111-8111-111111111111"
_RELEASE = "22222222-2222-4222-8222-222222222222"


def _projection() -> dict[str, object]:
    return {
        "schema": "TPAA_ED2_UPPER_PRODUCT_PROJECTION_V1",
        "snapshot_id": _SNAPSHOT,
        "kind": "MEDIA_DEBRIEF",
        "source_release_ids": [_RELEASE],
        "as_of_utc": "2030-01-01T05:00:00Z",
        "logical_content_hash": "a" * 64,
        "frozen": True,
        "mutable_alias_resolution": False,
        "payload": {
            "release_id": _RELEASE,
            "business_recompute": False,
            "mutable_alias_resolution": False,
            "cesium_linked": True,
            "view_2d": True,
            "view_3d": True,
            "semantic_layers": ["W", "P", "A", "J", "M"],
            "timeline": [
                {"session_time_us": 1, "layer": "W", "ref": "world:1"},
                {"session_time_us": 2, "layer": "J", "ref": "event:1"},
            ],
            "media": [],
            "bookmarks": [],
            "playlists": [],
        },
    }


def test_ed2_b3_linked_debrief_is_exact_frozen_presentation_only() -> None:
    value = build_linked_debrief_projection(
        _projection(),
        expected_snapshot_id=_SNAPSHOT,
    )
    assert value.release_id == _RELEASE
    assert value.cesium_linked is True
    assert value.view_2d is True
    assert value.view_3d is True
    assert set(value.semantic_layers) >= {"W", "P", "A", "J", "M"}


def test_ed2_b3_linked_debrief_rejects_alias_and_recompute() -> None:
    with pytest.raises(ED2LinkedDebriefError, match="SNAPSHOT_ID_MISMATCH"):
        build_linked_debrief_projection(
            _projection(),
            expected_snapshot_id="latest",
        )

    payload = _projection()
    body = payload["payload"]
    assert isinstance(body, dict)
    body["business_recompute"] = True
    with pytest.raises(ED2LinkedDebriefError, match="RECOMPUTE_FORBIDDEN"):
        build_linked_debrief_projection(
            payload,
            expected_snapshot_id=_SNAPSHOT,
        )
