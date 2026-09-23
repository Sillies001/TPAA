"""AST-based executable projection of the SDIB package dependency contract."""

from __future__ import annotations

import ast
import importlib.util
import json
import sys
from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True, slots=True)
class ArchitecturePolicy:
    schema: str
    authority: str
    transport_packages: frozenset[str]
    lower_layer_packages: frozenset[str]
    business_core_packages: frozenset[str]
    forbidden_first_party_edges: dict[str, frozenset[str]]
    forbidden_external_prefixes: dict[str, tuple[str, ...]]
    semantic_constraints_not_proven_by_import_scan: tuple[str, ...]


@dataclass(frozen=True, order=True, slots=True)
class ImportDependency:
    relative_file: str
    line: int
    source_package: str
    imported_module: str
    import_kind: str


@dataclass(frozen=True, order=True, slots=True)
class ArchitectureViolation:
    relative_file: str
    line: int
    source_package: str
    imported_module: str
    reason: str
    rule: str

    def as_dict(self) -> dict[str, object]:
        return {
            "file": self.relative_file,
            "line": self.line,
            "source_package": self.source_package,
            "imported_module": self.imported_module,
            "reason": self.reason,
            "rule": self.rule,
        }


def load_policy(path: Path) -> ArchitecturePolicy:
    raw = json.loads(path.read_text(encoding="utf-8"))
    if raw.get("schema") != "TPAA_ARCHITECTURE_POLICY_V1":
        raise ValueError("unsupported architecture policy schema")
    return ArchitecturePolicy(
        schema=str(raw["schema"]),
        authority=str(raw["authority"]),
        transport_packages=frozenset(map(str, raw["transport_packages"])),
        lower_layer_packages=frozenset(map(str, raw["lower_layer_packages"])),
        business_core_packages=frozenset(map(str, raw["business_core_packages"])),
        forbidden_first_party_edges={
            str(source): frozenset(map(str, targets))
            for source, targets in raw["forbidden_first_party_edges"].items()
        },
        forbidden_external_prefixes={
            str(source): tuple(map(str, prefixes))
            for source, prefixes in raw["forbidden_external_prefixes"].items()
        },
        semantic_constraints_not_proven_by_import_scan=tuple(
            map(str, raw["semantic_constraints_not_proven_by_import_scan"])
        ),
    )


def _module_for_path(path: Path, src_root: Path) -> tuple[str, str]:
    relative = path.relative_to(src_root)
    parts = list(relative.with_suffix("").parts)
    if parts[-1] == "__init__":
        parts.pop()
    module = ".".join(parts)
    source_package = parts[0] if parts else ""
    return module, source_package


def _resolve_from_import(module_name: str, path: Path, src_root: Path, level: int, module: str | None) -> str:
    if level == 0:
        return module or ""
    if path.name == "__init__.py":
        package = module_name
    else:
        package = module_name.rpartition(".")[0]
    relative_name = "." * level + (module or "")
    try:
        return importlib.util.resolve_name(relative_name, package)
    except (ImportError, ValueError):
        return relative_name


def _literal_dynamic_import(node: ast.Call) -> str | None:
    if not node.args or not isinstance(node.args[0], ast.Constant) or not isinstance(node.args[0].value, str):
        return None
    if isinstance(node.func, ast.Name) and node.func.id == "__import__":
        return node.args[0].value
    if (
        isinstance(node.func, ast.Attribute)
        and node.func.attr == "import_module"
        and isinstance(node.func.value, ast.Name)
        and node.func.value.id == "importlib"
    ):
        return node.args[0].value
    return None


def collect_imports(src_root: Path) -> tuple[list[ImportDependency], list[ArchitectureViolation], int]:
    dependencies: list[ImportDependency] = []
    parse_violations: list[ArchitectureViolation] = []
    scanned_files = 0
    for path in sorted(src_root.rglob("*.py")):
        if not path.is_file():
            continue
        scanned_files += 1
        relative = path.relative_to(src_root.parent).as_posix()
        module_name, source_package = _module_for_path(path, src_root)
        try:
            tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        except (SyntaxError, UnicodeError) as exc:
            line = int(getattr(exc, "lineno", 0) or 0)
            parse_violations.append(
                ArchitectureViolation(
                    relative_file=relative,
                    line=line,
                    source_package=source_package,
                    imported_module="<unparsed>",
                    reason="PYTHON_PARSE_ERROR",
                    rule=str(exc),
                )
            )
            continue
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    dependencies.append(
                        ImportDependency(relative, node.lineno, source_package, alias.name, "import")
                    )
            elif isinstance(node, ast.ImportFrom):
                imported = _resolve_from_import(
                    module_name, path, src_root, node.level, node.module
                )
                dependencies.append(
                    ImportDependency(relative, node.lineno, source_package, imported, "from")
                )
            elif isinstance(node, ast.Call):
                dynamic_imported = _literal_dynamic_import(node)
                if dynamic_imported:
                    dependencies.append(
                        ImportDependency(
                            relative,
                            node.lineno,
                            source_package,
                            dynamic_imported,
                            "dynamic-literal",
                        )
                    )
    return sorted(set(dependencies)), sorted(parse_violations), scanned_files


def _matches_prefix(module: str, prefix: str) -> bool:
    return module == prefix or module.startswith(prefix + ".")


def _first_party_root(module: str, first_party_packages: frozenset[str]) -> str | None:
    root = module.split(".", 1)[0]
    return root if root in first_party_packages else None


def evaluate_dependencies(
    dependencies: Iterable[ImportDependency],
    policy: ArchitecturePolicy,
    first_party_packages: frozenset[str],
) -> list[ArchitectureViolation]:
    violations: set[ArchitectureViolation] = set()
    stdlib = frozenset(sys.stdlib_module_names) | {"__future__"}

    for dep in dependencies:
        source = dep.source_package
        imported_root = _first_party_root(dep.imported_module, first_party_packages)

        if source in policy.lower_layer_packages and imported_root in policy.transport_packages:
            violations.add(
                ArchitectureViolation(
                    dep.relative_file,
                    dep.line,
                    source,
                    dep.imported_module,
                    "LOWER_LAYER_TRANSPORT_DEPENDENCY",
                    f"{source} must not depend on transport package {imported_root}",
                )
            )

        if source in policy.business_core_packages and imported_root == "tpaa_platform":
            violations.add(
                ArchitectureViolation(
                    dep.relative_file,
                    dep.line,
                    source,
                    dep.imported_module,
                    "BUSINESS_CORE_PLATFORM_IMPLEMENTATION_DEPENDENCY",
                    f"{source} must consume OS/native capability through a port, not tpaa_platform implementation",
                )
            )

        if imported_root and imported_root in policy.forbidden_first_party_edges.get(source, frozenset()):
            violations.add(
                ArchitectureViolation(
                    dep.relative_file,
                    dep.line,
                    source,
                    dep.imported_module,
                    "FORBIDDEN_FIRST_PARTY_DEPENDENCY",
                    f"SDIB Appendix E forbids {source} -> {imported_root}",
                )
            )

        for prefix in policy.forbidden_external_prefixes.get(source, ()):
            if _matches_prefix(dep.imported_module, prefix):
                violations.add(
                    ArchitectureViolation(
                        dep.relative_file,
                        dep.line,
                        source,
                        dep.imported_module,
                        "FORBIDDEN_EXTERNAL_DEPENDENCY",
                        f"SDIB Appendix E forbids {prefix} implementation leakage into {source}",
                    )
                )

        if source == "tpaa_generated":
            root = dep.imported_module.split(".", 1)[0]
            if root not in stdlib and root != "tpaa_generated":
                violations.add(
                    ArchitectureViolation(
                        dep.relative_file,
                        dep.line,
                        source,
                        dep.imported_module,
                        "GENERATED_NON_STDLIB_DEPENDENCY",
                        "tpaa_generated may depend on Python stdlib/self only at M0",
                    )
                )

    return sorted(violations)


def _policy_first_party_packages(policy: ArchitecturePolicy) -> frozenset[str]:
    packages: set[str] = set(policy.transport_packages)
    packages.update(policy.lower_layer_packages)
    packages.update(policy.business_core_packages)
    packages.update(policy.forbidden_first_party_edges)
    for targets in policy.forbidden_first_party_edges.values():
        packages.update(targets)
    return frozenset(packages)


def scan_architecture(src_root: Path, policy: ArchitecturePolicy) -> tuple[list[ArchitectureViolation], int, int]:
    dependencies, parse_violations, scanned_files = collect_imports(src_root)
    discovered = {
        path.name for path in src_root.iterdir() if path.is_dir() and path.name.startswith("tpaa_")
    }
    first_party_packages = frozenset(discovered) | _policy_first_party_packages(policy)
    violations = parse_violations + evaluate_dependencies(dependencies, policy, first_party_packages)
    return sorted(set(violations)), scanned_files, len(dependencies)
