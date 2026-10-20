from __future__ import annotations

from pathlib import Path

import tpaa_desktop.__main__ as desktop_cli


def test_desktop_main_forwards_packaged_root_and_data_root(
    tmp_path: Path,
    monkeypatch,
) -> None:
    app_root = tmp_path / "app"
    data_root = tmp_path / "data"
    backend = object()
    observed: dict[str, object] = {}

    def project_version(root: Path | None = None) -> str:
        observed["app_root"] = root
        return "1.0.0"

    def controller(**kwargs):
        observed["controller"] = kwargs
        return backend

    def run_desktop(argv, *, backend):
        observed["qt_args"] = argv
        observed["backend"] = backend
        return 0

    monkeypatch.setattr(desktop_cli, "project_version", project_version)
    monkeypatch.setattr(desktop_cli, "LocalBackendController", controller)
    monkeypatch.setattr(desktop_cli, "run_desktop", run_desktop)

    assert (
        desktop_cli.main(
            ["--data-root", str(data_root), "-style", "fusion"],
            app_root=app_root,
        )
        == 0
    )
    assert observed == {
        "app_root": app_root,
        "controller": {
            "product_build_version": "1.0.0",
            "data_root": data_root,
        },
        "qt_args": ["-style", "fusion"],
        "backend": backend,
    }
