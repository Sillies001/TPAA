from __future__ import annotations

import pytest

from tools.governance.m1_entry_assign_roles import render


def _blocked_roles() -> dict[str, object]:
    return {
        "schema": "TPAA_M1_ROLE_ASSIGNMENTS_V1",
        "status": "UNASSIGNED",
        "primary_ws_owner": None,
        "golden_independent_reviewer": None,
        "m1_exit_reviewer": None,
        "golden_independence_attestation": None,
    }


def _blocked_review() -> dict[str, object]:
    return {
        "schema": "TPAA_M1_ENTRY_GATE_REVIEW_V1",
        "conditions": [
            {
                "id": index,
                "status": "BLOCKED_UNASSIGNED" if index == 8 else "PASS",
                "evidence": "existing evidence",
            }
            for index in range(1, 11)
        ],
        "pass_count": 9,
        "condition_count": 10,
        "decision": "M1_NOT_ADMITTED",
        "blocking_conditions": [8],
        "implementation_authorized": False,
    }


def test_role_renderer_creates_candidate_but_never_admits_m1() -> None:
    roles, review = render(
        roles=_blocked_roles(),
        review=_blocked_review(),
        primary_ws_owner="owner-one",
        golden_independent_reviewer="reviewer-two",
        m1_exit_reviewer="reviewer-three",
        golden_independence_attestation=(
            "reviewer-two is independent of the implementation and expected-result author"
        ),
    )
    assert roles["status"] == "ASSIGNED"
    assert roles["primary_ws_owner"] == "owner-one"
    assert roles["golden_independent_reviewer"] == "reviewer-two"
    assert roles["m1_exit_reviewer"] == "reviewer-three"
    assert roles["assignment_source"] == "EXPLICIT_HUMAN_ASSIGNMENT"

    conditions = {item["id"]: item["status"] for item in review["conditions"]}
    assert conditions[8] == "PASS"
    assert conditions[6] == "RUNTIME_VERIFY_REQUIRED"
    assert all(conditions[index] == "PASS" for index in (1, 2, 3, 4, 5, 7, 9, 10))
    assert review["decision"] == "M1_ADMISSION_CANDIDATE"
    assert review["blocking_conditions"] == ["MERGED_MAIN_RUNTIME_EVIDENCE"]
    assert review["implementation_authorized"] is False
    assert review["pass_count"] == 9


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("primary_ws_owner", ""),
        ("golden_independent_reviewer", "<reviewer>"),
        ("m1_exit_reviewer", "   "),
    ],
)
def test_role_renderer_rejects_placeholder_or_empty_identity(field: str, value: str) -> None:
    kwargs = {
        "primary_ws_owner": "owner-one",
        "golden_independent_reviewer": "reviewer-two",
        "m1_exit_reviewer": "reviewer-three",
        "golden_independence_attestation": "explicit independent-review attestation",
    }
    kwargs[field] = value
    with pytest.raises(ValueError):
        render(
            roles=_blocked_roles(),
            review=_blocked_review(),
            **kwargs,
        )


def test_role_renderer_rejects_missing_independence_attestation() -> None:
    with pytest.raises(ValueError):
        render(
            roles=_blocked_roles(),
            review=_blocked_review(),
            primary_ws_owner="owner-one",
            golden_independent_reviewer="reviewer-two",
            m1_exit_reviewer="reviewer-three",
            golden_independence_attestation="",
        )
