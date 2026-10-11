from __future__ import annotations

from copy import deepcopy

import pytest

from tpaa_application import (
    ED2_TRAINING_PLUGIN_CONTRACTS,
    ED2UpperProductError,
    build_ed2_upper_product,
)

_RELEASE = "11111111-1111-4111-8111-111111111111"
_EVENT = "22222222-2222-4222-8222-222222222222"
_RELATION = "33333333-3333-4333-8333-333333333333"
_OBJECTIVE = "44444444-4444-4444-8444-444444444444"
_REVISION = "55555555-5555-4555-8555-555555555555"
_AS_OF = "2030-01-01T05:00:00Z"
_HASH = "a" * 64


def _event_payload() -> dict[str, object]:
    return {
        "event_refs": [_EVENT],
        "event_availability": "AVAILABLE",
        "relation_refs": [_RELATION],
        "objective_refs": [_OBJECTIVE],
        "objective_availability": "AVAILABLE",
        "compliance_refs": ["CR-020"],
        "knowledge_time_mode": "ORIGINAL_AS_KNOWN",
        "causal_upgrade": False,
        "root_cause_candidates": [
            {
                "category": "DATA_QUALITY",
                "candidate_only": True,
                "automatic_personnel_fault": False,
                "responsibility_basis": "SYSTEM_OR_DATA_FACTOR",
            }
        ],
    }


def _human_payload() -> dict[str, object]:
    return {
        "scope_kind": "HUMAN",
        "privacy_mode": "PSEUDONYMIZED",
        "direct_identity_present": False,
        "subject_key": "pseudonym:alpha",
        "comparison_dimensions": [
            "scenario_family",
            "mission_type",
            "role",
        ],
        "revision_refs": [_REVISION],
        "revision_aware_replay": True,
        "trend_contracts": ["EWMA", "P10", "P50", "P90"],
    }


def _course_payload() -> dict[str, object]:
    return {
        "scope_kind": "COURSE",
        "privacy_mode": "AGGREGATED",
        "minimum_cohort_size": 4,
        "suppressed_below_minimum": True,
        "cohort_dimensions": [
            "scenario_family",
            "mission_type",
            "role",
            "team_size",
        ],
        "aggregate_refs": ["aggregate:course:001"],
    }


def _plugin_payload() -> dict[str, object]:
    return {
        "profile_id": "ED2_TRAINING_PLUGIN_PROFILE",
        "profile_version": "1.0.0",
        "components": [
            {
                "contract": contract,
                "implementation_id": f"TPAA:{contract}",
                "implementation_version": "1.0.0",
                "authority_hash": _HASH,
                "enabled": True,
            }
            for contract in ED2_TRAINING_PLUGIN_CONTRACTS
        ],
        "untrusted_dynamic_loading": False,
    }


def _gateway_payload() -> dict[str, object]:
    return {
        "external_protocol_boundary": True,
        "session_type": "LVC",
        "external_profile_id": "P6_LVC_EXCHANGE",
        "external_profile_version": "1.0.0",
        "adapter_id": "P6_LVC_ADAPTER",
        "adapter_version": "1.0.0",
        "mapping_lossless": True,
        "fact_projection_separated": True,
        "operational_optimization": False,
        "unit_basis": {"altitude": "m", "speed": "m/s"},
        "time_basis": "UTC",
        "canonical_entity_refs": ["entity:aircraft:a"],
        "canonical_relation_refs": ["relation:formation:a-b"],
        "interop_snapshot_id": "P6_INTEROP_SHA256:" + _HASH,
        "logical_content_hash": _HASH,
    }


def _media_payload() -> dict[str, object]:
    return {
        "release_id": _RELEASE,
        "mutable_alias_resolution": False,
        "business_recompute": False,
        "cesium_linked": True,
        "view_2d": True,
        "view_3d": True,
        "semantic_layers": ["W", "P", "A", "J", "M"],
        "timeline": [
            {"session_time_us": 1_000_000, "layer": "W", "ref": "world:1"},
            {"session_time_us": 2_000_000, "layer": "J", "ref": "event:1"},
        ],
        "media": [
            {
                "media_id": "media:1",
                "media_type": "VIDEO",
                "uri": "tpaa-object://media/debrief-1",
                "artifact_sha256": _HASH,
                "source_release_id": _RELEASE,
                "transcript_status": "UNAVAILABLE",
            }
        ],
        "bookmarks": [
            {
                "bookmark_id": "bookmark:1",
                "session_time_us": 1_500_000,
                "label": "handoff",
            }
        ],
        "playlists": [
            {
                "playlist_id": "playlist:1",
                "item_refs": ["media:1", "bookmark:1"],
            }
        ],
    }


@pytest.mark.parametrize(
    ("kind", "payload"),
    [
        ("EVENT_RELATION_ROOT_CAUSE", _event_payload()),
        ("LONGITUDINAL_HUMAN_TEAM", _human_payload()),
        ("COURSE_UNIT_ANALYTICS", _course_payload()),
        ("TRAINING_PLUGIN_COMPOSITION", _plugin_payload()),
        ("JOINT_LVC_GATEWAY", _gateway_payload()),
        ("MEDIA_DEBRIEF", _media_payload()),
    ],
)
def test_ed2_b3_upper_product_kinds_are_exact_and_hash_stable(
    kind: str,
    payload: dict[str, object],
) -> None:
    first = build_ed2_upper_product(
        kind=kind,
        source_release_ids=(_RELEASE,),
        as_of_utc=_AS_OF,
        payload=payload,
    )
    second = build_ed2_upper_product(
        kind=kind.lower(),
        source_release_ids=(_RELEASE, _RELEASE),
        as_of_utc=_AS_OF,
        payload=deepcopy(payload),
    )
    assert first == second
    assert len(first.logical_content_hash) == 64
    assert first.source_release_ids == (_RELEASE,)


def test_ed2_b3_root_cause_never_upgrades_candidate_to_causal_or_personnel_fault(
) -> None:
    causal = _event_payload()
    causal["causal_upgrade"] = True
    with pytest.raises(ED2UpperProductError, match="CAUSAL_UPGRADE_FORBIDDEN"):
        build_ed2_upper_product(
            kind="EVENT_RELATION_ROOT_CAUSE",
            source_release_ids=(_RELEASE,),
            as_of_utc=_AS_OF,
            payload=causal,
        )

    personnel = _event_payload()
    candidates = personnel["root_cause_candidates"]
    assert isinstance(candidates, list)
    candidate = candidates[0]
    assert isinstance(candidate, dict)
    candidate["automatic_personnel_fault"] = True
    with pytest.raises(
        ED2UpperProductError,
        match="AUTOMATIC_PERSONNEL_FAULT_FORBIDDEN",
    ):
        build_ed2_upper_product(
            kind="EVENT_RELATION_ROOT_CAUSE",
            source_release_ids=(_RELEASE,),
            as_of_utc=_AS_OF,
            payload=personnel,
        )


def test_ed2_b3_human_and_course_products_enforce_privacy_boundaries() -> None:
    human = _human_payload()
    human["actor_id"] = "66666666-6666-4666-8666-666666666666"
    with pytest.raises(ED2UpperProductError, match="DIRECT_IDENTITY_FORBIDDEN"):
        build_ed2_upper_product(
            kind="LONGITUDINAL_HUMAN_TEAM",
            source_release_ids=(_RELEASE,),
            as_of_utc=_AS_OF,
            payload=human,
        )

    course = _course_payload()
    course["minimum_cohort_size"] = 1
    with pytest.raises(ED2UpperProductError, match="COHORT_MINIMUM_INVALID"):
        build_ed2_upper_product(
            kind="COURSE_UNIT_ANALYTICS",
            source_release_ids=(_RELEASE,),
            as_of_utc=_AS_OF,
            payload=course,
        )


def test_ed2_b3_training_plugin_forbids_dynamic_import_contract_drift() -> None:
    payload = _plugin_payload()
    components = payload["components"]
    assert isinstance(components, list)
    first = components[0]
    assert isinstance(first, dict)
    first["module_path"] = "arbitrary.module:Plugin"
    with pytest.raises(ED2UpperProductError, match="DYNAMIC_LOAD_FORBIDDEN"):
        build_ed2_upper_product(
            kind="TRAINING_PLUGIN_COMPOSITION",
            source_release_ids=(_RELEASE,),
            as_of_utc=_AS_OF,
            payload=payload,
        )


def test_ed2_b3_hash_input_remains_json_native_and_media_is_exact_release_bound(
) -> None:
    float_payload = _course_payload()
    float_payload["aggregate_value"] = 0.5
    with pytest.raises(ED2UpperProductError, match="FLOAT_FORBIDDEN"):
        build_ed2_upper_product(
            kind="COURSE_UNIT_ANALYTICS",
            source_release_ids=(_RELEASE,),
            as_of_utc=_AS_OF,
            payload=float_payload,
        )

    media = _media_payload()
    media["mutable_alias_resolution"] = True
    with pytest.raises(ED2UpperProductError, match="MUTABLE_ALIAS_FORBIDDEN"):
        build_ed2_upper_product(
            kind="MEDIA_DEBRIEF",
            source_release_ids=(_RELEASE,),
            as_of_utc=_AS_OF,
            payload=media,
        )

def test_ed2_b3_media_requires_sealed_hash_and_explicit_transcript_state() -> None:
    missing_hash = _media_payload()
    raw_media = missing_hash["media"]
    assert isinstance(raw_media, list)
    first = raw_media[0]
    assert isinstance(first, dict)
    del first["artifact_sha256"]
    with pytest.raises(
        ED2UpperProductError,
        match="TEXT_INVALID:media\\[0\\]\\.artifact_sha256",
    ):
        build_ed2_upper_product(
            kind="MEDIA_DEBRIEF",
            source_release_ids=(_RELEASE,),
            as_of_utc=_AS_OF,
            payload=missing_hash,
        )

    missing_status = _media_payload()
    raw_media = missing_status["media"]
    assert isinstance(raw_media, list)
    first = raw_media[0]
    assert isinstance(first, dict)
    del first["transcript_status"]
    with pytest.raises(
        ED2UpperProductError,
        match="TRANSCRIPT_STATUS_INVALID",
    ):
        build_ed2_upper_product(
            kind="MEDIA_DEBRIEF",
            source_release_ids=(_RELEASE,),
            as_of_utc=_AS_OF,
            payload=missing_status,
        )

