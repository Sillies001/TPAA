from __future__ import annotations

from collections.abc import Mapping
from typing import Any

import pytest

from tpaa_gui.local_backend import LocalBackendController, LocalBackendError


def test_product_surface_adapters_are_scoped_and_reuse_authenticated_transport(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    controller = LocalBackendController()
    calls: list[tuple[str, str, dict[str, object] | None, dict[str, str] | None]] = []

    def fake_request(
        method: str,
        path: str,
        *,
        body: dict[str, object] | None = None,
        headers: dict[str, str] | None = None,
    ) -> tuple[int, dict[str, Any]]:
        calls.append((method, path, body, headers))
        return 200, {"ok": True}

    monkeypatch.setattr(controller, "request_json", fake_request)
    assert controller.m3_request_json("GET", "/m3/workspace/x")[0] == 200
    assert controller.m4_request_json("POST", "/m4/debrief/annotations", body={"a": 1})[0] == 200
    assert controller.m6_request_json("GET", "/m6/p2/releases/x/estimates/y/comparison")[0] == 200
    assert controller.m7_request_json("GET", "/m7/p3/twins/x/estimates/y/workspace")[0] == 200
    assert controller.m8_request_json("GET", "/m8/workspace/p4/x/p5/y")[0] == 200
    assert controller.m9_request_json(
        "GET",
        "/m9/workspace/forecast/x/counterfactual/y/recommendation/z",
    )[0] == 200
    assert controller.runtime_request_json("GET", "/runtime/qualification")[0] == 200
    assert len(calls) == 7


def test_product_surface_adapters_fail_closed_on_cross_surface_or_runtime_mutation(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    controller = LocalBackendController()

    def unused(
        method: str,
        path: str,
        *,
        body: dict[str, object] | None = None,
        headers: dict[str, str] | None = None,
    ) -> tuple[int, dict[str, Any]]:
        raise AssertionError((method, path, body, headers))

    monkeypatch.setattr(controller, "request_json", unused)
    with pytest.raises(LocalBackendError, match="M7_HTTP_PATH_FORBIDDEN"):
        controller.m7_request_json("GET", "/m8/workspace/p4/x/p5/y")
    with pytest.raises(LocalBackendError, match="RUNTIME_HTTP_METHOD_FORBIDDEN"):
        controller.runtime_request_json("POST", "/runtime/qualification")
    with pytest.raises(LocalBackendError, match="RUNTIME_HTTP_PATH_FORBIDDEN"):
        controller.runtime_request_json("GET", "/runtime/not-authorized")


def test_m6_adapter_accepts_mapping_without_exposing_mutable_authority(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    controller = LocalBackendController()
    observed: list[Mapping[str, object] | None] = []

    def fake_request(
        method: str,
        path: str,
        *,
        body: dict[str, object] | None = None,
        headers: dict[str, str] | None = None,
    ) -> tuple[int, dict[str, Any]]:
        observed.append(body)
        return 200, {}

    monkeypatch.setattr(controller, "request_json", fake_request)
    controller.m6_request_json("POST", "/m6/p2/commands/example", body={"x": 1})
    assert observed == [{"x": 1}]
