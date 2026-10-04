from __future__ import annotations

import pytest

from tpaa_gui.visualization import (
    VisualizationPresentationError,
    build_2d_polyline,
    build_cesium_trajectory_packets,
    build_trajectory_presentation,
)


def _payload() -> dict[str, object]:
    return {
        "schema": "TPAA_TRAJECTORY_PRESENTATION_V1",
        "release_id": "11111111-1111-4111-8111-111111111111",
        "time_semantics": "SESSION_TIME",
        "business_recompute": False,
        "persistence_access": False,
        "mutable_alias_resolution": False,
        "samples": [
            {
                "session_time_us": 1_000_000,
                "latitude_deg": 34.0,
                "longitude_deg": -117.0,
                "altitude_m": 1000.0,
                "source_release_id": "11111111-1111-4111-8111-111111111111",
                "evidence_ref": "evidence:1",
            },
            {
                "session_time_us": 2_000_000,
                "latitude_deg": 34.1,
                "longitude_deg": -116.9,
                "altitude_m": 1100.0,
                "source_release_id": "11111111-1111-4111-8111-111111111111",
                "evidence_ref": "evidence:2",
            },
        ],
        "media": [
            {
                "media_id": "media-1",
                "media_type": "VIDEO",
                "uri": "tpaa-media://media-1",
                "source_release_id": "11111111-1111-4111-8111-111111111111",
                "evidence_ref": "evidence:1",
            }
        ],
    }


def test_exact_release_payload_builds_2d_and_cesium_ready_views() -> None:
    presentation = build_trajectory_presentation(
        _payload(),
        expected_release_id="11111111-1111-4111-8111-111111111111",
    )

    assert build_2d_polyline(presentation) == ((-117.0, 34.0), (-116.9, 34.1))
    packets = build_cesium_trajectory_packets(presentation)
    assert packets[0]["properties"] == {
        "tpaaTimeSemantics": "SESSION_TIME_RELATIVE_ONLY",
        "tpaaReleaseId": "11111111-1111-4111-8111-111111111111",
    }
    assert packets[1]["properties"] == {
        "tpaaRelativeEpochIsNotUtcFact": True,
        "tpaaSessionTimeOriginUs": 1_000_000,
        "tpaaReleaseId": "11111111-1111-4111-8111-111111111111",
    }


def test_visualization_fails_closed_on_release_alias_and_time_order() -> None:
    with pytest.raises(VisualizationPresentationError, match="RELEASE_ID_MISMATCH"):
        build_trajectory_presentation(_payload(), expected_release_id="latest")

    payload = _payload()
    samples = payload["samples"]
    assert isinstance(samples, list)
    first = samples[0]
    second = samples[1]
    assert isinstance(first, dict) and isinstance(second, dict)
    first["session_time_us"] = 3_000_000
    second["session_time_us"] = 2_000_000
    with pytest.raises(VisualizationPresentationError, match="SAMPLE_TIME_ORDER"):
        build_trajectory_presentation(
            payload,
            expected_release_id="11111111-1111-4111-8111-111111111111",
        )


def test_visualization_rejects_business_or_persistence_authority() -> None:
    payload = _payload()
    payload["business_recompute"] = True
    with pytest.raises(VisualizationPresentationError, match="RECOMPUTE"):
        build_trajectory_presentation(
            payload,
            expected_release_id="11111111-1111-4111-8111-111111111111",
        )

    payload = _payload()
    payload["persistence_access"] = True
    with pytest.raises(VisualizationPresentationError, match="PERSISTENCE"):
        build_trajectory_presentation(
            payload,
            expected_release_id="11111111-1111-4111-8111-111111111111",
        )
