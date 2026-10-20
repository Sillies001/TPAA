"""W3 approval inbox routes; high-risk execution stays on the unified guard."""

from __future__ import annotations

from fastapi import FastAPI, HTTPException, Request, status
from pydantic import BaseModel, ConfigDict

from tpaa_security import ApprovalError, ApprovalRequest, ApprovalService, Permission


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
