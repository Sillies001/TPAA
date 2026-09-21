from __future__ import annotations

from pathlib import Path

from tools.architecture.dependency_policy import load_policy, scan_architecture


REPO_ROOT = Path(__file__).resolve().parents[3]
POLICY = load_policy(REPO_ROOT / "tools" / "architecture" / "ARCHITECTURE_POLICY.json")


def _scan(tmp_path: Path, package: str, source: str) -> list[str]:
    src = tmp_path / "src"
    target = src / package
    target.mkdir(parents=True)
    (target / "__init__.py").write_text(source, encoding="utf-8", newline="\n")
    violations, _, _ = scan_architecture(src, POLICY)
    return [item.reason for item in violations]


def test_lower_layer_static_import_of_gui_is_rejected(tmp_path: Path) -> None:
    reasons = _scan(tmp_path, "tpaa_metric", "import tpaa_gui\n")
    assert "LOWER_LAYER_TRANSPORT_DEPENDENCY" in reasons


def test_lower_layer_from_import_of_api_is_rejected(tmp_path: Path) -> None:
    reasons = _scan(tmp_path, "tpaa_world", "from tpaa_api import client\n")
    assert "LOWER_LAYER_TRANSPORT_DEPENDENCY" in reasons


def test_business_core_platform_implementation_import_is_rejected(tmp_path: Path) -> None:
    reasons = _scan(tmp_path, "tpaa_context", "from tpaa_platform import native\n")
    assert "BUSINESS_CORE_PLATFORM_IMPLEMENTATION_DEPENDENCY" in reasons


def test_literal_dynamic_import_is_detected(tmp_path: Path) -> None:
    reasons = _scan(
        tmp_path,
        "tpaa_metric",
        'import importlib\nmod = importlib.import_module("tpaa_gui.internal")\n',
    )
    assert "LOWER_LAYER_TRANSPORT_DEPENDENCY" in reasons


def test_literal_dunder_import_is_detected(tmp_path: Path) -> None:
    reasons = _scan(tmp_path, "tpaa_application", 'mod = __import__("tpaa_platform.native")\n')
    assert "BUSINESS_CORE_PLATFORM_IMPLEMENTATION_DEPENDENCY" in reasons


def test_relative_same_package_import_is_allowed(tmp_path: Path) -> None:
    src = tmp_path / "src"
    target = src / "tpaa_metric"
    target.mkdir(parents=True)
    (target / "__init__.py").write_text("from .engine import VALUE\n", encoding="utf-8")
    (target / "engine.py").write_text("VALUE = 1\n", encoding="utf-8")
    violations, _, _ = scan_architecture(src, POLICY)
    assert violations == []


def test_parse_error_fails_closed(tmp_path: Path) -> None:
    reasons = _scan(tmp_path, "tpaa_world", "def broken(:\n")
    assert "PYTHON_PARSE_ERROR" in reasons


def test_generated_non_stdlib_dependency_is_rejected(tmp_path: Path) -> None:
    reasons = _scan(tmp_path, "tpaa_generated", "import polars\n")
    assert "GENERATED_NON_STDLIB_DEPENDENCY" in reasons


def test_forbidden_external_framework_import_is_rejected(tmp_path: Path) -> None:
    reasons = _scan(tmp_path, "tpaa_canonical", "import fastapi\n")
    assert "FORBIDDEN_EXTERNAL_DEPENDENCY" in reasons


def test_violation_output_is_deterministic(tmp_path: Path) -> None:
    src = tmp_path / "src"
    target = src / "tpaa_metric"
    target.mkdir(parents=True)
    (target / "b.py").write_text("import tpaa_gui\n", encoding="utf-8")
    (target / "a.py").write_text("import tpaa_api\n", encoding="utf-8")
    first, _, _ = scan_architecture(src, POLICY)
    second, _, _ = scan_architecture(src, POLICY)
    assert first == second
    assert [item.relative_file for item in first] == sorted(item.relative_file for item in first)
