"""The installed B2 P2 cohort must survive every independent-subject jackknife."""

from __future__ import annotations

import pytest

from tools.testing.ed2_b2_continuous_input_builder import (
    verify_p2_jackknife_support,
)


def test_ed2_b2_eight_subject_cohort_supports_four_historical_targets() -> None:
    verify_p2_jackknife_support(
        {
            "1": "0.35",
            "2": "0.45",
            "3": "0.55",
            "4": "0.65",
            "5": "0.0",
            "6": "0.1",
            "7": "0.9",
            "8": "1.0",
        },
        reference_value="0.5",
    )


def test_ed2_b2_original_five_subject_design_fails_closed() -> None:
    with pytest.raises(ValueError, match="REFERENCE_SUBJECT_COUNT_INVALID"):
        verify_p2_jackknife_support(
            {
                "1": "0.0",
                "2": "1.0",
                "3": "1.0",
                "4": "0.0",
                "5": "0.5",
            },
            reference_value="0.5",
        )


def test_ed2_b2_unsupported_jackknife_design_fails_closed() -> None:
    with pytest.raises(ValueError, match="JACKKNIFE_SUPPORT_INSUFFICIENT"):
        verify_p2_jackknife_support(
            {
                "1": "0.0",
                "2": "1.0",
                "3": "1.0",
                "4": "0.0",
                "5": "0.5",
                "6": "0.5",
                "7": "0.5",
                "8": "0.5",
            },
            reference_value="0.5",
        )
