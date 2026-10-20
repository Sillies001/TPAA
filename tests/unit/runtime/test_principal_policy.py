from __future__ import annotations

import json
from pathlib import Path

import pytest

from tpaa_runtime import (
    PrincipalPolicyError,
    ProductionRole,
    permission_governance_status,
    validate_production_principal_policy,
)

ROOT = Path(__file__).resolve().parents[3]
AUTHORITY = ROOT / "baseline" / "CB-1.4.0" / "canonical"


def test_production_role_boundary_is_not_silently_expanded() -> None:
    assert tuple(role.value for role in ProductionRole) == (
        "SUBJECT_SELF",
        "INSTRUCTOR_EVALUATOR",
        "TEAM_LEAD",
        "ANALYST",
        "ADMIN_AUDITOR",
    )
    with pytest.raises(PrincipalPolicyError) as captured:
        validate_production_principal_policy(
            role="MODEL_REVIEWER",
            privileged_identity_authorized=False,
            visibility_authorized=False,
            export_authorized=False,
        )
    assert captured.value.code == "ROLE_NOT_AUTHORIZED"


def test_explicit_grants_preserve_existing_fail_closed_rules() -> None:
    with pytest.raises(PrincipalPolicyError) as analyst:
        validate_production_principal_policy(
            role="ANALYST",
            privileged_identity_authorized=True,
            visibility_authorized=False,
            export_authorized=False,
        )
    assert analyst.value.code == "ROLE_PRIVILEGE_ESCALATION"

    with pytest.raises(PrincipalPolicyError) as instructor:
        validate_production_principal_policy(
            role="INSTRUCTOR_EVALUATOR",
            privileged_identity_authorized=False,
            visibility_authorized=False,
            export_authorized=True,
        )
    assert instructor.value.code == "EXPORT_PRIVILEGE_ESCALATION"


def test_permission_status_reports_gaps_without_granting_them() -> None:
    status = permission_governance_status()
    assert status["status"] == "PARTIAL"
    assert status["default_decision"] == "DENY"
    assert status["canonical_roles_not_admitted_for_production"] == [
        "MODEL_REVIEWER"
    ]
    assert status["unwired_high_risk_permissions"] == [
        "MODEL_RELEASE",
        "PRODUCT_PUBLISH",
        "PUBLICATION_OVERRIDE",
        "PLUGIN_INSTALL",
    ]
    assert status["design_role_mapping"] == "PRODUCT_DECISION_REQUIRED"


def test_reported_role_gap_matches_frozen_canonical_profiles() -> None:
    p4_p5 = json.loads(
        (AUTHORITY / "P4_P5_ROLE_PRIVACY_PROFILE.json").read_text(
            encoding="utf-8"
        )
    )
    p6 = json.loads(
        (AUTHORITY / "P6_ROLE_PRIVACY_RELEASE_PROFILE.json").read_text(
            encoding="utf-8"
        )
    )
    canonical_roles = set(p4_p5["scope"]["role_families"])
    canonical_roles.update(p6["scope"]["role_families"])
    admitted_roles = {role.value for role in ProductionRole}

    assert canonical_roles - admitted_roles == {"MODEL_REVIEWER"}
    assert admitted_roles - canonical_roles == set()
