"""Qt-native G4 source picker that returns only governed backend tickets."""

from __future__ import annotations

import io
import json
import urllib.error
import urllib.request
import zipfile
from pathlib import Path
from urllib.parse import quote

from PySide6.QtCore import QObject, Slot
from PySide6.QtWidgets import QFileDialog, QWidget

from tpaa_application import SOURCE_MAX_ARTIFACT_BYTES

from .local_backend import WebEngineBinding

_MAX_DIRECTORY_MEMBERS = 32


class NativeImportBridge(QObject):
    """Blocking native picker exposed through QWebChannel.

    Physical paths are used only inside this adapter and are never serialized
    to JavaScript or sent to the backend.
    """

    def __init__(self, binding: WebEngineBinding, parent: QWidget) -> None:
        super().__init__(parent)
        self._binding = binding
        self._parent = parent

    @staticmethod
    def _error(code: str) -> str:
        return json.dumps({"error": code}, separators=(",", ":"))

    @staticmethod
    def _bounded_read(path: Path) -> bytes:
        try:
            with path.open("rb") as stream:
                data = stream.read(SOURCE_MAX_ARTIFACT_BYTES + 1)
        except OSError as exc:
            raise RuntimeError("NATIVE_IMPORT_READ_FAILED") from exc
        if not data or len(data) > SOURCE_MAX_ARTIFACT_BYTES:
            raise RuntimeError("NATIVE_IMPORT_SIZE_INVALID")
        return data

    def _upload(self, *, kind: str, display_name: str, data: bytes) -> str:
        request = urllib.request.Request(
            f"{self._binding.origin}/api/v1/gui/import-tickets",
            data=data,
            method="POST",
            headers={
                "Authorization": self._binding.authorization_header.decode("ascii"),
                "X-TPAA-Desktop-Nonce": self._binding.desktop_nonce.decode("ascii"),
                "X-TPAA-Ticket-Kind": kind,
                "X-TPAA-Display-Name": quote(display_name, safe=""),
                "Content-Type": "text/csv" if kind == "FILE" else "application/zip",
                "Accept": "application/json",
                "Origin": self._binding.origin,
            },
        )
        try:
            with urllib.request.urlopen(request, timeout=30.0) as response:  # noqa: S310
                body = response.read(SOURCE_MAX_ARTIFACT_BYTES + 1)
        except urllib.error.HTTPError as exc:
            try:
                payload = json.loads(exc.read().decode("utf-8"))
            except (UnicodeDecodeError, json.JSONDecodeError):
                payload = {}
            code = payload.get("code") if isinstance(payload, dict) else None
            return self._error(code if isinstance(code, str) else f"HTTP_{exc.code}")
        except (OSError, TimeoutError):
            return self._error("NATIVE_IMPORT_BACKEND_UNAVAILABLE")
        if len(body) > SOURCE_MAX_ARTIFACT_BYTES:
            return self._error("NATIVE_IMPORT_RESPONSE_INVALID")
        try:
            payload = json.loads(body.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError):
            return self._error("NATIVE_IMPORT_RESPONSE_INVALID")
        if not isinstance(payload, dict) or not isinstance(payload.get("ticket_id"), str):
            return self._error("NATIVE_IMPORT_RESPONSE_INVALID")
        payload["local_path"] = None
        return json.dumps(payload, ensure_ascii=False, separators=(",", ":"))

    @Slot(result=str)
    def selectFile(self) -> str:  # noqa: N802
        path, _filter = QFileDialog.getOpenFileName(
            self._parent,
            "选择飞行记录 CSV 文件",
            "",
            "CSV 文件 (*.csv)",
        )
        if not path:
            return "null"
        candidate = Path(path)
        if candidate.suffix.lower() != ".csv":
            return self._error("NATIVE_IMPORT_MEDIA_TYPE_INVALID")
        try:
            data = self._bounded_read(candidate)
        except RuntimeError as exc:
            return self._error(str(exc))
        return self._upload(kind="FILE", display_name=candidate.name, data=data)

    @Slot(result=str)
    def selectDirectory(self) -> str:  # noqa: N802
        selected = QFileDialog.getExistingDirectory(
            self._parent,
            "选择飞行记录 CSV 目录",
            "",
            QFileDialog.Option.ShowDirsOnly,
        )
        if not selected:
            return "null"
        root = Path(selected)
        try:
            files = sorted(
                (path for path in root.rglob("*.csv") if path.is_file()),
                key=lambda path: path.relative_to(root).as_posix(),
            )
        except OSError:
            return self._error("NATIVE_IMPORT_DIRECTORY_READ_FAILED")
        if not files or len(files) > _MAX_DIRECTORY_MEMBERS:
            return self._error("NATIVE_IMPORT_DIRECTORY_COUNT_INVALID")
        stream = io.BytesIO()
        total = 0
        try:
            with zipfile.ZipFile(stream, "w", compression=zipfile.ZIP_DEFLATED) as archive:
                for path in files:
                    data = self._bounded_read(path)
                    total += len(data)
                    if total > SOURCE_MAX_ARTIFACT_BYTES:
                        return self._error("NATIVE_IMPORT_SIZE_INVALID")
                    archive.writestr(path.relative_to(root).as_posix(), data)
        except (OSError, RuntimeError, zipfile.BadZipFile) as exc:
            return self._error(str(exc) or "NATIVE_IMPORT_DIRECTORY_READ_FAILED")
        return self._upload(kind="DIRECTORY", display_name="batch-directory.zip", data=stream.getvalue())


__all__ = ["NativeImportBridge"]
