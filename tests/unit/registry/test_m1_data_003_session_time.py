from __future__ import annotations

import ast
import inspect
from pathlib import Path

import pytest

import tpaa_registry.time_alignment as time_alignment
from tpaa_registry import (
    CanonicalTimeTransformProjection,
    SessionTimeError,
    apply_session_time_us,
    build_all_session_time_projections,
    build_session_time_projection,
    parse_offset_us,
    parse_source_time_us,
    validate_source_clock_sequence,
)

FIXTURE_ROOT = Path(__file__).resolve().parents[2] / "fixtures" / "m1"


def test_nominal_fixture_maps_source_clock_to_session_time_exactly() -> None:
    projection = build_session_time_projection(
        FIXTURE_ROOT / "BF_M1_NOMINAL_V1"
    )

    assert projection.source_time_basis == "SOURCE_US"
    assert projection.start_session_time_us == 1_000_000
    assert projection.end_session_time_us == 9_000_000
    assert [row.session_time_us for row in projection.rows] == [
        1_000_000,
        2_000_000,
        3_000_000,
        4_000_000,
        5_000_000,
        6_000_000,
        7_000_000,
        8_000_000,
    ]
    assert [marker.session_time_us for marker in projection.markers] == [
        1_000_000,
        3_000_000,
        5_000_000,
        7_000_000,
        9_000_000,
    ]


def test_nominal_transform_is_canonical_anchored_rational() -> None:
    transform = build_session_time_projection(
        FIXTURE_ROOT / "BF_M1_NOMINAL_V1"
    ).transform

    assert transform.model == "ANCHORED_RATIONAL"
    assert transform.anchor_segment_time_ns == 0
    assert transform.anchor_session_time_us == 1_000_000
    assert transform.rate_num == 1
    assert transform.rate_den == 1000
    assert transform.valid_segment_start_ns == 0
    assert transform.valid_segment_end_ns == 8_000_000_000
    assert transform.residual_rms_us == 0.0
    assert transform.residual_p95_us == 0.0
    assert transform.confidence == 1.0
    assert transform.method == "M1_FIXTURE_OFFSET_US"
    assert transform.version == "1.0.0"
    assert len(transform.transform_hash) == 64


def test_all_governed_fixtures_have_deterministic_unique_time_identities() -> None:
    first = build_all_session_time_projections(FIXTURE_ROOT)
    second = build_all_session_time_projections(FIXTURE_ROOT)

    assert first == second
    assert len(first) == 8
    assert len({item.transform.source_clock_segment_id for item in first}) == 8
    assert len({item.transform.time_transform_id for item in first}) == 8
    assert len({item.logical_hash for item in first}) == 8


@pytest.mark.parametrize(
    "value",
    [
        "",
        "+1000000",
        "01",
        "1,000,000",
        "1 000 000",
        "1000000.0",
        " 1000000",
        "1000000 ",
        "-1",
    ],
)
def test_source_time_parser_rejects_noncanonical_text(value: str) -> None:
    with pytest.raises(SessionTimeError) as caught:
        parse_source_time_us(value)

    assert caught.value.code == "M1_SESSION_TIME_SOURCE_FORMAT_INVALID"


@pytest.mark.parametrize(
    "value",
    [
        "",
        "+1000000",
        "-0",
        "01",
        "-01",
        "1,000,000",
        "1000000.0",
        " 1000000",
        None,
        1000000,
    ],
)
def test_offset_parser_rejects_locale_or_implicit_formats(value: object) -> None:
    with pytest.raises(SessionTimeError) as caught:
        parse_offset_us(value)

    assert caught.value.code == "M1_SESSION_TIME_OFFSET_FORMAT_INVALID"


def test_offset_parser_supports_explicit_signed_decimal_integer() -> None:
    assert parse_offset_us("0") == 0
    assert parse_offset_us("1000000") == 1_000_000
    assert parse_offset_us("-1000000") == -1_000_000


def test_clock_rollback_is_detected_before_any_reordering() -> None:
    with pytest.raises(SessionTimeError) as caught:
        validate_source_clock_sequence((0, 2_000_000, 1_000_000))

    assert caught.value.code == "M1_SESSION_TIME_CLOCK_ROLLBACK_UNSEGMENTED"


def test_exact_rational_transform_rejects_implicit_rounding() -> None:
    transform = CanonicalTimeTransformProjection(
        source_clock_segment_id="segment",
        time_transform_id="transform",
        model="ANCHORED_RATIONAL",
        anchor_segment_time_ns=0,
        anchor_session_time_us=0,
        rate_num=1,
        rate_den=3,
        valid_segment_start_ns=0,
        valid_segment_end_ns=10,
        residual_rms_us=0.0,
        residual_p95_us=0.0,
        confidence=1.0,
        method="TEST",
        version="1",
        transform_hash="0" * 64,
    )

    with pytest.raises(SessionTimeError) as caught:
        apply_session_time_us(transform, 1)

    assert caught.value.code == "M1_SESSION_TIME_NON_INTEGRAL_TRANSFORM"


def test_transform_rejects_time_outside_valid_domain() -> None:
    transform = build_session_time_projection(
        FIXTURE_ROOT / "BF_M1_NOMINAL_V1"
    ).transform

    with pytest.raises(SessionTimeError) as caught:
        apply_session_time_us(transform, transform.valid_segment_end_ns + 1000)

    assert caught.value.code == "M1_SESSION_TIME_OUTSIDE_TRANSFORM_DOMAIN"


def test_time_alignment_module_has_no_timezone_locale_or_wall_clock_import() -> None:
    tree = ast.parse(inspect.getsource(time_alignment))
    imported_roots: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported_roots.update(alias.name.split(".", 1)[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imported_roots.add(node.module.split(".", 1)[0])

    assert imported_roots.isdisjoint({"datetime", "locale", "time", "zoneinfo"})
