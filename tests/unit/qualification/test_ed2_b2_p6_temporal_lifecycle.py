"""ED2 B2 P6 qualification separates model cutoff from forecast knowledge time."""

from __future__ import annotations

from collections.abc import Mapping
from typing import cast

import pytest

from tools.testing.ed2_b2_continuous_input_builder import (
    build_ed2_b2_continuous_qualification_plan,
    verify_p6_temporal_lifecycle,
)


def test_ed2_b2_p6_plan_uses_separate_training_and_forecast_cutoffs() -> None:
    plan = build_ed2_b2_continuous_qualification_plan()
    raw = plan["p6_profile"]
    assert isinstance(raw, Mapping)
    profile = cast(Mapping[str, object], raw)
    verify_p6_temporal_lifecycle(profile)
    assert profile["model_as_of_utc"] == "2030-01-01T05:00:00Z"
    assert profile["trained_at_utc"] == "2030-01-01T05:01:00Z"
    assert profile["sealed_at_utc"] == "2030-01-01T05:02:00Z"
    assert profile["forecast_origin_utc"] == "2030-01-01T05:03:00Z"
    assert profile["as_of_utc"] == "2030-01-01T05:03:00Z"


def test_ed2_b2_run717_collapsed_p6_timeline_fails_preflight() -> None:
    with pytest.raises(ValueError, match="P6_TEMPORAL_LIFECYCLE_INVALID"):
        verify_p6_temporal_lifecycle(
            {
                "model_as_of_utc": "2030-01-01T05:00:00Z",
                "trained_at_utc": "2030-01-01T05:01:00Z",
                "sealed_at_utc": "2030-01-01T05:02:00Z",
                "forecast_origin_utc": "2030-01-01T05:00:00Z",
                "as_of_utc": "2030-01-01T05:00:00Z",
            }
        )


def test_ed2_b2_model_training_cannot_precede_its_knowledge_cutoff() -> None:
    with pytest.raises(ValueError, match="P6_TEMPORAL_LIFECYCLE_INVALID"):
        verify_p6_temporal_lifecycle(
            {
                "model_as_of_utc": "2030-01-01T05:02:00Z",
                "trained_at_utc": "2030-01-01T05:01:00Z",
                "sealed_at_utc": "2030-01-01T05:03:00Z",
                "forecast_origin_utc": "2030-01-01T05:04:00Z",
                "as_of_utc": "2030-01-01T05:04:00Z",
            }
        )
