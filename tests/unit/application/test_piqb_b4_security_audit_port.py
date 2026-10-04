from __future__ import annotations

from tpaa_application import (
    InMemoryM8AssessmentRepository,
    InMemoryM9P6Repository,
    InMemorySecurityAuditSink,
    M8ViewerContext,
    M8WorkspaceService,
    M9ViewerContext,
    M9WorkspaceService,
)


def test_b4_m8_security_event_flows_through_application_audit_port() -> None:
    sink = InMemorySecurityAuditSink()
    service = M8WorkspaceService(
        InMemoryM8AssessmentRepository(),
        security_audit_sink=sink,
    )
    viewer = M8ViewerContext(
        viewer_role="ANALYST",
        viewer_actor_id=None,
        scope_match=True,
    )

    service._audit(
        viewer,
        action="P4_READ",
        object_ref="22222222-2222-4222-8222-222222222222",
        outcome="ALLOW",
    )

    assert len(sink.events) == 1
    event = sink.events[0]
    assert event.actor_id is None
    assert event.principal_key == "ROLE:ANALYST"
    assert event.action == "P4_READ"
    assert event.object_type == "M8_SECURITY_EVENT"
    assert event.outcome == "ALLOW"


def test_b4_p6_security_event_flows_through_application_audit_port() -> None:
    sink = InMemorySecurityAuditSink()
    service = M9WorkspaceService(
        InMemoryM9P6Repository(),
        security_audit_sink=sink,
    )
    viewer = M9ViewerContext(
        role="MODEL_REVIEWER",
        actor_id="11111111-1111-4111-8111-111111111111",
        scope_match=True,
        validation_only=True,
    )

    service._record(
        viewer,
        action="MODEL_READ",
        object_ref="33333333-3333-4333-8333-333333333333",
        outcome="ALLOW",
        request_id="b4-security-read-1",
    )

    assert len(sink.events) == 1
    event = sink.events[0]
    assert event.actor_id == "11111111-1111-4111-8111-111111111111"
    assert event.action == "MODEL_READ"
    assert event.object_type == "P6_SECURITY_EVENT"
    assert event.request_id == "b4-security-read-1"
    assert event.outcome == "ALLOW"
