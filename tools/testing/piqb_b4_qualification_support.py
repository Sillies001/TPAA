"""Support functions for PIQB B4 API/audit/observability qualification."""

from __future__ import annotations

import json
from dataclasses import asdict
from pathlib import Path

from tools.api.product_v1_contract import (
    build_client_contract,
    build_product_openapi,
)
from tpaa_application import SecurityAuditRecord
from tpaa_runtime import (
    PostgreSQLSecurityAuditSink,
    ProductAdmissionResolver,
    ProductFeatureAvailability,
    ProductOperationalStatus,
    ProductQualificationStatus,
    RuntimeProfile,
    SQLiteSecurityAuditSink,
)
from tpaa_storage import (
    AuditLogRow,
    PostgreSQLServiceUnitOfWork,
    SQLiteDesktopUnitOfWork,
)

ROOT = Path(__file__).resolve().parents[2]


def qualification_events() -> tuple[SecurityAuditRecord, ...]:
    return (
        SecurityAuditRecord(
            actor_id="11111111-1111-4111-8111-111111111111",
            principal_key="SUBJECT_SHA256:" + "a" * 64,
            action="P4_APPROVAL_WRITE",
            object_type="M8_SECURITY_EVENT",
            object_id="22222222-2222-4222-8222-222222222222",
            outcome="ALLOW",
            request_id="b4-qualification-request-1",
            reason="training approval",
            details={
                "viewer_role": "INSTRUCTOR_EVALUATOR",
                "scope_match": True,
            },
        ),
        SecurityAuditRecord(
            actor_id=None,
            principal_key="ROLE:ANALYST",
            action="P6_FORECAST_READ",
            object_type="P6_SECURITY_EVENT",
            object_id="33333333-3333-4333-8333-333333333333",
            outcome="ALLOW",
            reason="P6_FORECAST_READ",
            details={
                "viewer_role": "ANALYST",
                "scope_match": True,
            },
        ),
    )


def semantic_rows(rows: tuple[AuditLogRow, ...]) -> list[dict[str, object]]:
    result: list[dict[str, object]] = []
    for item in rows:
        value = asdict(item)
        value.pop("audit_id", None)
        value.pop("created_at", None)
        result.append(value)
    return result


def expected_security_rows(
    events: tuple[SecurityAuditRecord, ...],
) -> list[dict[str, object]]:
    return [
        {
            "actor_id": event.actor_id,
            "principal_key": event.principal_key,
            "action": event.action,
            "object_type": event.object_type,
            "object_id": event.object_id,
            "outcome": event.outcome,
            "request_id": event.request_id,
            "reason": event.reason,
            "details": dict(event.details or {}),
        }
        for event in events
    ]


def exercise_sqlite(database: Path) -> dict[str, object]:
    sink = SQLiteSecurityAuditSink(database)
    for event in qualification_events():
        sink.record(event)
    with SQLiteDesktopUnitOfWork(database) as restarted:
        rows = restarted.audit_log.rows()
        metadata = restarted.metadata.get()
        restarted.commit()
    return {
        "metadata": asdict(metadata),
        "rows": semantic_rows(rows),
        "row_count": len(rows),
        "restart_exact": len(rows) == len(qualification_events()),
    }


def exercise_postgres(conninfo: str) -> dict[str, object]:
    sink = PostgreSQLSecurityAuditSink(conninfo)
    for event in qualification_events():
        sink.record(event)
    with PostgreSQLServiceUnitOfWork(conninfo, read_only=True) as restarted:
        rows = restarted.audit_log.rows()
        metadata = restarted.metadata.get()
        restarted.commit()
    return {
        "metadata": asdict(metadata),
        "rows": semantic_rows(rows),
        "row_count": len(rows),
        "restart_exact": len(rows) == len(qualification_events()),
    }


def contract_checks() -> dict[str, object]:
    generated_openapi = build_product_openapi()
    generated_client = build_client_contract()
    committed_openapi = json.loads(
        (ROOT / "api" / "openapi-product-v1.json").read_text(encoding="utf-8")
    )
    committed_client = json.loads(
        (ROOT / "api" / "product-v1-client-contract.json").read_text(
            encoding="utf-8"
        )
    )
    contract = json.loads(
        (
            ROOT
            / "docs"
            / "baseline"
            / "PIQB-1.0"
            / "B4_PRODUCT_API_V1_CONTRACT.json"
        ).read_text(encoding="utf-8")
    )
    routes = contract.get("routes")
    invariants = contract.get("invariants")
    return {
        "openapi_exact": generated_openapi == committed_openapi,
        "client_exact": generated_client == committed_client,
        "route_count": len(routes) if isinstance(routes, list) else -1,
        "exact_ids_only": (
            isinstance(invariants, dict)
            and invariants.get("exact_ids_only") is True
        ),
        "no_alias_latest": (
            isinstance(invariants, dict)
            and invariants.get("mutable_latest_routes_forbidden") is True
            and invariants.get("aliases_forbidden") is True
        ),
        "no_hidden_recompute": (
            isinstance(invariants, dict)
            and invariants.get("hidden_recomputation_forbidden") is True
        ),
    }


def observability_checks() -> dict[str, object]:
    resolver = ProductAdmissionResolver()
    availability = ProductFeatureAvailability(
        resolver,
        configured={
            "P1": True,
            "P2": True,
            "P3": True,
            "P4": True,
            "P5": True,
            "P6": True,
        },
    )
    qualification = ProductQualificationStatus(
        feature_availability=availability,
        profile=RuntimeProfile.SERVICE,
        product_build_version="PIQB-B4-QUALIFICATION",
    )
    status = qualification.execute()
    operational = ProductOperationalStatus(qualification).execute()
    serialized = json.dumps(operational, sort_keys=True).casefold()
    forbidden = (
        "authorization",
        "cookie",
        "password",
        "secret",
        "token",
        "private_key",
        "credential",
    )
    data_plane = status.get("data_compute_plane")
    capabilities = status.get("capability_admission")
    items = capabilities.get("items") if isinstance(capabilities, dict) else None
    return {
        "qualification_schema_exact": (
            status.get("schema") == "TPAA_PRODUCT_QUALIFICATION_STATUS_V1"
        ),
        "db_schema_1_9": status.get("db_schema_version") == "1.9.0",
        "b3_qualified_exact": (
            isinstance(data_plane, dict)
            and data_plane.get("qualification") == "PIQB_B3_QUALIFIED"
            and data_plane.get("source_revision")
            == "08e223c8137eb261b43ed7c2ca3612e22770d8ba"
            and data_plane.get("run_number") == 618
        ),
        "p1_p6_available": (
            isinstance(items, list)
            and len(items) == 6
            and all(
                isinstance(item, dict) and item.get("state") == "AVAILABLE"
                for item in items
            )
        ),
        "structured_record_exact": (
            operational.get("component") == "tpaa-product-runtime"
            and operational.get("reason_code") == "PRODUCT_RUNTIME_STATUS"
        ),
        "secret_safe": not any(fragment in serialized for fragment in forbidden),
    }
