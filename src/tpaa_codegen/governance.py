from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path, PurePosixPath

from .errors import CodegenError, CodegenErrorContext, CodegenReason
from .models import GeneratedFile
from .provenance import GENERATED_MARKER

GOVERNED_ROOT = PurePosixPath("src/tpaa_generated")


@dataclass(frozen=True, slots=True)
class GeneratedTreeReport:
    expected_files: tuple[str, ...]
    python_files: tuple[str, ...]


def _error(reason: CodegenReason, identity: str, detail: str) -> CodegenError:
    return CodegenError(
        reason,
        CodegenErrorContext(
            generator_id="generated-source-governance",
            identity=identity,
            detail=detail,
        ),
    )


def _iter_governed_files(root: Path) -> set[str]:
    governed = root.joinpath(*GOVERNED_ROOT.parts)
    if not governed.exists():
        return set()
    paths: set[str] = set()
    for path in governed.rglob("*"):
        if not path.is_file():
            continue
        if "__pycache__" in path.parts or path.suffix == ".pyc":
            continue
        paths.add(path.relative_to(root).as_posix())
    return paths


def verify_generated_tree(repo_root: Path, files: tuple[GeneratedFile, ...]) -> GeneratedTreeReport:
    root = repo_root.resolve()
    expected = {file.relative_path.as_posix(): file for file in files}
    actual_paths = _iter_governed_files(root)
    expected_paths = set(expected)

    missing = sorted(expected_paths - actual_paths)
    if missing:
        raise _error(CodegenReason.GENERATED_FILE_MISSING, missing[0], "expected generated file is missing")

    unexpected = sorted(actual_paths - expected_paths)
    if unexpected:
        raise _error(
            CodegenReason.UNEXPECTED_GENERATED_FILE,
            unexpected[0],
            "file is not emitted by the approved generation coordinator",
        )

    python_files: list[str] = []
    for relative in sorted(expected):
        generated = expected[relative]
        target = root.joinpath(*generated.relative_path.parts)
        actual = target.read_bytes()
        if actual != generated.content:
            raise _error(
                CodegenReason.GENERATED_FILE_DRIFT,
                relative,
                f"expected_sha256={generated.sha256}",
            )
        if generated.relative_path.suffix == ".py":
            python_files.append(relative)
            if not actual.startswith((GENERATED_MARKER + "\n").encode("utf-8")):
                raise _error(
                    CodegenReason.PROVENANCE_HEADER_MISMATCH,
                    relative,
                    "generated Python source lacks the governed provenance marker",
                )

    return GeneratedTreeReport(
        expected_files=tuple(sorted(expected)),
        python_files=tuple(python_files),
    )
