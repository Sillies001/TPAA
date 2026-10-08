from __future__ import annotations

import json
from uuid import NAMESPACE_URL, uuid5

from tpaa_ingest import (
    SourceFamily,
    descriptor_for_interchange_family,
    production_interchange_profile,
)
from tpaa_runtime.durable_jobs import ProductionJobExecutor

SESSION_ID = "e2100000-0000-4000-8000-000000000001"


def _id(name: str) -> str:
    return str(uuid5(NAMESPACE_URL, f"ed2-source-set:{name}"))


def _item(family: SourceFamily, ordinal: int) -> dict[str, object]:
    descriptor = descriptor_for_interchange_family(family)
    profile = production_interchange_profile(family)
    source_json = json.dumps(
        {
            "schema": "TPAA_PRODUCTION_INTERCHANGE_SOURCE_V1",
            "schema_version": "1.0.0",
            "source_family": family.value,
            "session_id": SESSION_ID,
            "profile": {
                "profile_id": profile.profile_id,
                "profile_version": profile.profile_version,
                "profile_hash": profile.profile_hash,
            },
            "knowledge_time_utc": "2026-10-08T00:00:00Z",
            "payload": {
                "projection_class": profile.projection_class,
                "lineage_ref": f"source:{family.value}:{ordinal}",
            },
        },
        sort_keys=True,
        separators=(",", ":"),
    )
    return {
        "source_json": source_json,
        "source_import": {
            "source_family": family.value,
            "source_id": _id(f"source-{ordinal}"),
            "session_id": SESSION_ID,
            "platform_id": None,
            "producer_system": "ED2_GATEWAY",
            "schema_name": "TPAA_PRODUCTION_INTERCHANGE_SOURCE_V1",
            "schema_version": "1.0.0",
            "time_basis": "SESSION_TIME_US",
            "nominal_rate_hz": None,
            "source_quality": "1.0",
            "source_stream_id": _id(f"stream-{ordinal}"),
            "stream_code": f"{family.value}_{ordinal}",
            "ordinal_basis": "SOURCE_SEQUENCE",
            "stream_status": "ACTIVE",
            "artifact_id": _id(f"artifact-{ordinal}"),
            "source_artifact_sequence": ordinal,
            "uri_kind": "MANAGED",
            "availability_status": "AVAILABLE",
            "last_verified_at": "2026-10-08T00:00:00Z",
            "mtime_source": None,
            "source_ref": f"gateway://{family.value.lower()}/{ordinal}",
            "media_type": descriptor.media_types[0],
            "classification_label": "UNCLASSIFIED",
        },
    }


def test_durable_p1_source_set_accepts_multiple_governed_families() -> None:
    commands = ProductionJobExecutor._source_imports(
        {
            "source_documents": [
                _item(SourceFamily.MISSION_AVIONICS, 1),
                _item(SourceFamily.TDL, 2),
                _item(SourceFamily.RANGE_ACMI, 3),
                _item(SourceFamily.SCENARIO, 4),
                _item(SourceFamily.AUDIO_VIDEO, 5),
            ]
        }
    )

    assert len(commands) == 5
    assert {item.session_id for item in commands} == {SESSION_ID}
    assert {
        item.envelope.source_family
        for item in commands
    } == {
        SourceFamily.MISSION_AVIONICS,
        SourceFamily.TDL,
        SourceFamily.RANGE_ACMI,
        SourceFamily.SCENARIO,
        SourceFamily.AUDIO_VIDEO,
    }
    assert all(item.envelope.adapter_id.startswith("tpaa-production-") for item in commands)
