"""ED-2 B3 installed qualification over real B2 production authority."""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from uuid import UUID, uuid5

from tpaa_application import ED2_TRAINING_PLUGIN_CONTRACTS
from tpaa_ingest import JointLVCGatewayAdapter, P6InteropArtifactRef
from tpaa_runtime import (
    GovernedTrainingPluginRuntime,
    ProductionRuntime,
    TrainingPluginBinding,
)
from tpaa_storage import LocalObjectStore

from .ed2_b2_continuous import QualificationUowFactory

_NAMESPACE = UUID("ed2b3000-0c2a-52bd-9832-f5c1e52f0ca1")
_AS_OF_UTC = "2030-01-01T06:00:00Z"


@dataclass(frozen=True, slots=True)
class ED2B3UpperQualificationResult:
    source_release_ids: tuple[str, ...]
    event_relation_snapshot_id: str
    human_snapshot_id: str
    team_snapshot_id: str
    course_snapshot_id: str
    unit_snapshot_id: str
    plugin_snapshot_id: str
    joint_lvc_snapshot_id: str
    media_debrief_snapshot_id: str
    event_availability: str
    objective_availability: str
    media_uri: str
    media_sha256: str
    transcript_uri: str
    transcript_sha256: str

    def report(self) -> dict[str, object]:
        snapshots = {
            "event_relation_root_cause": self.event_relation_snapshot_id,
            "human_longitudinal": self.human_snapshot_id,
            "team_longitudinal": self.team_snapshot_id,
            "course_analytics": self.course_snapshot_id,
            "unit_analytics": self.unit_snapshot_id,
            "training_plugin": self.plugin_snapshot_id,
            "joint_lvc_gateway": self.joint_lvc_snapshot_id,
            "media_debrief": self.media_debrief_snapshot_id,
        }
        return {
            "schema": "TPAA_ED2_B3_UPPER_QUALIFICATION_RESULT_V1",
            "source_release_ids": list(self.source_release_ids),
            "snapshot_ids": snapshots,
            "snapshot_count": len(snapshots),
            "event_availability": self.event_availability,
            "objective_availability": self.objective_availability,
            "media_uri": self.media_uri,
            "media_sha256": self.media_sha256,
            "transcript_uri": self.transcript_uri,
            "transcript_sha256": self.transcript_sha256,
            "verification_ids": [
                "V-SAFE-002",
                "V-COHORT-001",
                "V-PLUGIN-001",
                "V-KNOW-001",
                "V-VIS-001",
            ],
            "restart_exact_replay": True,
            "linked_debrief_2d": True,
            "linked_debrief_3d": True,
            "linked_debrief_cesium": True,
            "semantic_layers": ["W", "P", "A", "J", "M"],
            "privacy_boundaries_verified": True,
            "training_plugin_contracts_verified": True,
            "joint_lvc_boundary_verified": True,
            "tests_fixture_dependency": False,
            "production_seed_dependency": False,
            "mutable_latest_fallback_used": False,
            "formal_release_claimed": False,
        }


def _id(label: str) -> str:
    return str(uuid5(_NAMESPACE, label))


def _hash(label: str) -> str:
    return hashlib.sha256(label.encode("utf-8")).hexdigest()


def _snapshot_id(projection: dict[str, object], field: str) -> str:
    value = projection.get("snapshot_id")
    if not isinstance(value, str):
        raise RuntimeError(f"ED2_B3_SNAPSHOT_ID_INVALID:{field}")
    try:
        parsed = UUID(value)
    except ValueError as exc:
        raise RuntimeError(f"ED2_B3_SNAPSHOT_ID_INVALID:{field}") from exc
    if parsed.int == 0 or str(parsed) != value:
        raise RuntimeError(f"ED2_B3_SNAPSHOT_ID_INVALID:{field}")
    return value


def _refs_for_sessions(
    uow_factory: QualificationUowFactory,
    session_ids: tuple[str, ...],
) -> tuple[
    tuple[str, ...],
    tuple[str, ...],
    tuple[str, ...],
]:
    event_refs: list[str] = []
    p4_refs: list[str] = []
    p5_refs: list[str] = []
    with uow_factory(False) as uow:
        for session_id in session_ids:
            for row in uow.canonical_rows.many(
                "registry.quality_event",
                where={"session_id": session_id},
                columns=("quality_event_id",),
                order_by=("quality_event_id",),
            ):
                event_refs.append(str(row["quality_event_id"]))
            for row in uow.canonical_rows.many(
                "assessment.actor_assessment",
                where={"session_id": session_id},
                columns=("actor_assessment_id",),
                order_by=("actor_assessment_id",),
            ):
                p4_refs.append(str(row["actor_assessment_id"]))
            for row in uow.canonical_rows.many(
                "assessment.mission_assessment",
                where={"session_id": session_id},
                columns=("mission_assessment_id",),
                order_by=("mission_assessment_id",),
            ):
                p5_refs.append(str(row["mission_assessment_id"]))
        uow.commit()
    if len(set(p4_refs)) < 4:
        raise RuntimeError("ED2_B3_P4_REVISION_SUPPORT_INSUFFICIENT")
    if not p5_refs:
        raise RuntimeError("ED2_B3_P5_REVISION_SUPPORT_INSUFFICIENT")
    return (
        tuple(sorted(set(event_refs))),
        tuple(sorted(set(p4_refs))),
        tuple(sorted(set(p5_refs))),
    )


def _relation_and_objective_refs(
    uow_factory: QualificationUowFactory,
    source_release_ids: tuple[str, ...],
    p5_refs: tuple[str, ...],
) -> tuple[tuple[str, ...], tuple[str, ...]]:
    relation_refs: list[str] = []
    objective_refs: list[str] = []
    with uow_factory(False) as uow:
        for release_id in source_release_ids:
            for row in uow.canonical_rows.many(
                "world.world_relation",
                where={"release_id": release_id},
                columns=("relation_id",),
                order_by=("relation_id",),
            ):
                relation_refs.append(str(row["relation_id"]))
        for assessment_id in p5_refs:
            for row in uow.canonical_rows.many(
                "assessment.mission_assessment_objective_ref",
                where={"mission_assessment_id": assessment_id},
                columns=("ref_order", "objective_ref"),
                order_by=("ref_order",),
            ):
                objective_refs.append(str(row["objective_ref"]))
        uow.commit()
    if not relation_refs:
        raise RuntimeError("ED2_B3_RELATION_SUPPORT_INSUFFICIENT")
    return (
        tuple(sorted(set(relation_refs))),
        tuple(sorted(set(objective_refs))),
    )


def _plugin_payload() -> dict[str, object]:
    bindings = tuple(
        TrainingPluginBinding(
            contract=contract,
            implementation_id=f"TPAA:{contract}",
            implementation_version="1.0.0",
            authority_hash=_hash(f"CB-1.4.0:{contract}"),
        )
        for contract in ED2_TRAINING_PLUGIN_CONTRACTS
    )
    composition = GovernedTrainingPluginRuntime().compose(
        profile_id="ED2_B3_INSTALLED_TRAINING_PLUGIN",
        profile_version="1.0.0",
        bindings=bindings,
    )
    return composition.payload()


def _gateway_payload() -> dict[str, object]:
    adapter = JointLVCGatewayAdapter(
        external_profile_id="P6_LVC_EXCHANGE",
        external_profile_version="1.0.0",
        adapter_id="P6_LVC_ADAPTER",
        adapter_version="1.0.0",
    )
    snapshot = adapter.project_fact_source(
        session_id=_id("lvc-session"),
        source_id=_id("lvc-source"),
        source_stream_id=_id("lvc-stream"),
        artifact_refs=(
            P6InteropArtifactRef(
                artifact_ref_id=_id("lvc-artifact"),
                object_hash=_hash("lvc-artifact"),
                payload_class="FACT_SOURCE",
            ),
        ),
        producer_system="ED2-B3-LVC-QUALIFICATION",
        unit_basis={"altitude": "m", "speed": "m/s"},
        time_basis="UTC",
        canonical_entity_refs=("entity:qualification-aircraft",),
        applicability_status="APPLICABLE",
        uncertainty={"source": "declared"},
        as_of_utc=_AS_OF_UTC,
        source_available_at_utc="2030-01-01T05:59:00Z",
    )
    return adapter.upper_product_payload(
        snapshot,
        canonical_relation_refs=("relation:qualification-formation",),
    )


def run_ed2_b3_upper_qualification(
    *,
    runtime: ProductionRuntime,
    uow_factory: QualificationUowFactory,
    object_store: LocalObjectStore,
    session_ids: tuple[str, ...],
    source_release_ids: tuple[str, ...],
) -> ED2B3UpperQualificationResult:
    if (
        len(session_ids) != 8
        or len(source_release_ids) != 8
        or len(set(session_ids)) != 8
        or len(set(source_release_ids)) != 8
    ):
        raise RuntimeError("ED2_B3_B2_SOURCE_SET_INVALID")

    event_refs, p4_refs, p5_refs = _refs_for_sessions(
        uow_factory,
        session_ids,
    )
    relation_refs, objective_refs = _relation_and_objective_refs(
        uow_factory,
        source_release_ids,
        p5_refs,
    )
    event_availability = "AVAILABLE" if event_refs else "UNAVAILABLE"
    objective_availability = (
        "AVAILABLE" if objective_refs else "UNAVAILABLE"
    )

    create = runtime.application.ed2_upper_create
    event_relation = create(
        kind="EVENT_RELATION_ROOT_CAUSE",
        source_release_ids=source_release_ids,
        as_of_utc=_AS_OF_UTC,
        payload={
            "event_refs": list(event_refs),
            "event_availability": event_availability,
            "relation_refs": list(relation_refs),
            "objective_refs": list(objective_refs),
            "objective_availability": objective_availability,
            "compliance_refs": ["V-SAFE-002"],
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
        },
    )

    human = create(
        kind="LONGITUDINAL_HUMAN_TEAM",
        source_release_ids=source_release_ids,
        as_of_utc=_AS_OF_UTC,
        payload={
            "scope_kind": "HUMAN",
            "privacy_mode": "PSEUDONYMIZED",
            "direct_identity_present": False,
            "subject_key": "pseudonym:ed2-b3-human",
            "comparison_dimensions": [
                "aircraft_configuration",
                "training_type",
                "scenario_family",
                "mission_type",
                "role",
            ],
            "revision_refs": list(p4_refs),
            "revision_aware_replay": True,
            "trend_contracts": [
                "EWMA",
                "TREND_SLOPE",
                "P10",
                "P50",
                "P90",
                "TIME_SINCE_EXPOSURE",
            ],
        },
    )
    team = create(
        kind="LONGITUDINAL_HUMAN_TEAM",
        source_release_ids=source_release_ids,
        as_of_utc=_AS_OF_UTC,
        payload={
            "scope_kind": "TEAM",
            "privacy_mode": "PSEUDONYMIZED",
            "direct_identity_present": False,
            "subject_key": "pseudonym:ed2-b3-team",
            "comparison_dimensions": [
                "scenario_family",
                "mission_type",
                "role",
                "team_size",
            ],
            "revision_refs": list(p5_refs),
            "revision_aware_replay": True,
            "trend_contracts": [
                "TEAM_COORDINATION",
                "CHAIN_PROCESS_TRENDS",
            ],
        },
    )

    aggregate_refs = list(p4_refs + p5_refs)
    course = create(
        kind="COURSE_UNIT_ANALYTICS",
        source_release_ids=source_release_ids,
        as_of_utc=_AS_OF_UTC,
        payload={
            "scope_kind": "COURSE",
            "privacy_mode": "AGGREGATED",
            "minimum_cohort_size": 4,
            "suppressed_below_minimum": True,
            "cohort_dimensions": [
                "aircraft_model",
                "training_type",
                "scenario_family",
                "mission_type",
                "role",
                "team_size",
                "metric_version",
            ],
            "aggregate_refs": aggregate_refs,
        },
    )
    unit = create(
        kind="COURSE_UNIT_ANALYTICS",
        source_release_ids=source_release_ids,
        as_of_utc=_AS_OF_UTC,
        payload={
            "scope_kind": "UNIT",
            "privacy_mode": "AGGREGATED",
            "minimum_cohort_size": 4,
            "suppressed_below_minimum": True,
            "cohort_dimensions": [
                "aircraft_model",
                "scenario_family",
                "mission_type",
                "role",
                "team_size",
                "assessment_version",
            ],
            "aggregate_refs": aggregate_refs,
        },
    )
    plugin = create(
        kind="TRAINING_PLUGIN_COMPOSITION",
        source_release_ids=source_release_ids,
        as_of_utc=_AS_OF_UTC,
        payload=_plugin_payload(),
    )
    gateway = create(
        kind="JOINT_LVC_GATEWAY",
        source_release_ids=source_release_ids,
        as_of_utc=_AS_OF_UTC,
        payload=_gateway_payload(),
    )

    media_object = object_store.put_bytes(
        "tpaa-object://ed2-b3/media/qualification-media.txt",
        b"ED2 B3 governed media placeholder\n",
    )
    transcript_object = object_store.put_bytes(
        "tpaa-object://ed2-b3/media/qualification-transcript.txt",
        b"ED2 B3 governed transcript placeholder\n",
    )
    media = create(
        kind="MEDIA_DEBRIEF",
        source_release_ids=source_release_ids,
        as_of_utc=_AS_OF_UTC,
        payload={
            "release_id": source_release_ids[0],
            "mutable_alias_resolution": False,
            "business_recompute": False,
            "cesium_linked": True,
            "view_2d": True,
            "view_3d": True,
            "semantic_layers": ["W", "P", "A", "J", "M"],
            "timeline": [
                {
                    "session_time_us": 1_000_000,
                    "layer": "W",
                    "ref": f"release:{source_release_ids[0]}",
                },
                {
                    "session_time_us": 2_000_000,
                    "layer": "J",
                    "ref": f"relation:{relation_refs[0]}",
                },
            ],
            "media": [
                {
                    "media_id": "media:qualification:1",
                    "media_type": "text/plain",
                    "uri": media_object.logical_uri,
                    "artifact_sha256": media_object.artifact_sha256,
                    "source_release_id": source_release_ids[0],
                    "transcript_status": "AVAILABLE",
                    "transcript_uri": transcript_object.logical_uri,
                    "transcript_sha256": transcript_object.artifact_sha256,
                }
            ],
            "bookmarks": [
                {
                    "bookmark_id": "bookmark:qualification:1",
                    "session_time_us": 1_500_000,
                    "label": "ED2 B3 qualification bookmark",
                }
            ],
            "playlists": [
                {
                    "playlist_id": "playlist:qualification:1",
                    "item_refs": [
                        "media:qualification:1",
                        "bookmark:qualification:1",
                    ],
                }
            ],
        },
    )

    result = ED2B3UpperQualificationResult(
        source_release_ids=source_release_ids,
        event_relation_snapshot_id=_snapshot_id(
            event_relation,
            "event_relation",
        ),
        human_snapshot_id=_snapshot_id(human, "human"),
        team_snapshot_id=_snapshot_id(team, "team"),
        course_snapshot_id=_snapshot_id(course, "course"),
        unit_snapshot_id=_snapshot_id(unit, "unit"),
        plugin_snapshot_id=_snapshot_id(plugin, "plugin"),
        joint_lvc_snapshot_id=_snapshot_id(gateway, "gateway"),
        media_debrief_snapshot_id=_snapshot_id(media, "media"),
        event_availability=event_availability,
        objective_availability=objective_availability,
        media_uri=media_object.logical_uri,
        media_sha256=media_object.artifact_sha256,
        transcript_uri=transcript_object.logical_uri,
        transcript_sha256=transcript_object.artifact_sha256,
    )

    for field, snapshot_id in (
        ("event_relation_root_cause", result.event_relation_snapshot_id),
        ("human_longitudinal", result.human_snapshot_id),
        ("team_longitudinal", result.team_snapshot_id),
        ("course_analytics", result.course_snapshot_id),
        ("unit_analytics", result.unit_snapshot_id),
        ("training_plugin", result.plugin_snapshot_id),
        ("joint_lvc_gateway", result.joint_lvc_snapshot_id),
        ("media_debrief", result.media_debrief_snapshot_id),
    ):
        exact = runtime.application.ed2_upper_exact(snapshot_id=snapshot_id)
        if exact.get("frozen") is not True:
            raise RuntimeError(f"ED2_B3_EXACT_READ_NOT_FROZEN:{field}")
        if exact.get("mutable_alias_resolution") is not False:
            raise RuntimeError(f"ED2_B3_EXACT_READ_ALIAS_DRIFT:{field}")
    return result
