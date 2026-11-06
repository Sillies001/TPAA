"""Approved CB-1.7.0 GUI permission derivation boundary."""

from __future__ import annotations

from collections.abc import Iterable

from .generated_g2_authority import (
    GUI_ACTIVATION_STATUS,
    GUI_AUTHORITY_ID,
    GUI_AUTHORITY_VERSION,
    GUI_PERMISSION_BINDINGS,
    KNOWN_GUI_ROLES,
)
from .permissions import Permission, SecurityRole


class GuiPermissionAuthorityError(ValueError):
    """The generated GUI authority contains an unsupported binding."""


def derive_gui_permissions(
    roles: Iterable[SecurityRole],
    business_permissions: Iterable[Permission],
) -> tuple[str, ...]:
    """Derive GUI grants without converting them into API authorization."""

    role_ids = {role.value for role in roles}
    if not role_ids or not role_ids.issubset(KNOWN_GUI_ROLES):
        return ()
    business_ids = {permission.value for permission in business_permissions}
    grants: list[str] = []
    for permission_id, binding_type, required_business in GUI_PERMISSION_BINDINGS:
        if binding_type == "AUTHENTICATED_KNOWN_ROLE":
            grants.append(permission_id)
        elif binding_type == "ANY_BUSINESS_PERMISSION":
            if business_ids.intersection(required_business):
                grants.append(permission_id)
        else:
            raise GuiPermissionAuthorityError(
                f"unsupported GUI permission binding: {binding_type}"
            )
    return tuple(sorted(grants))


__all__ = [
    "GUI_ACTIVATION_STATUS",
    "GUI_AUTHORITY_ID",
    "GUI_AUTHORITY_VERSION",
    "GuiPermissionAuthorityError",
    "derive_gui_permissions",
]
