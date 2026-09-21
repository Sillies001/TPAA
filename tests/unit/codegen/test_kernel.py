from __future__ import annotations

from pathlib import PurePosixPath

import pytest

from tpaa_codegen import CodegenError, CodegenReason, GeneratedFile
from tpaa_codegen.coordinator import GenerationCoordinator
from tpaa_codegen.models import GenerationResult
from tpaa_codegen.naming import project_unique_identifiers, python_identifier
from tpaa_codegen.rendering import render_json, render_python


class _LoaderStub:
    expected_core_baseline = "CB-TEST"
    trusted_lock_sha256 = "a" * 64


class _Generator:
    def __init__(self, generator_id: str, path: str, content: bytes) -> None:
        self.generator_id = generator_id
        self.path = path
        self.content = content

    def generate(self, loader: object) -> GenerationResult:
        del loader
        return GenerationResult.create(
            generator_id=self.generator_id,
            sources=(),
            files=(GeneratedFile(PurePosixPath(self.path), self.content),),
        )


def test_python_identifier_projection_is_deterministic() -> None:
    assert python_identifier("P-1.2", generator_id="g", artifact_id="A") == "P_1_2"
    assert python_identifier("class", generator_id="g", artifact_id="A") == "class_"
    assert python_identifier("1ABC", generator_id="g", artifact_id="A") == "_1ABC"


def test_identifier_collision_fails_closed() -> None:
    with pytest.raises(CodegenError) as exc_info:
        project_unique_identifiers(["A-B", "A_B"], generator_id="g", artifact_id="A")
    assert exc_info.value.reason is CodegenReason.DUPLICATE_IDENTIFIER


def test_render_python_is_utf8_lf_with_one_final_newline() -> None:
    rendered = render_python(["α = 1", "", "value = 2\n"])
    assert rendered == "α = 1\n\nvalue = 2\n".encode()
    assert b"\r\n" not in rendered


def test_render_json_is_key_sorted_and_deterministic() -> None:
    assert render_json({"z": 1, "a": 2}) == b'{\n  "a": 2,\n  "z": 1\n}\n'


def test_same_ir_produces_identical_bytes() -> None:
    generator = _Generator("g", "src/tpaa_generated/x.py", b"x = 1\n")
    coordinator = GenerationCoordinator(_LoaderStub(), [generator])  # type: ignore[arg-type]
    assert tuple(file.content for file in coordinator.build().files) == tuple(
        file.content for file in coordinator.build().files
    )


def test_output_path_collision_fails_closed() -> None:
    coordinator = GenerationCoordinator(  # type: ignore[arg-type]
        _LoaderStub(),
        [
            _Generator("a", "src/tpaa_generated/x.py", b"a\n"),
            _Generator("b", "src/tpaa_generated/x.py", b"b\n"),
        ],
    )
    with pytest.raises(CodegenError) as exc_info:
        coordinator.build()
    assert exc_info.value.reason is CodegenReason.OUTPUT_PATH_COLLISION


def test_manifest_path_is_reserved() -> None:
    coordinator = GenerationCoordinator(  # type: ignore[arg-type]
        _LoaderStub(),
        [_Generator("a", "src/tpaa_generated/_generation_manifest.json", b"{}\n")],
    )
    with pytest.raises(CodegenError) as exc_info:
        coordinator.build()
    assert exc_info.value.reason is CodegenReason.OUTPUT_PATH_COLLISION
