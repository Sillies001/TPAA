"""Exercise authenticated role defaults and a real permission-bound GUI task."""

from __future__ import annotations

import argparse
import getpass
import json
import os
import platform
from datetime import UTC, datetime, timedelta
from functools import partial
from pathlib import Path
from typing import cast

from tools.gui.w5_acceptance import _request_manifest
from tpaa_gui.design_system import Theme, configure_application_font, theme_stylesheet
from tpaa_gui.diagnostics import DiagnosticsSnapshot
from tpaa_gui.local_backend import LocalBackendController
from tpaa_gui.product_shell import create_product_workspace
from tpaa_security import ASSIGNMENT_SCHEMA, sign_assignment

_ROLE_DEFAULTS = {
    "TRAINEE": "P02",
    "INSTRUCTOR": "P03",
    "EVALUATOR": "P13",
    "TRAINING_MANAGER": "P11",
    "DATA_ENGINEER": "P12",
}
_SOURCE_IMPORT_ROLES = frozenset({"INSTRUCTOR", "DATA_ENGINEER"})


def _diagnostics(controller: LocalBackendController) -> DiagnosticsSnapshot:
    return controller.diagnostics


def _identity(role: str, *, key_name: str, key: str) -> dict[str, object]:
    now = datetime.now(UTC)
    payload: dict[str, object] = {
        "schema": ASSIGNMENT_SCHEMA,
        "key_id": key_name,
        "account_id": getpass.getuser(),
        "device_id": platform.node(),
        "subject": f"role-acceptance-{role.lower()}",
        "roles": [role],
        "scopes": ["*"],
        "issued_at": now.isoformat().replace("+00:00", "Z"),
        "expires_at": (now + timedelta(hours=1)).isoformat().replace("+00:00", "Z"),
    }
    return {
        **payload,
        "signature": sign_assignment(payload, key.encode("utf-8")),
    }


def run(work_root: Path, evidence_path: Path) -> dict[str, object]:
    from PySide6 import QtCore, QtGui, QtTest, QtWidgets

    work_root = work_root.resolve(strict=False)
    evidence_path = evidence_path.resolve(strict=False)
    work_root.mkdir(parents=True, exist_ok=False)
    app = cast(
        "QtWidgets.QApplication",
        QtWidgets.QApplication.instance()
        or QtWidgets.QApplication(["tpaa-role-task-acceptance"]),
    )
    configure_application_font(QtGui, app)
    app.setStyleSheet(theme_stylesheet(Theme.LIGHT, 96.0))
    source_bytes = json.dumps(
        _request_manifest(),
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    records: list[dict[str, object]] = []
    for role, expected_page in _ROLE_DEFAULTS.items():
        role_root = work_root / role.lower()
        data_root = role_root / "desktop-data"
        data_root.mkdir(parents=True)
        key_name = f"TPAA_ROLE_ACCEPTANCE_KEY_{role}"
        key = f"local-role-acceptance-{role.lower()}"
        identity_path = data_root / "desktop-identity.json"
        identity_path.write_text(
            json.dumps(
                _identity(role, key_name=key_name, key=key),
                sort_keys=True,
                separators=(",", ":"),
            ),
            encoding="utf-8",
        )
        os.environ[key_name] = key
        os.environ["TPAA_DESKTOP_IDENTITY_FILE"] = str(identity_path)
        os.environ["TPAA_DESKTOP_IDENTITY_KEY_REF"] = f"env://{key_name}"
        controller = LocalBackendController(
            product_build_version="1.0.0",
            data_root=data_root,
            startup_timeout_seconds=30.0,
        )
        window = QtWidgets.QMainWindow()
        try:
            controller.start()
            status_code, security_context = controller.security_request_json(
                "GET", "/security/session"
            )
            if status_code != 200 or security_context.get("roles") != [role]:
                raise RuntimeError(
                    f"ROLE_SESSION_CONTEXT_INVALID:{role}:{security_context!r}"
                )
            workspace = create_product_workspace(
                QtCore,
                QtWidgets,
                window,
                transport=controller,
                diagnostics_provider=partial(_diagnostics, controller),
            )
            window.setCentralWidget(workspace)
            window.resize(1440, 900)
            window.show()
            app.processEvents()
            role_button = workspace.findChild(
                QtWidgets.QPushButton,
                "tpaaApplyRoleView",
            )
            QtTest.QTest.mouseClick(role_button, QtCore.Qt.MouseButton.LeftButton)
            app.processEvents()
            selected_page = workspace._tpaa_shell_state.selection.page_id
            if selected_page != expected_page:
                raise RuntimeError(
                    f"ROLE_DEFAULT_PAGE_MISMATCH:{role}:{selected_page}"
                )
            screenshot = role_root / f"{role}_{expected_page}_1440x900.png"
            if not window.grab().save(str(screenshot), "PNG"):
                raise RuntimeError(f"ROLE_SCREENSHOT_FAILED:{role}")
            import_status, import_payload = controller.source_request_bytes(
                "/api/v1/sources/p1-request/stage",
                data=source_bytes,
                content_type="application/json",
            )
            expected_status = 201 if role in _SOURCE_IMPORT_ROLES else 403
            if import_status != expected_status:
                raise RuntimeError(
                    f"ROLE_IMPORT_POLICY_MISMATCH:{role}:{import_status}:"
                    f"{import_payload!r}"
                )
            records.append(
                {
                    "role": role,
                    "security_context_status": status_code,
                    "default_page": selected_page,
                    "expected_default_page": expected_page,
                    "source_import_http_status": import_status,
                    "source_import_expected_http_status": expected_status,
                    "screenshot": str(screenshot),
                    "passed": True,
                }
            )
        finally:
            window.close()
            app.processEvents()
            controller.shutdown()
    result: dict[str, object] = {
        "schema": "TPAA_GUI_ROLE_TASK_ACCEPTANCE_V1",
        "status": "PASS",
        "records": records,
        "role_count": len(records),
        "pushed": False,
        "production_deployed": False,
    }
    evidence_path.parent.mkdir(parents=True, exist_ok=True)
    evidence_path.write_text(
        json.dumps(result, indent=2, ensure_ascii=False, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return result


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--work-root", type=Path, required=True)
    parser.add_argument("--evidence", type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(run(args.work_root, args.evidence), sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
