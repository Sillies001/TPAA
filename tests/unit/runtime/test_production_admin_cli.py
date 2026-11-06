from __future__ import annotations

import json
from pathlib import Path

from tpaa_admin.__main__ import main


def _payload(text: str) -> dict[str, object]:
    value = json.loads(text)
    assert isinstance(value, dict)
    return value


def test_desktop_admin_init_verify_backup_restore(
    tmp_path: Path,
    capsys,
) -> None:
    source = tmp_path / "source"
    backup = tmp_path / "backup"
    restored = tmp_path / "restored"

    assert main(["init", "--data-root", str(source)]) == 0
    initialized = _payload(capsys.readouterr().out)
    assert initialized["status"] == "READY"
    assert initialized["db_schema_version"] == "1.9.0"
    assert initialized["backup"]["state"] == "NEVER_VERIFIED"

    object_file = source / "objects" / "operator" / "state.bin"
    object_file.parent.mkdir(parents=True)
    object_file.write_bytes(b"durable-state")

    assert main(["verify", "--data-root", str(source)]) == 0
    assert _payload(capsys.readouterr().out)["status"] == "READY"

    assert (
        main(
            [
                "backup",
                "--data-root",
                str(source),
                "--destination",
                str(backup),
            ]
        )
        == 0
    )
    assert _payload(capsys.readouterr().out)["status"] == "COMPLETE"

    assert main(["status", "--data-root", str(source)]) == 0
    status_payload = _payload(capsys.readouterr().out)
    assert status_payload["backup"]["state"] == "VERIFIED"
    assert "manifest_path" not in status_payload["backup"]

    assert (
        main(
            [
                "restore",
                "--data-root",
                str(restored),
                "--backup",
                str(backup),
            ]
        )
        == 0
    )
    restored_payload = _payload(capsys.readouterr().out)
    assert restored_payload["status"] == "READY"
    assert restored_payload["backup"]["state"] == "VERIFIED"
    assert (restored / "objects" / "operator" / "state.bin").read_bytes() == b"durable-state"


def test_admin_rejects_relative_data_root_without_leaking_detail(capsys) -> None:
    assert main(["status", "--data-root", "relative-data"]) == 2
    captured = capsys.readouterr()
    payload = _payload(captured.err)
    assert payload == {
        "schema": "TPAA_ADMIN_RESULT_V1",
        "command": "status",
        "status": "FAILED",
        "error_type": "ValueError",
    }
    assert "relative-data" not in captured.err


def test_admin_permissions_reports_completed_default_deny_policy(capsys) -> None:
    assert main(["permissions"]) == 0
    payload = _payload(capsys.readouterr().out)
    assert payload["schema"] == "TPAA_ADMIN_RESULT_V1"
    assert payload["command"] == "permissions"
    governance = payload["permission_governance"]
    assert isinstance(governance, dict)
    assert governance["status"] == "COMPLETE"
    assert governance["default_decision"] == "DENY"
    assert governance["canonical_roles_not_admitted_for_production"] == []
    assert governance["maker_checker"] == "REQUIRED"


def test_admin_issues_signed_desktop_identity_without_echoing_secret(
    tmp_path: Path,
    capsys,
    monkeypatch,
) -> None:
    monkeypatch.setenv("TPAA_TEST_DESKTOP_IDENTITY_KEY", "not-returned-secret")
    assert (
        main(
            [
                "identity-issue",
                "--data-root",
                str(tmp_path),
                "--subject",
                "00000000-0000-4000-8000-000000000001",
                "--role",
                "INSTRUCTOR",
                "--scope",
                "*",
                "--key-ref",
                "env://TPAA_TEST_DESKTOP_IDENTITY_KEY",
            ]
        )
        == 0
    )
    output = capsys.readouterr().out
    assert "not-returned-secret" not in output
    payload = _payload(output)
    assert payload["status"] == "COMPLETE"
    identity = json.loads((tmp_path / "desktop-identity.json").read_text(encoding="utf-8"))
    assert identity["roles"] == ["INSTRUCTOR"]
    assert len(identity["signature"]) == 64


def test_admin_source_stage_returns_managed_immutable_reference(
    tmp_path: Path,
    capsys,
) -> None:
    data_root = tmp_path / "data"
    source_file = tmp_path / "source.json"
    source_file.write_text('{"schema":"TEST"}', encoding="utf-8")
    artifact_id = "d6000000-0000-4000-8000-000000000002"
    assert main(["init", "--data-root", str(data_root)]) == 0
    capsys.readouterr()

    assert (
        main(
            [
                "source-stage",
                "--data-root",
                str(data_root),
                "--artifact-id",
                artifact_id,
                "--source-file",
                str(source_file),
            ]
        )
        == 0
    )
    payload = _payload(capsys.readouterr().out)
    reference = payload["source_artifact"]
    assert isinstance(reference, dict)
    assert reference["logical_uri"] == (f"tpaa-object://source-ingress/{artifact_id}/source.json")
    assert reference["byte_size"] == len(source_file.read_bytes())
    assert len(str(reference["artifact_sha256"])) == 64
    assert payload["source_import_binding"] == {
        "source_ref": reference["logical_uri"],
        "uri_kind": "MANAGED",
    }
