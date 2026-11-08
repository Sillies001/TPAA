from __future__ import annotations

import io
import json
import os
import zipfile
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication, QFileDialog, QWidget

from tpaa_gui.local_backend import WebEngineBinding
from tpaa_gui.native_import import NativeImportBridge


class _CapturingBridge(NativeImportBridge):
    captured: tuple[str, str, bytes] | None = None

    def _upload(self, *, kind: str, display_name: str, data: bytes) -> str:
        self.captured = (kind, display_name, data)
        return json.dumps(
            {"ticket_id": "g4-ticket", "kind": kind, "local_path": None},
            separators=(",", ":"),
        )


def _bridge() -> tuple[QApplication, QWidget, _CapturingBridge]:
    app = QApplication.instance() or QApplication(["tpaa-g4-native-import-test"])
    parent = QWidget()
    bridge = _CapturingBridge(
        WebEngineBinding(
            origin="http://127.0.0.1:43123",
            authorization_header=b"Bearer local-secret",
            desktop_nonce=b"desktop-nonce",
        ),
        parent,
    )
    return app, parent, bridge


def test_native_file_selection_returns_ticket_without_local_path(
    tmp_path: Path, monkeypatch,
) -> None:
    source = tmp_path / "flight.csv"
    source.write_text("source_time_us,session_time_us\n0,0\n", encoding="utf-8")
    app, parent, bridge = _bridge()
    monkeypatch.setattr(
        QFileDialog,
        "getOpenFileName",
        lambda *_args, **_kwargs: (str(source), "CSV 文件 (*.csv)"),
    )

    result = bridge.selectFile()

    assert str(tmp_path) not in result
    assert json.loads(result)["local_path"] is None
    assert bridge.captured == ("FILE", "flight.csv", source.read_bytes())
    parent.deleteLater()
    app.processEvents()


def test_native_directory_selection_packages_relative_csv_members_only(
    tmp_path: Path, monkeypatch,
) -> None:
    (tmp_path / "nested").mkdir()
    (tmp_path / "a.csv").write_text("a,b\n1,2\n", encoding="utf-8")
    (tmp_path / "nested" / "b.csv").write_text("a,b\n3,4\n", encoding="utf-8")
    (tmp_path / "ignored.txt").write_text("not imported", encoding="utf-8")
    app, parent, bridge = _bridge()
    monkeypatch.setattr(
        QFileDialog,
        "getExistingDirectory",
        lambda *_args, **_kwargs: str(tmp_path),
    )

    result = bridge.selectDirectory()

    assert str(tmp_path) not in result
    assert bridge.captured is not None
    kind, display_name, body = bridge.captured
    assert (kind, display_name) == ("DIRECTORY", "batch-directory.zip")
    with zipfile.ZipFile(io.BytesIO(body)) as archive:
        assert archive.namelist() == ["a.csv", "nested/b.csv"]
        assert all(not Path(name).is_absolute() and ".." not in Path(name).parts for name in archive.namelist())
    parent.deleteLater()
    app.processEvents()
