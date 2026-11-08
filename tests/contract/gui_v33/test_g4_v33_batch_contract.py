from __future__ import annotations

import json
import re
from pathlib import Path
from typing import cast

from fastapi.routing import APIRoute

from tools.baseline.adopt_g4_successor import check_successor
from tools.codegen.g4_batch_generate import OUTPUTS, render
from tpaa_api import UnifiedPrincipal, create_desktop_app, create_unified_service_app
from tpaa_application import ApplicationService
from tpaa_security import (
    ApiAuthorizationGuard,
    ApprovalService,
    AuthorizationService,
    InMemoryApiAuthorizationAudit,
    InMemoryApprovalEventRepository,
    load_security_policy,
    route_security,
)

ROOT = Path(__file__).resolve().parents[3]
BASELINE = ROOT / "baseline" / "CB-1.9.0"


def _load(path: Path) -> dict[str, object]:
    value = json.loads(path.read_text(encoding="utf-8"))
    assert isinstance(value, dict)
    return value


def _runtime_graph() -> set[tuple[str, str, str, str]]:
    principal = UnifiedPrincipal(
        role="ADMIN_AUDITOR",
        actor_id="g4-route-parity",
        scope_match=True,
    )
    policy = load_security_policy()
    approvals = ApprovalService(AuthorizationService(policy), InMemoryApprovalEventRepository())
    guard = ApiAuthorizationGuard(
        AuthorizationService(policy), audit=InMemoryApiAuthorizationAudit()
    )
    application = cast(ApplicationService, object())
    apps = (
        create_unified_service_app(
            application=application,
            principal_resolver=lambda _request: principal,
            authorization_guard=guard,
            approval_service=approvals,
        ),
        create_desktop_app(
            application=application,
            bearer_token="g4-route-parity",
            principal_resolver=lambda _request: principal,
            authorization_guard=guard,
            approval_service=approvals,
            desktop_nonce="g4-route-parity-nonce",
        ),
    )
    graph = set()
    for app in apps:
        for route in app.routes:
            if isinstance(route, APIRoute):
                assert route.methods is not None and len(route.methods) == 1
                graph.add(
                    (
                        next(iter(route.methods)),
                        route.path,
                        route.endpoint.__module__,
                        route.endpoint.__name__,
                    )
                )
    return graph


def test_g4_successor_and_generated_runtime_are_reproducible() -> None:
    check_successor()
    for key, expected in render().items():
        assert OUTPUTS[key].read_text(encoding="utf-8") == expected
    baseline = _load(BASELINE / "BASELINE_LOCK.json")["baseline"]
    assert isinstance(baseline, dict)
    assert baseline["core"] == "CB-1.9.0"
    assert baseline["db_schema"] == "1.10.0"
    assert baseline["approval_status"] == "APPROVED_LOCAL"
    assert baseline["release_claim"] is False


def test_g4_security_authority_matches_the_current_runtime_graph_exactly() -> None:
    authority = _load(BASELINE / "canonical" / "API_ROUTE_SECURITY_AUTHORITY.json")
    routes = authority["active_routes"]
    assert isinstance(routes, list) and len(routes) == 96
    expected = {
        (item["method"], item["path"], item["module"], item["handler"])
        for item in routes
        if isinstance(item, dict)
    }
    assert _runtime_graph() == expected
    assert len({item["route_id"] for item in routes if isinstance(item, dict)}) == 96
    for number, item in enumerate(routes[-7:], start=90):
        assert isinstance(item, dict)
        concrete = re.sub(r"\{[^}/]+\}", "d4400000-0000-4000-8000-000000000001", str(item["path"]))
        binding = route_security(str(item["method"]), concrete)
        assert binding is not None
        assert binding.route_id == f"api.route.{number:03d}"
        assert binding.permission is not None
        assert binding.gui_permission_id == item["gui_permission_id"]
        assert binding.audit_mode == "ALWAYS"


def test_g4_activates_only_batch_and_context_routes() -> None:
    authority = _load(BASELINE / "canonical" / "API_ROUTE_AUTHORITY.json")
    routes = authority["routes"]
    reserved = authority["reserved_routes"]
    assert isinstance(routes, list)
    assert isinstance(reserved, list) and len(reserved) == 6
    g4 = {
        str(item["path"])
        for item in routes
        if isinstance(item, dict) and item.get("implementation_status") == "IMPLEMENTED_G4"
    }
    assert g4 == {
        "/api/v1/gui/import-tickets",
        "/api/v1/gui/batches",
        "/api/v1/gui/batches/{batch_id}",
        "/api/v1/gui/batches/{batch_id}/training-type-revisions",
        "/api/v1/gui/contexts/{context_id}/force-formation",
        "/api/v1/gui/contexts/{context_id}/force-formation-revisions",
    }
    assert all(item.get("implementation_status") == "RESERVED_G4_NOT_EXPOSED" for item in reserved)


def test_g4_authority_forbids_defaults_paths_and_unqualified_v01_admission() -> None:
    authority = _load(BASELINE / "canonical" / "GUI_BATCH_IMPORT_AUTHORITY.json")
    rules = authority["rules"]
    database = authority["database"]
    assert isinstance(rules, dict) and isinstance(database, dict)
    assert rules["default_training_type_forbidden"] is True
    assert rules["unconfirmed_training_type"] == "UNCLASSIFIED"
    assert rules["local_path_exposure"] == "FORBIDDEN"
    assert rules["v01_admission"] == "QUALIFIED_ONLY"
    assert rules["failure_retry"] == "SAME_IDEMPOTENCY_KEY_AND_IMMUTABLE_MANIFEST"
    assert database == {
        "schema": "1.10.0",
        "migration_required": False,
        "reason": "G1 DB 1.10.0 already admitted all four G4 physical tables.",
    }
    dto = _load(BASELINE / "canonical" / "CROSS_LAYER_DTO_CONTRACTS.json")
    contracts = dto["contracts"]
    assert isinstance(contracts, dict)
    assert {
        "ImportTicketDTO",
        "BatchRegistrationDTO",
        "BatchListDTO",
        "ForceFormationContextDTO",
        "BatchImportErrorDTO",
    }.issubset(contracts)
