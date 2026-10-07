"""PRCB C5 deterministic P4/P5 qualification seed using product persistence."""

from __future__ import annotations

from tpaa_assessment import P4SubjectContext
from tpaa_context import canonical_hash, pseudonymous_subject_key
from tpaa_storage.canonical_rows import CanonicalRowRepository

AIRCRAFT_MODEL = "94100000-0000-4000-8000-000000000001"
AIRCRAFT = "94100000-0000-4000-8000-000000000002"
TWIN = "94100000-0000-4000-8000-000000000003"
SESSION = "94100000-0000-4000-8000-000000000004"
EPISODE = "94100000-0000-4000-8000-000000000005"
ROLE_OBJECT = "94100000-0000-4000-8000-000000000006"
ROLE_ARTIFACT = "94100000-0000-4000-8000-000000000007"
JOB = "94100000-0000-4000-8000-000000000008"
RELEASE = "94100000-0000-4000-8000-000000000009"
EVIDENCE = "94100000-0000-4000-8000-00000000000a"
ACTOR = "94100000-0000-4000-8000-00000000000b"
P4_ID = "94100000-0000-4000-8000-00000000000c"
ANNOTATION_ID = "94100000-0000-4000-8000-00000000000f"
TEAM = "94100000-0000-4000-8000-00000000000d"
P5_ID = "94100000-0000-4000-8000-00000000000e"
AS_OF = "2026-09-20T12:00:00Z"
CREATED = "2026-09-20T12:30:00Z"


def build_prcb_c5_p4_subject() -> P4SubjectContext:
    subject_key = pseudonymous_subject_key(ACTOR)
    identity = {
        "subject_key": subject_key,
        "role_code": "SUBJECT_SELF",
        "seat_code": "FRONT",
        "function_code": "PILOT",
        "session_id": SESSION,
        "episode_id": EPISODE,
        "stage_id": None,
        "aircraft_id": AIRCRAFT,
        "twin_revision_id": TWIN,
        "p3_estimate_id": None,
        "assessment_spec_id": "P4_ASSESSMENT:TRAINING_EVIDENCE_ONLY",
        "assessment_spec_version": "1.0.0",
        "role_model_context_artifact_id": ROLE_ARTIFACT,
        "as_of_utc": AS_OF,
    }
    return P4SubjectContext(
        subject_context_id=f"P4_SUBJECT_CONTEXT_SHA256:{canonical_hash(identity)}",
        subject_key=subject_key,
        actor_id=ACTOR,
        role_code="SUBJECT_SELF",
        seat_code="FRONT",
        function_code="PILOT",
        session_id=SESSION,
        episode_id=EPISODE,
        stage_id=None,
        aircraft_id=AIRCRAFT,
        twin_revision_id=TWIN,
        p3_estimate_id=None,
        assessment_spec_id="P4_ASSESSMENT:TRAINING_EVIDENCE_ONLY",
        assessment_spec_version="1.0.0",
        role_model_context_artifact_id=ROLE_ARTIFACT,
        role_model_version="1.0.0",
        world_refs=("world:action:ordered-2", "world:perceived:ordered-1"),
        evidence_set_id=EVIDENCE,
        as_of_utc=AS_OF,
        knowledge_time_utc="2026-09-20T11:59:59Z",
    )


def seed_prcb_c5_p4_p5_upstream(rows: CanonicalRowRepository) -> None:
    rows.insert(
        "master.aircraft_model",
        {
            "aircraft_model_id": AIRCRAFT_MODEL,
            "type_code": "PRCB-C5-P45-TYPE",
            "model_name": "PRCB C5 P4/P5 Qualification Model",
        },
    )
    rows.insert(
        "master.aircraft",
        {
            "aircraft_id": AIRCRAFT,
            "aircraft_model_id": AIRCRAFT_MODEL,
            "internal_code": "PRCB-C5-P45-AIRCRAFT",
            "master_data_status": "ACTIVE",
        },
    )
    rows.insert(
        "capability.aircraft_twin_revision",
        {
            "twin_revision_id": TWIN,
            "aircraft_id": AIRCRAFT,
            "revision_no": 1,
            "component_model_refs": (),
            "valid_from": "2026-09-01T00:00:00Z",
            "as_of_data_time": AS_OF,
            "published_at": AS_OF,
            "status": "PUBLISHED",
            "uncertainty_summary": {},
            "evidence_snapshot_id": "94100000-0000-4000-8000-00000000000f",
        },
        field_kinds={
            "component_model_refs": "uuid_array",
            "uncertainty_summary": "json",
        },
    )
    rows.insert(
        "registry.training_session",
        {
            "session_id": SESSION,
            "session_code": "PRCB-C5-P4P5",
            "session_type": "SIM",
            "start_session_time_us": 0,
            "end_session_time_us": 1_000_000,
            "training_type_set": ("QUALIFICATION",),
            "data_status": "READY",
            "source_count": 1,
            "schema_version": "1.9.0",
        },
        field_kinds={"training_type_set": "text_array"},
    )
    rows.insert(
        "episode.training_episode",
        {
            "episode_id": EPISODE,
            "session_id": SESSION,
            "episode_type": "MISSION",
            "start_session_time_us": 0,
            "end_session_time_us": 1_000_000,
            "subject_scope": "TEAM",
            "primary_aircraft_id": AIRCRAFT,
            "primary_team_id": TEAM,
            "world_capability_code": "P4_P5",
            "episode_status": "COMPLETE",
            "detector_version": "PRCB-C5",
            "coverage": 1.0,
            "confidence": 1.0,
        },
    )
    rows.insert(
        "registry.object_reference",
        {
            "object_ref_id": ROLE_OBJECT,
            "managed_uri": "tpaa-object://piqb-b2/role-model.json",
            "media_type": "application/json",
            "size_bytes": 2,
            "artifact_sha256": "a" * 64,
            "logical_content_hash": "a" * 64,
            "storage_backend": "LOCAL_OBJECT_STORE",
            "sealed": True,
            "gc_state": "ACTIVE",
            "gc_state_version": 0,
        },
    )
    rows.insert(
        "registry.context_artifact",
        {
            "context_artifact_id": ROLE_ARTIFACT,
            "artifact_kind": "ROLE_MODEL",
            "logical_key": "PRCB-C5:P4-P5-ROLE-MODEL",
            "artifact_version": "1.0.0",
            "object_ref_id": ROLE_OBJECT,
            "artifact_sha256": "a" * 64,
            "schema_version": "TPAA_M8_ROLE_PRIVACY_PROFILE_V1",
            "status": "ACTIVE",
        },
    )
    rows.insert(
        "registry.compute_job",
        {
            "job_id": JOB,
            "job_type": "PRCB_C5_P4_P5_QUALIFICATION",
            "session_id": SESSION,
            "episode_id": EPISODE,
            "job_key": "PRCB-C5-P4-P5",
            "status": "SUCCEEDED",
            "component_version": "PRCB-1.0",
            "input_hash": "b" * 64,
            "progress": 1.0,
            "reason_codes": (),
        },
        field_kinds={"reason_codes": "text_array"},
    )
    rows.insert(
        "registry.analysis_release",
        {
            "release_id": RELEASE,
            "scope_type": "SESSION",
            "scope_key": f"SESSION:{SESSION}",
            "session_id": SESSION,
            "release_no": 1,
            "compute_job_id": JOB,
            "catalog_version": "P1-METRIC-CATALOG-1.0",
            "catalog_hash": "c" * 64,
            "context_binding_hash": "d" * 64,
            "status": "PUBLISHED",
            "manifest_hash": "e" * 64,
            "created_at": "2026-09-20T11:00:00Z",
            "published_at": "2026-09-20T11:01:00Z",
        },
    )
    rows.insert(
        "metric.evidence_set",
        {
            "evidence_set_id": EVIDENCE,
            "release_id": RELEASE,
            "session_id": SESSION,
            "episode_id": EPISODE,
            "series_locator": [],
            "algorithm_versions": {"piqb_b2": "1.0.0"},
        },
        field_kinds={
            "series_locator": "json",
            "algorithm_versions": "json",
        },
    )
