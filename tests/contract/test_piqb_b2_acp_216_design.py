from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
BASE = ROOT / "docs" / "baseline" / "PIQB-1.0"
PROPOSAL = ROOT / "docs" / "proposals" / "ACP-216_EXACT_PERSISTENCE_SCHEMA_PROPOSAL.json"


def test_acp_216_is_proposal_only_and_does_not_adopt_schema() -> None:
    value = json.loads(PROPOSAL.read_text(encoding="utf-8"))
    assert value["schema"] == "TPAA_AUTHORITY_CHANGE_PROPOSAL_V1"
    assert value["proposal_id"] == "ACP-216"
    assert value["status"] == "PROPOSED_NOT_ADOPTED"
    assert value["current_authority"]["db_schema_version"] == "1.6.0"
    assert value["candidate_authority"]["db_schema_version"] == "1.7.0"
    assert value["candidate_authority"]["adoption_state"] == "NONE"
    assert value["candidate_authority"]["canonical_files_modified_by_this_proposal"] is False
    assert value["candidate_authority"]["migration_created_by_this_proposal"] is False


def test_acp_216_covers_every_current_schema_fit_blocker() -> None:
    fit = json.loads(
        (BASE / "B2_SCHEMA_PERSISTENCE_FIT.json").read_text(encoding="utf-8")
    )
    proposal = json.loads(PROPOSAL.read_text(encoding="utf-8"))
    expected = {
        (family["product_family"], blocker["field"])
        for family in fit["families"]
        for blocker in family.get("blockers", [])
    }
    covered_fields = {
        field
        for change in proposal["changes"]
        for field in change["covers_blockers"]
    }
    actual = {
        (family["product_family"], blocker["field"])
        for family in fit["families"]
        for blocker in family.get("blockers", [])
        if blocker["field"] in covered_fields
    }
    assert actual == expected
    assert proposal["blocker_coverage"]["uncovered"] == []


def test_acp_216_uses_named_relations_not_shadow_payloads() -> None:
    proposal = json.loads(PROPOSAL.read_text(encoding="utf-8"))
    relations = {change["relation"] for change in proposal["changes"]}
    assert "registry.mutation_idempotency" in relations
    assert "assessment.p4_subject_context" in relations
    assert "assessment.p5_composition_snapshot" in relations
    assert "intelligence.forecast_request" in relations
    assert "intelligence.counterfactual_request" in relations
    assert "intelligence.training_recommendation_revision" in relations

    serialized = json.dumps(proposal, sort_keys=True)
    for forbidden in (
        "audit.audit_log.old_value",
        "audit.audit_log.new_value",
        "validation_metrics as hidden",
        "backtest_metrics as hidden",
    ):
        assert forbidden not in serialized
