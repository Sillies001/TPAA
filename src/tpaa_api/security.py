"""W3 approval inbox routes; high-risk execution stays on the unified guard."""

from __future__ import annotations

from fastapi import FastAPI, HTTPException, Request, status
from pydantic import BaseModel, ConfigDict

from tpaa_security import (
    GUI_ACTIVATION_STATUS,
    GUI_AUTHORITY_ID,
    GUI_AUTHORITY_VERSION,
    ApprovalError,
    ApprovalRequest,
    ApprovalService,
    Permission,
    derive_gui_permissions,
    load_security_policy,
)


class ApprovalRequestBody(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    permission: str
    target_path: str
    reason: str


class ApprovalDecisionBody(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    approve: bool
    reason: str


def _principal(request: Request):  # type: ignore[no-untyped-def]
    from .unified import UnifiedPrincipal

    value = getattr(request.state, "tpaa_principal", None)
    if not isinstance(value, UnifiedPrincipal):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="PRINCIPAL_REQUIRED",
        )
    return value.authorization_principal()


def _payload(value: ApprovalRequest) -> dict[str, object]:
    return {
        "approval_id": value.approval_id,
        "permission": value.permission.value,
        "target_type": value.target_type,
        "target_id": value.target_id,
        "target_sha256": value.target_sha256,
        "maker_subject": value.maker_subject,
        "status": value.status.value,
        "created_at": value.created_at.isoformat().replace("+00:00", "Z"),
        "expires_at": value.expires_at.isoformat().replace("+00:00", "Z"),
        "checker_subject": value.checker_subject,
    }


def register_security_routes(app: FastAPI, approvals: ApprovalService) -> None:
    @app.get("/security/session")
    def session_context(request: Request) -> dict[str, object]:
        principal = _principal(request)
        policy = load_security_policy()
        permissions = sorted(
            {
                permission.value
                for role in principal.roles
                for permission in policy.role_permissions.get(role, frozenset())
            }
        )
        permission_values = frozenset(Permission(value) for value in permissions)
        gui_permissions = derive_gui_permissions(principal.roles, permission_values)
        return {
            "schema": "TPAA_SECURITY_SESSION_CONTEXT_V1",
            "roles": sorted(role.value for role in principal.roles),
            "projection_role": policy.projection_role(principal.roles),
            "permissions": permissions,
            "gui_permissions": list(gui_permissions),
            "gui_permission_authority_id": GUI_AUTHORITY_ID,
            "gui_permission_authority_version": GUI_AUTHORITY_VERSION,
            "gui_permission_activation_status": GUI_ACTIVATION_STATUS,
            "policy_sha256": policy.sha256,
        }

    @app.get("/security/approvals")
    def approval_inbox(request: Request) -> dict[str, object]:
        try:
            items = approvals.inbox(_principal(request))
        except ApprovalError as exc:
            raise HTTPException(status_code=403, detail=exc.code) from exc
        return {"schema": "TPAA_APPROVAL_INBOX_V1", "items": [_payload(item) for item in items]}

    @app.post("/security/approvals", status_code=status.HTTP_201_CREATED)
    def request_approval(body: ApprovalRequestBody, request: Request) -> dict[str, object]:
        try:
            permission = Permission(body.permission)
            item = approvals.request(
                _principal(request),
                permission,
                target_type="API_PATH",
                target_id=body.target_path,
                target={"path": body.target_path},
                reason=body.reason,
            )
        except (ApprovalError, ValueError) as exc:
            code = exc.code if isinstance(exc, ApprovalError) else "PERMISSION_INVALID"
            raise HTTPException(status_code=403, detail=code) from exc
        return _payload(item)

    @app.post("/security/approvals/{approval_id}/decision")
    def decide_approval(
        approval_id: str,
        body: ApprovalDecisionBody,
        request: Request,
    ) -> dict[str, object]:
        try:
            item = approvals.decide(
                _principal(request),
                approval_id,
                approve=body.approve,
                reason=body.reason,
            )
        except ApprovalError as exc:
            raise HTTPException(status_code=403, detail=exc.code) from exc
        return _payload(item)


__all__ = ["register_security_routes"]
