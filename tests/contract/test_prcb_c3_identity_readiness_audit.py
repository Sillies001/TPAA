from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def test_prcb_c3_identity_readiness_and_job_audit_are_production_wired() -> None:
    config = (ROOT / "src" / "tpaa_runtime" / "config.py").read_text(
        encoding="utf-8"
    )
    identity = (ROOT / "src" / "tpaa_runtime" / "identity.py").read_text(
        encoding="utf-8"
    )
    production = (ROOT / "src" / "tpaa_runtime" / "production.py").read_text(
        encoding="utf-8"
    )
    jobs = (ROOT / "src" / "tpaa_runtime" / "durable_jobs.py").read_text(
        encoding="utf-8"
    )

    assert "service_principals" in config
    assert "credential_sha256" in config
    assert '"SYSTEM"' not in config
    assert "ConfiguredBearerIdentityProvider" in identity
    assert "hashlib.sha256" in identity
    assert "hmac.compare_digest" in identity
    assert "PRCB_C3_ROLE_NOT_AUTHORIZED" in identity
    assert "guard_production_principal_resolver" in production

    assert "ProductionDependencyProbe" in production
    assert "dependency_ready = {" not in production
    assert "dependency_ready=dependency_probe.phase_flags" in production
    assert "ProductionRuntimeReadiness" in production

    assert "del actor" not in jobs
    assert "AuditLogWrite(" in jobs
    assert '"JOB_SUBMIT"' in jobs
    assert '"JOB_CANCEL"' in jobs
    assert "uow.audit_log.append(" in jobs


def test_prcb_c3_governance_state_records_completed_handoff_to_c4() -> None:
    state = json.loads(
        (
            ROOT
            / "docs"
            / "baseline"
            / "PRCB-1.0"
            / "PRCB_IMPLEMENTATION_STATE.json"
        ).read_text(encoding="utf-8")
    )
    assert state["active_batch"] == "C4"
    assert state["task_state"]["C2"]["state"] == "COMPLETE"
    assert state["task_state"]["C3"]["state"] == "COMPLETE"
    assert state["task_state"]["C4"]["state"] == "ACTIVE"
    assert state["task_state"]["C5"]["state"] == "BLOCKED_BY_C4"
    assert state["qualification"]["formal_release_claimed"] is False
