from __future__ import annotations

import json
from pathlib import Path

from tpaa_security import HIGH_RISK_PERMISSIONS, Permission, SecurityRole, load_security_policy

ROOT = Path(__file__).resolve().parents[2]


def test_w3_policy_is_complete_default_deny_and_packaged() -> None:
    policy = load_security_policy()
    assert policy.document["default_decision"] == "DENY"
    assert set(policy.role_permissions) == set(SecurityRole)
    assert set(policy.high_risk_rules) == HIGH_RISK_PERMISSIONS
    assert set(HIGH_RISK_PERMISSIONS) == {
        Permission.MODEL_RELEASE,
        Permission.PRODUCT_PUBLISH,
        Permission.PUBLICATION_OVERRIDE,
        Permission.PLUGIN_INSTALL,
    }
    package = (ROOT / "pyproject.toml").read_text(encoding="utf-8")
    assert 'tpaa_security = ["TPAA_SECURITY_POLICY_V1.json"]' in package


def test_w3_public_service_requires_oidc_mtls_runtime_document() -> None:
    entry = (ROOT / "src" / "tpaa_runtime" / "entry_config.py").read_text(
        encoding="utf-8"
    )
    federated = (ROOT / "src" / "tpaa_runtime" / "federated_identity.py").read_text(
        encoding="utf-8"
    )
    assert 'raise ValueError("TPAA_RUNTIME_CONFIG_FILE is required for Service")' in entry
    assert '"mode") != "OIDC_MTLS"' in entry
    assert "client_cert_chain" in federated
    assert "x-tpaa-client-cert" not in federated.lower()


def test_w3_compliance_matrix_has_no_unresolved_stage_requirement() -> None:
    matrix = json.loads(
        (ROOT / "docs" / "compliance" / "W3_COMPLIANCE_MATRIX.json").read_text(
            encoding="utf-8"
        )
    )
    assert matrix["status"] == "CLOSED_LOCAL_PASS"
    assert len(matrix["requirements"]) == 6
    assert all(
        str(item["status"]).startswith(("PASS", "POLICY_FROZEN"))
        for item in matrix["requirements"]
    )
