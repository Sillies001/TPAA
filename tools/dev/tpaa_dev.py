#!/usr/bin/env python3
"""Cross-platform developer command dispatcher for TPAA M0.

The dispatcher is intentionally standard-library-only. Project dependencies and
quality tools are executed through the frozen toolchain contract rather than
being imported by this bootstrap script.
"""

from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
TOOLCHAIN_PATH = REPO_ROOT / "tools" / "dev" / "TOOLCHAIN.json"
BASELINE_VERIFY = REPO_ROOT / "tools" / "baseline" / "verify_baseline.py"
CANONICAL_VERIFY = REPO_ROOT / "tools" / "canonical" / "verify_loader.py"
CODEGEN_GENERATE = REPO_ROOT / "tools" / "codegen" / "generate.py"
CODEGEN_VERIFY_GENERATED = REPO_ROOT / "tools" / "codegen" / "verify_generated.py"
CODEGEN_REGENERATE_DIFF = REPO_ROOT / "tools" / "codegen" / "regenerate_diff.py"
ARCHITECTURE_VERIFY = REPO_ROOT / "tools" / "architecture" / "verify_dependencies.py"
STORAGE_BOOTSTRAP = REPO_ROOT / "tools" / "storage" / "bootstrap_db.py"
POSTGRES_STORAGE = REPO_ROOT / "tools" / "storage" / "postgres_db.py"
REPOSITORY_POLICY_VERIFY = REPO_ROOT / "tools" / "storage" / "verify_repository_policy.py"
DESKTOP_LIFECYCLE_POLICY_VERIFY = REPO_ROOT / "tools" / "desktop" / "verify_desktop_lifecycle_policy.py"
SQLITE_REPOSITORY = REPO_ROOT / "tools" / "storage" / "sqlite_repository.py"
POSTGRES_REPOSITORY = REPO_ROOT / "tools" / "storage" / "postgres_repository.py"
API_SMOKE = REPO_ROOT / "tools" / "api" / "smoke.py"
GUI_SMOKE = REPO_ROOT / "tools" / "gui" / "smoke.py"
DESKTOP_BACKEND_SMOKE = REPO_ROOT / "tools" / "desktop" / "lifecycle_smoke.py"
UI_AUTOMATION_SMOKE = REPO_ROOT / "tools" / "gui" / "automation_smoke.py"
CI_VERIFY = REPO_ROOT / "tools" / "ci" / "verify_ci.py"
CI_GATE = REPO_ROOT / "tools" / "ci" / "run_gate.py"
FIXTURE_HARNESS = REPO_ROOT / "tools" / "testing" / "fixture_harness.py"
GOVERNANCE_VERIFY = REPO_ROOT / "tools" / "governance" / "verify_governance.py"
REPOSITORY_BOOTSTRAP_VERIFY = REPO_ROOT / "tools" / "governance" / "verify_repository_bootstrap.py"
M0_DELTA_CLOSURE_VERIFY = REPO_ROOT / "tools" / "governance" / "verify_m0_delta_closure.py"
M1_ENTRY_PREPARATION_MODULE = "tools.governance.verify_m1_entry_preparation"
M1_ENTRY_GATE_STATE_MODULE = "tools.governance.verify_m1_entry_gate_state"
M1_ENTRY_ACTIVATION_MODULE = "tools.governance.m1_entry_activation"
M1_ENTRY_ASSIGN_ROLES_MODULE = "tools.governance.m1_entry_assign_roles"
M1_DETAILED_DESIGN_VERIFY_MODULE = "tools.governance.verify_m1_detailed_design"
M1_FIXTURE_HARNESS_MODULE = "tools.testing.m1_fixture_harness"
M1_SOURCE_ADAPTER_CHECK_MODULE = "tools.testing.m1_source_adapter_check"
M2_FIXTURE_FAMILY_CHECK_MODULE = "tools.testing.m2_fixture_family_check"
M2_MEASUREMENT_ALIGNMENT_CHECK_MODULE = "tools.testing.m2_measurement_alignment_check"
M2_MISSION_SYSTEM_CHECK_MODULE = "tools.testing.m2_mission_system_check"
M2_REFERENCE_TRUTH_CHECK_MODULE = "tools.testing.m2_reference_truth_check"
M2_REFERENCE_TIME_WORLD_CHECK_MODULE = "tools.testing.m2_reference_time_world_check"
M2_REFERENCE_TIME_WORLD_COMPARE_MODULE = "tools.testing.m2_reference_time_world_compare"
M2_RADAR_SENSOR_WORLD_CHECK_MODULE = "tools.testing.m2_radar_sensor_world_check"
M2_RADAR_SENSOR_WORLD_COMPARE_MODULE = "tools.testing.m2_radar_sensor_world_compare"
M2_STAGE_WORLD_LINEAGE_CHECK_MODULE = "tools.testing.m2_stage_world_lineage_check"
M2_STAGE_WORLD_LINEAGE_COMPARE_MODULE = "tools.testing.m2_stage_world_lineage_compare"
M2_GENERAL_METRIC_ENGINE_CHECK_MODULE = "tools.testing.m2_general_metric_engine_check"
M2_GENERAL_METRIC_ENGINE_COMPARE_MODULE = "tools.testing.m2_general_metric_engine_compare"
M2_QA_FOUNDATION_INCREMENTAL_CHECK_MODULE = "tools.testing.m2_qa_foundation_incremental_check"
M2_QA_FOUNDATION_INCREMENTAL_COMPARE_MODULE = "tools.testing.m2_qa_foundation_incremental_compare"
M2_AIR_FORMAL_DELIVERY_CHECK_MODULE = "tools.testing.m2_air_formal_delivery_check"
M2_AIR_FORMAL_DELIVERY_COMPARE_MODULE = "tools.testing.m2_air_formal_delivery_compare"
M2_SNS_DETECTION_CHECK_MODULE = "tools.testing.m2_sns_detection_check"
M2_SNS_DETECTION_COMPARE_MODULE = "tools.testing.m2_sns_detection_compare"
M2_TIME_ALIGNMENT_CHECK_MODULE = "tools.testing.m2_time_alignment_check"
M1_SOURCE_REGISTRY_CHECK_MODULE = "tools.testing.m1_source_registry_check"
M1_SESSION_TIME_CHECK_MODULE = "tools.testing.m1_session_time_check"
M1_AIRCRAFT_IDENTITY_CHECK_MODULE = "tools.testing.m1_aircraft_identity_check"
M1_CANONICAL_FLIGHT_CHANNELS_CHECK_MODULE = (
    "tools.testing.m1_canonical_flight_channels_check"
)
M1_EVALUATION_CONTEXT_CHECK_MODULE = "tools.testing.m1_evaluation_context_check"
M1_LINEAGE_QUALITY_CHECK_MODULE = "tools.testing.m1_lineage_quality_check"
M1_BASIC_EPISODE_CHECK_MODULE = "tools.testing.m1_basic_episode_check"
M1_BASIC_STAGE_CHECK_MODULE = "tools.testing.m1_basic_stage_check"
M1_STAGE_QUALITY_CHECK_MODULE = "tools.testing.m1_stage_quality_check"
M1_BATCH_1_CORE_CHECK_MODULE = "tools.testing.m1_batch_1_core_check"
M1_BATCH_1_COMPARE_MODULE = "tools.testing.m1_batch_1_compare"
M1_BATCH_2_SERVICE_SMOKE_MODULE = "tools.testing.m1_batch_2_service_smoke"
M1_BATCH_2_SERVICE_COMPARE_MODULE = "tools.testing.m1_batch_2_service_compare"
M1_BATCH_2_STORAGE_PARITY_MODULE = "tools.testing.m1_batch_2_storage_parity"
M1_BATCH_2_BACKEND_CHECK_MODULE = "tools.testing.m1_batch_2_backend_check"
M1_BATCH_2_REVIEW_MODULE = "tools.testing.m1_batch_2_review"
M1_BATCH_3_DESKTOP_E2E_MODULE = "tools.testing.m1_batch_3_desktop_e2e"
M1_BATCH_3_DESKTOP_COMPARE_MODULE = "tools.testing.m1_batch_3_desktop_compare"
M1_BATCH_3_REVIEW_MODULE = "tools.testing.m1_batch_3_review"
M1_BATCH_4_PLATFORM_CHECK_MODULE = "tools.testing.m1_batch_4_platform_check"
M1_BATCH_4_COMPARE_MODULE = "tools.testing.m1_batch_4_compare"
M1_EXIT_REVIEW_MODULE = "tools.testing.m1_exit_review"
PLATFORM_SMOKE = REPO_ROOT / "tools" / "platform" / "smoke.py"
OPENAPI_SNAPSHOT = REPO_ROOT / "tools" / "api" / "openapi_snapshot.py"
MIGRATION_HARNESS = REPO_ROOT / "tools" / "storage" / "migration_harness.py"
BACKUP_RESTORE_SMOKE = REPO_ROOT / "tools" / "storage" / "backup_restore_smoke.py"
SECURITY_SMOKE = REPO_ROOT / "tools" / "security" / "smoke.py"
MANIFEST_TOOL = REPO_ROOT / "tools" / "manifest" / "build_artifacts.py"
M1_ENTRY_MANIFEST_MODULE = "tools.manifest.m1_entry_manifest"
PACKAGE_TOOL = REPO_ROOT / "tools" / "packaging" / "development_package.py"
PACKAGE_SMOKE = REPO_ROOT / "tools" / "packaging" / "smoke.py"
COLD_START = REPO_ROOT / "tools" / "ci" / "cold_start.py"

EXIT_OK = 0
EXIT_FAILURE = 2
EXIT_NOT_IMPLEMENTED = 3


@dataclass(frozen=True)
class CommandSpec:
    name: str
    milestone_task: str
    state: str
    description: str


COMMANDS: tuple[CommandSpec, ...] = (
    CommandSpec("bootstrap", "M0-DEV-001", "IMPLEMENTED", "Validate runtime/lock/baseline and sync the frozen project environment."),
    CommandSpec("verify-repository-bootstrap", "M0-DEV-000", "IMPLEMENTED", "Verify the source-controlled Formal Repository Bootstrap contract."),
    CommandSpec("verify-m0-delta-closure", "M0 Milestone Review", "IMPLEMENTED", "Verify the SDIB-1.0.1 48-task M0 delta closure record."),
    CommandSpec("verify-m1-entry-preparation", "M1 Entry Gate §19.1(6/7/9/10)", "IMPLEMENTED", "Verify non-admitting M1 Entry preparation evidence."),
    CommandSpec("verify-m1-entry-gate-state", "M1 Entry Gate §19.1", "IMPLEMENTED", "Verify the current blocked/admitted M1 Entry review state."),
    CommandSpec("m1-entry-activation", "M1 Entry Gate §19.1", "IMPLEMENTED", "Verify a PR candidate or emit merged-main M1 admission activation evidence."),
    CommandSpec("m1-entry-assign-roles", "M1 Entry Gate §19.1(8)", "IMPLEMENTED", "Render explicit human role assignments into a non-admitting M1 admission candidate."),
    CommandSpec("verify-m1-detailed-design", "M1-A/B/C Design", "IMPLEMENTED", "Verify pre-admission M1 fixture/data-spine/stage design against frozen authorities."),
    CommandSpec("m1-fixture-check", "M1-TST-001", "IMPLEMENTED", "Validate all governed M1 synthetic fixture bundles and hashes."),
    CommandSpec("m1-source-adapter-check", "M1-DATA-001", "IMPLEMENTED", "Verify the synthetic source adapter over all governed M1 bundles."),
    CommandSpec("m2-reference-truth-check", "M2-DATA-001", "IMPLEMENTED", "Verify governed M2 reference-relative truth/time/frame provenance."),
    CommandSpec("m2-mission-system-check", "M2-DATA-003", "IMPLEMENTED", "Verify governed RADAR mission-system identity and fail-closed SNS applicability."),
    CommandSpec("m2-measurement-alignment-check", "M2-DATA-004", "IMPLEMENTED", "Verify governed measurement/reference pairing, quality, gap and uncertainty provenance."),
    CommandSpec("m2-fixture-family-check", "M2-DATA-005", "IMPLEMENTED", "Verify the governed M2 nominal/boundary/gap/insufficient/invalid/applicability fixture family."),
    CommandSpec("m2-fixture-family-compare", "M2-DATA-005", "IMPLEMENTED", "Compare Windows/Linux M2 fixture-family logical evidence exactly."),
    CommandSpec("m2-time-alignment-check", "M2-DATA-002", "IMPLEMENTED", "Verify governed M2 sensor/INS time-alignment input provenance and fail-closed negatives."),
    CommandSpec("m2-reference-time-world-check", "M2-WORLD-001", "IMPLEMENTED", "Verify Core-compatible replay-stable M2 reference/time World products."),
    CommandSpec("m2-reference-time-world-compare", "M2-WORLD-001", "IMPLEMENTED", "Compare Windows/Linux M2 reference/time World logical evidence exactly."),
    CommandSpec("m2-radar-sensor-world-check", "M2-WORLD-002", "IMPLEMENTED", "Verify Core-compatible RADAR sensor MACHINE World input and subject identity."),
    CommandSpec("m2-radar-sensor-world-compare", "M2-WORLD-002", "IMPLEMENTED", "Compare Windows/Linux M2 RADAR sensor World logical evidence exactly."),
    CommandSpec("m2-stage-world-lineage-check", "M2-WORLD-003", "IMPLEMENTED", "Verify replay-stable M2 Basic Flight Stage/World lineage, quality and status."),
    CommandSpec("m2-stage-world-lineage-compare", "M2-WORLD-003", "IMPLEMENTED", "Compare Windows/Linux M2 Stage/World lineage logical evidence exactly."),
    CommandSpec("m2-general-metric-engine-check", "M2-MET-001", "IMPLEMENTED", "Verify the frozen Catalog-driven general Metric Engine substrate and evidence."),
    CommandSpec("m2-general-metric-engine-compare", "M2-MET-001", "IMPLEMENTED", "Compare Windows/Linux M2-MET-001 logical evidence exactly."),
    CommandSpec("m2-qa-foundation-incremental-check", "M2-MET-002", "IMPLEMENTED", "Verify the authority-safe QA foundation subset without claiming task completion."),
    CommandSpec("m2-qa-foundation-incremental-compare", "M2-MET-002", "IMPLEMENTED", "Compare Windows/Linux incremental M2-MET-002 QA evidence exactly."),
    CommandSpec("m2-air-formal-delivery-check", "M2-MET-003", "IMPLEMENTED", "Requalify the exact M2 AIR metric set through Catalog, Golden, Evidence, and immutable Release."),
    CommandSpec("m2-air-formal-delivery-compare", "M2-MET-003", "IMPLEMENTED", "Compare Windows/Linux M2-MET-003 AIR formal-delivery evidence exactly."),
    CommandSpec("m2-sns-detection-check", "M2-MET-004", "IMPLEMENTED", "Verify exact SNS detection semantics, Golden cases, and RADAR applicability."),
    CommandSpec("m2-sns-detection-compare", "M2-MET-004", "IMPLEMENTED", "Compare Windows/Linux M2-MET-004 SNS detection evidence exactly."),
    CommandSpec("m1-source-registry-check", "M1-DATA-002", "IMPLEMENTED", "Verify immutable source-bundle and context-artifact registration refs/hashes."),
    CommandSpec("m1-session-time-check", "M1-DATA-003", "IMPLEMENTED", "Verify explicit Source Time to Session Time transforms over all governed M1 bundles."),
    CommandSpec("m1-aircraft-identity-check", "M1-DATA-004", "IMPLEMENTED", "Verify replay-stable governed aircraft identity resolution over all M1 bundles."),
    CommandSpec("m1-canonical-flight-channels-check", "M1-DATA-005", "IMPLEMENTED", "Verify exact physical-to-Canonical aircraft flight channel projection over all M1 bundles."),
    CommandSpec("m1-evaluation-context-check", "M1-DATA-006", "IMPLEMENTED", "Verify immutable Basic/Stage/Metric Evaluation Context binding over all M1 bundles."),
    CommandSpec("m1-lineage-quality-check", "M1-DATA-007", "IMPLEMENTED", "Verify field-level source lineage and exact quality/missing propagation over all M1 bundles."),
    CommandSpec("m1-basic-episode-check", "M1-WORLD-001", "IMPLEMENTED", "Verify replay-stable Basic Flight Episode identity/revision over all M1 bundles."),
    CommandSpec("m1-basic-stage-check", "M1-WORLD-002", "IMPLEMENTED", "Verify exact BASIC_FLIGHT_V1 Stage order and half-open boundary projection over all M1 bundles."),
    CommandSpec("m1-stage-quality-check", "M1-WORLD-003", "IMPLEMENTED", "Verify governed Stage status, coverage, confidence, and detector version over all M1 bundles."),
    CommandSpec("m1-batch-1-core-check", "M1-WORLD-004..007/M1-MET-001..008/M1-TST-002..003", "IMPLEMENTED", "Verify consolidated M1 Batch 1 World, representative Metric, staging, and Golden acceptance."),
    CommandSpec("m1-batch-1-compare", "M1-WORLD-006/M1-TST-002", "IMPLEMENTED", "Compare Windows/Linux Batch 1 logical evidence exactly."),
    CommandSpec("m1-batch-2-service-smoke", "M1-PLAT-003", "IMPLEMENTED", "Run the M1 Batch 2 Application/Repository service contract and emit logical evidence."),
    CommandSpec("m1-batch-2-service-compare", "M1-PLAT-003", "IMPLEMENTED", "Compare Windows/Linux Batch 2 service logical evidence exactly."),
    CommandSpec("m1-batch-2-storage-parity", "M1-STO-001/M1-STO-003", "IMPLEMENTED", "Publish the same Batch 2 Release to real SQLite/PostgreSQL Core schemas and compare logical membership exactly."),
    CommandSpec("m1-batch-2-backend-check", "M1 Batch 2 backend acceptance", "IMPLEMENTED", "Emit executable acceptance for OBS/STO-002/API/TST backend rows."),
    CommandSpec("m1-batch-2-review", "M1 Batch 2 Issue #87", "IMPLEMENTED", "Aggregate exact-revision Windows/Linux/backend/service/storage evidence into the 18-row Batch 2 acceptance matrix."),
    CommandSpec("m1-batch-3-desktop-e2e", "M1-GUI-001..007/M1-TST-008/M1-PLAT-001..002", "IMPLEMENTED", "Run the real M1 Desktop journey and emit exact-revision platform evidence."),
    CommandSpec("m1-batch-3-desktop-compare", "M1-PLAT-001/M1-PLAT-002", "IMPLEMENTED", "Compare Windows/Linux M1 Desktop logical products exactly."),
    CommandSpec("m1-batch-3-review", "M1 Batch 3 Issue #89", "IMPLEMENTED", "Aggregate exact-revision Windows/Linux Desktop evidence into the ten-row Batch 3 acceptance matrix."),
    CommandSpec("m1-batch-4-platform-check", "M1-TST-010", "IMPLEMENTED", "Qualify integrated M1 on one platform from a clean locked workspace and emit a noise-free logical product."),
    CommandSpec("m1-batch-4-compare", "M1-TST-009/M1-PLAT-004", "IMPLEMENTED", "Compare Windows/Linux integrated M1 logical products while excluding platform noise."),
    CommandSpec("m1-exit-review", "M1 Batch 4 Issue #88", "IMPLEMENTED", "Aggregate all 56 M1 Task IDs and emit GO only for exact protected-main push evidence."),
    CommandSpec("generate", "M0-CORE-003", "IMPLEMENTED", "Generate deterministic projections from Canonical authorities."),
    CommandSpec("verify-generated", "M0-CORE-004", "IMPLEMENTED", "Verify exact generated tree and provenance without rewriting it."),
    CommandSpec("regenerate-diff", "M0-CORE-004", "IMPLEMENTED", "Regenerate and require zero Git diff for governed generated source."),
    CommandSpec("verify-architecture", "M0-CORE-005", "IMPLEMENTED", "Verify SDIB package/layer dependency direction using the static architecture gate."),
    CommandSpec("verify-repository-policy", "ADR-M0-004", "IMPLEMENTED", "Verify the frozen Repository DB access technology/UoW decision."),
    CommandSpec("verify-desktop-lifecycle-policy", "ADR-M0-005", "IMPLEMENTED", "Verify the frozen Desktop backend lifecycle/IPC/token decision."),
    CommandSpec("verify-baseline", "M0-CORE-001", "IMPLEMENTED", "Verify BASELINE_LOCK and controlled Canonical artifact hashes."),
    CommandSpec("verify-canonical", "M0-CORE-002", "IMPLEMENTED", "Verify Canonical loader compatibility and fail-closed contracts."),
    CommandSpec("db-bootstrap", "M0-STO-001", "IMPLEMENTED", "Bootstrap an empty SQLite Desktop DB from frozen schema 1.6.0 authority."),
    CommandSpec("db-verify", "M0-STO-001", "IMPLEMENTED", "Verify SQLite schema/version/provenance against frozen schema 1.6.0 authority."),
    CommandSpec("db-sqlite-repository-acceptance", "M0-STO-002", "IMPLEMENTED", "Run disposable SQLite Desktop Repository/UoW/WAL/single-writer acceptance."),
    CommandSpec("db-postgres-bootstrap", "M0-STO-001", "IMPLEMENTED", "Bootstrap PostgreSQL through the repository-controlled external psql harness."),
    CommandSpec("db-postgres-verify", "M0-STO-001", "IMPLEMENTED", "Verify PostgreSQL schema/version/provenance through the external psql harness."),
    CommandSpec("db-postgres-acceptance", "M0-STO-001", "IMPLEMENTED", "Run destructive M0-STO-001 PostgreSQL acceptance in a dedicated disposable database."),
    CommandSpec("db-postgres-repository-acceptance", "M0-STO-003", "IMPLEMENTED", "Run PostgreSQL Service Repository/UoW acceptance against an existing ready database."),
    CommandSpec("api-smoke", "M0-API-002", "IMPLEMENTED", "Smoke health/readiness/version through the FastAPI transport adapter."),
    CommandSpec("gui-smoke", "M0-GUI-001", "IMPLEMENTED", "Smoke PySide6 application startup and controlled exit."),
    CommandSpec("desktop-backend-smoke", "M0-GUI-002", "IMPLEMENTED", "Smoke owned local backend token/readiness/shutdown lifecycle."),
    CommandSpec("ui-automation-smoke", "M0-GUI-004", "IMPLEMENTED", "Automate Desktop launch/READY diagnostics/close/backend cleanup."),
    CommandSpec("verify-ci", "M0-PLAT-004/M0-PLAT-005", "IMPLEMENTED", "Verify the governed Windows/Linux CI orchestration contract."),
    CommandSpec("ci-check", "M0-PLAT-004/M0-PLAT-005", "IMPLEMENTED", "Run the current required M0 gate set and emit platform CI evidence."),
    CommandSpec("verify-governance", "M0-GOV-001..004", "IMPLEMENTED", "Verify ADR, Issue/PR, Baseline Change and DoD governance contracts."),
    CommandSpec("format", "ADR-M0-003", "IMPLEMENTED", "Run the frozen Ruff formatter."),
    CommandSpec("lint", "ADR-M0-003", "IMPLEMENTED", "Run the frozen Ruff linter."),
    CommandSpec("typecheck", "ADR-M0-003", "IMPLEMENTED", "Run the frozen mypy type checker."),
    CommandSpec("test", "M0-TST-001", "IMPLEMENTED", "Run the current repository test suite."),
    CommandSpec("test-unit", "M0-TST-001", "IMPLEMENTED", "Run unit tests."),
    CommandSpec("test-contract", "M0-TST-001", "IMPLEMENTED", "Run contract tests."),
    CommandSpec("test-golden", "M0-TST-001", "IMPLEMENTED", "Run Golden tests."),
    CommandSpec("test-replay", "M0-TST-001", "IMPLEMENTED", "Run replay tests."),
    CommandSpec("test-migration", "M0-TST-001", "IMPLEMENTED", "Run migration tests."),
    CommandSpec("test-e2e", "M0-TST-001", "IMPLEMENTED", "Run end-to-end tests."),
    CommandSpec("test-platform", "M0-PLAT-001..003", "IMPLEMENTED", "Run cross-platform adapter contract tests."),
    CommandSpec("platform-smoke", "M0-PLAT-001..003", "IMPLEMENTED", "Run real path/spawn/lock/atomic adapter smoke."),
    CommandSpec("openapi-snapshot", "M0-API-003", "IMPLEMENTED", "Generate/check Canonical DTO OpenAPI snapshot."),
    CommandSpec("migration-smoke", "M0-STO-005", "IMPLEMENTED", "Run bootstrap/rollback/forward-recovery migration harness."),
    CommandSpec("backup-restore-smoke", "M0-STO-007", "IMPLEMENTED", "Run development DB/object backup-restore smoke."),
    CommandSpec("security-smoke", "M0-SEC-001..004", "IMPLEMENTED", "Run security/audit/data-guard/secret-separation smoke."),
    CommandSpec("fixture-check", "M0-TST-001/M0-TST-005/M0-TST-006", "IMPLEMENTED", "Run the frozen M0 fixture/Golden/replay framework smoke and emit evidence."),
    CommandSpec("platform-logical-product", "M0-TST-006", "IMPLEMENTED", "Emit the current platform logical product for cross-platform comparison."),
    CommandSpec("compare-platform-logical", "M0-TST-006", "IMPLEMENTED", "Compare Windows/Linux logical products using the shared fixture tolerance."),
    CommandSpec("run", "M0-API-002/M0-GUI-001", "RESERVED", "Dispatch an API or GUI runtime profile."),
    CommandSpec("run-api", "M0-API-002", "RESERVED", "Start the API profile once implemented."),
    CommandSpec("run-gui", "M0-GUI-002", "IMPLEMENTED", "Start the composed Desktop shell with its owned local backend."),
    CommandSpec("package", "M0-DEV-005", "IMPLEMENTED", "Build a deterministic M0 development artifact for one governed profile."),
    CommandSpec("package-smoke", "M0-DEV-005", "IMPLEMENTED", "Clean-extract/install/start/stop Desktop and Service development bundles."),
    CommandSpec("manifest", "M0-DEV-003/M0-DEV-004", "IMPLEMENTED", "Generate build manifest, SBOM, license and native dependency evidence."),
    CommandSpec("m1-entry-manifest", "M1 Entry Gate §19.1(6)", "IMPLEMENTED", "Generate an exact M1 Entry build manifest without admitting M1."),
    CommandSpec("cold-start", "M0-DEV-006", "IMPLEMENTED", "Rebuild and execute current M0 gates from a clean local clone."),
    CommandSpec("doctor", "M0-DEV-001", "IMPLEMENTED", "Report runtime, resolver, lock and quality-tool availability."),
)


def _load_toolchain() -> dict[str, object]:
    data = json.loads(TOOLCHAIN_PATH.read_text(encoding="utf-8"))
    if not isinstance(data, dict) or data.get("schema") != "TPAA_M0_TOOLCHAIN_V1":
        raise RuntimeError("invalid TPAA toolchain contract")
    return data


def _run(args: Sequence[str], *, cwd: Path = REPO_ROOT) -> int:
    completed = subprocess.run(list(args), cwd=cwd, check=False)
    return completed.returncode


def _capture(args: Sequence[str], *, cwd: Path = REPO_ROOT) -> tuple[int, str]:
    try:
        completed = subprocess.run(
            list(args),
            cwd=cwd,
            check=False,
            capture_output=True,
            text=True,
            timeout=20,
        )
    except (OSError, subprocess.SubprocessError) as exc:
        return EXIT_FAILURE, str(exc)
    text = (completed.stdout or completed.stderr).strip()
    return completed.returncode, text


def _uv_executable() -> str | None:
    return shutil.which("uv")


def _version_text(executable: str, module: bool = False) -> str | None:
    args = [sys.executable, "-m", executable, "--version"] if module else [executable, "--version"]
    code, output = _capture(args)
    return output if code == 0 else None


def _quality_tool_command(tool: str, version: str, args: Sequence[str]) -> list[str]:
    executable = shutil.which(tool)
    if executable:
        code, output = _capture([executable, "--version"])
        if code == 0 and version in output:
            return [executable, *args]
    if tool == "pytest":
        code, output = _capture([sys.executable, "-m", "pytest", "--version"])
        if code == 0 and version in output:
            return [sys.executable, "-m", "pytest", *args]
    uv = _uv_executable()
    if uv is None:
        raise RuntimeError(f"{tool} {version} unavailable and uv is not on PATH")
    return [uv, "run", "--locked", "--with", f"{tool}=={version}", tool, *args]


def _quality_version(tool: str, version: str) -> tuple[str, str]:
    """Report locally available exact tools without causing network access."""
    executable = shutil.which(tool)
    if executable:
        code, output = _capture([executable, "--version"])
        if code == 0 and version in output:
            return "READY", output
        if code == 0:
            return "VERSION_MISMATCH", output
    if tool == "pytest":
        code, output = _capture([sys.executable, "-m", "pytest", "--version"])
        if code == 0 and version in output:
            return "READY", output
        if code == 0:
            return "VERSION_MISMATCH", output
    return "UNAVAILABLE", f"{tool} {version} is not installed in the current execution environment"


def _runtime_check() -> tuple[bool, str]:
    actual = f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}"
    ok = sys.implementation.name == "cpython" and sys.version_info[:2] == (3, 13)
    return ok, f"CPython {actual}" if sys.implementation.name == "cpython" else f"{sys.implementation.name} {actual}"


def _lock_check() -> tuple[bool, str]:
    uv = _uv_executable()
    if uv is None:
        return False, "uv unavailable"
    code, output = _capture([uv, "lock", "--check", "--offline"])
    return code == 0, output or ("uv.lock matches pyproject.toml" if code == 0 else "uv lock check failed")


def _baseline_check() -> int:
    return _run([sys.executable, str(BASELINE_VERIFY)])


def cmd_list(as_json: bool) -> int:
    payload = [spec.__dict__ for spec in COMMANDS]
    if as_json:
        print(json.dumps(payload, indent=2, sort_keys=True))
    else:
        width = max(len(item.name) for item in COMMANDS)
        for item in COMMANDS:
            print(f"{item.name:<{width}}  {item.state:<11}  {item.milestone_task:<22}  {item.description}")
    return EXIT_OK


def cmd_doctor(strict: bool) -> int:
    toolchain = _load_toolchain()
    runtime_ok, runtime_text = _runtime_check()
    lock_ok, lock_text = _lock_check()
    uv = _uv_executable()
    uv_text = _version_text(uv) if uv else None
    quality = toolchain["quality"]
    assert isinstance(quality, dict)
    report: dict[str, object] = {
        "runtime": {"status": "READY" if runtime_ok else "FAIL", "actual": runtime_text},
        "resolver": {"status": "READY" if uv else "FAIL", "actual": uv_text or "uv unavailable"},
        "dependency_lock": {"status": "READY" if lock_ok else "FAIL", "detail": lock_text},
        "quality": {},
    }
    quality_report = report["quality"]
    assert isinstance(quality_report, dict)
    all_quality_ready = True
    for role, raw in quality.items():
        assert isinstance(raw, dict)
        tool = str(raw["tool"])
        version = str(raw["version"])
        status, detail = _quality_version(tool, version)
        quality_report[role] = {"status": status, "tool": tool, "version": version, "detail": detail}
        all_quality_ready = all_quality_ready and status == "READY"
    print(json.dumps(report, indent=2, sort_keys=True))
    core_ready = runtime_ok and bool(uv) and lock_ok
    return EXIT_OK if core_ready and (all_quality_ready or not strict) else EXIT_FAILURE


def cmd_bootstrap(check_only: bool, with_quality_tools: bool) -> int:
    runtime_ok, runtime_text = _runtime_check()
    if not runtime_ok:
        print(f"BOOTSTRAP_FAIL runtime expected=CPython-3.13.x actual={runtime_text}", file=sys.stderr)
        return EXIT_FAILURE
    uv = _uv_executable()
    if uv is None:
        print("BOOTSTRAP_FAIL uv not found", file=sys.stderr)
        return EXIT_FAILURE
    lock_ok, lock_text = _lock_check()
    if not lock_ok:
        print(f"BOOTSTRAP_FAIL dependency_lock {lock_text}", file=sys.stderr)
        return EXIT_FAILURE
    if _baseline_check() != 0:
        print("BOOTSTRAP_FAIL baseline verify", file=sys.stderr)
        return EXIT_FAILURE
    if not check_only and _run([uv, "sync", "--frozen", "--offline"]) != 0:
        print("BOOTSTRAP_FAIL uv sync --frozen --offline", file=sys.stderr)
        return EXIT_FAILURE
    if with_quality_tools:
        return cmd_doctor(strict=True)
    print("BOOTSTRAP_PASS runtime+dependency-lock+baseline")
    return EXIT_OK


def cmd_quality(role: str, extra: Sequence[str]) -> int:
    toolchain = _load_toolchain()
    quality = toolchain["quality"]
    assert isinstance(quality, dict)
    raw = quality[role]
    assert isinstance(raw, dict)
    tool = str(raw["tool"])
    version = str(raw["version"])
    if role == "formatter":
        args = ["format", *extra, "tools", "tests", "src"]
    elif role == "linter":
        args = ["check", *extra, "tools", "tests", "src"]
    elif role == "type_checker":
        args = [*extra]
    else:
        raise RuntimeError(f"unsupported quality role {role}")
    try:
        command = _quality_tool_command(tool, version, args)
    except RuntimeError as exc:
        print(f"QUALITY_TOOL_FAIL {exc}", file=sys.stderr)
        return EXIT_FAILURE
    return _run(command)


def cmd_test(path: str | None) -> int:
    toolchain = _load_toolchain()
    quality = toolchain["quality"]
    assert isinstance(quality, dict)
    raw = quality["test_runner"]
    assert isinstance(raw, dict)
    tool = str(raw["tool"])
    version = str(raw["version"])
    args = [path] if path else ["tests"]
    try:
        command = _quality_tool_command(tool, version, args)
    except RuntimeError as exc:
        print(f"TEST_TOOL_FAIL {exc}", file=sys.stderr)
        return EXIT_FAILURE
    return _run(command)


def _reserved(task: str, command: str) -> int:
    print(
        f"NOT_IMPLEMENTED command={command} controlling_task={task}; "
        "the developer command is reserved but fails closed until that SDIB task is implemented.",
        file=sys.stderr,
    )
    return EXIT_NOT_IMPLEMENTED


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="TPAA unified developer command dispatcher")
    sub = parser.add_subparsers(dest="command", required=True)

    list_parser = sub.add_parser("list", help="List developer commands and implementation state")
    list_parser.add_argument("--json", action="store_true")

    bootstrap = sub.add_parser("bootstrap", help="Validate/sync the frozen development substrate")
    bootstrap.add_argument("--check-only", action="store_true", help="Do not modify .venv")
    bootstrap.add_argument(
        "--with-quality-tools",
        action="store_true",
        help="Also require exact Ruff/mypy/pytest versions (may need network/cache)",
    )

    sub.add_parser("verify-baseline", help="Verify frozen Canonical baseline")
    sub.add_parser("verify-canonical", help="Verify M0-CORE-002 Canonical loader contract")
    sub.add_parser("doctor", help="Report toolchain state").add_argument("--strict", action="store_true")
    generate = sub.add_parser("generate", help="Generate deterministic Canonical projections")
    generate.add_argument("--check", action="store_true", help="Fail if checked-in generated tree/provenance differs")
    sub.add_parser("verify-generated", help="Verify governed generated tree without rewriting")
    sub.add_parser("regenerate-diff", help="Regenerate generated source and require zero Git diff")
    sub.add_parser("verify-architecture", help="Verify SDIB package/layer architecture dependencies")
    sub.add_parser("verify-repository-policy", help="Verify frozen ADR-M0-004 Repository DB access policy")
    sub.add_parser("verify-desktop-lifecycle-policy", help="Verify frozen ADR-M0-005 Desktop backend lifecycle/IPC policy")
    sub.add_parser("api-smoke", help="Run M0-API-002 health/readiness/version HTTP smoke")
    db_bootstrap = sub.add_parser("db-bootstrap", help="Bootstrap empty SQLite Desktop DB to schema 1.6.0")
    db_bootstrap.add_argument("database", type=Path)
    db_verify = sub.add_parser("db-verify", help="Verify SQLite Desktop DB schema/version/provenance")
    db_verify.add_argument("database", type=Path)
    sub.add_parser("db-sqlite-repository-acceptance", help="Run M0-STO-002 SQLite Repository acceptance on a disposable DB")

    def add_postgres_client_args(command: argparse.ArgumentParser) -> None:
        command.add_argument("--user", default="tpaa")
        command.add_argument("--host")
        command.add_argument("--port", type=int)
        command.add_argument("--psql", default="psql")
        command.add_argument("--docker-container")

    pg_bootstrap = sub.add_parser("db-postgres-bootstrap", help="Bootstrap PostgreSQL schema 1.6.0 through external psql")
    add_postgres_client_args(pg_bootstrap)
    pg_bootstrap.add_argument("database")
    pg_verify = sub.add_parser("db-postgres-verify", help="Verify PostgreSQL schema/version/provenance through external psql")
    add_postgres_client_args(pg_verify)
    pg_verify.add_argument("database")
    pg_acceptance = sub.add_parser("db-postgres-acceptance", help="Run destructive PostgreSQL M0-STO-001 acceptance in a disposable database")
    add_postgres_client_args(pg_acceptance)
    pg_acceptance.add_argument("--admin-database", default="postgres")
    pg_acceptance.add_argument("--database", default="tpaa_m0_sto_001_acceptance")
    pg_repo_acceptance = sub.add_parser("db-postgres-repository-acceptance", help="Run disposable M0-STO-003 PostgreSQL Repository acceptance")
    add_postgres_client_args(pg_repo_acceptance)
    pg_repo_acceptance.add_argument("--admin-database", default="postgres")
    pg_repo_acceptance.add_argument("--database", default="tpaa_m0_sto_003_acceptance")
    pg_repo_acceptance.add_argument("--conninfo-template", required=True)

    fmt = sub.add_parser("format", help="Run Ruff formatter")
    fmt.add_argument("--check", action="store_true")
    sub.add_parser("lint", help="Run Ruff linter")
    sub.add_parser("typecheck", help="Run mypy")

    for name in (
        "test",
        "test-unit",
        "test-contract",
        "test-golden",
        "test-replay",
        "test-migration",
        "test-e2e",
        "test-platform",
    ):
        sub.add_parser(name, help=f"Run {name} suite")
    sub.add_parser("platform-smoke", help="Run M0 path/spawn/lock/atomic platform smoke")
    openapi = sub.add_parser("openapi-snapshot", help="Generate/check M0 Canonical DTO OpenAPI snapshot")
    openapi.add_argument("--check", action="store_true")
    sub.add_parser("migration-smoke", help="Run M0-STO-005 migration/recovery harness")
    sub.add_parser("backup-restore-smoke", help="Run M0-STO-007 development backup/restore smoke")
    sub.add_parser("security-smoke", help="Run M0 security/audit/data-governance smoke")

    fixture_check = sub.add_parser("fixture-check", help="Run M0 fixture/Golden/replay framework smoke")
    fixture_check.add_argument("--bundle", type=Path)
    fixture_check.add_argument("--evidence", type=Path)
    platform_product = sub.add_parser(
        "platform-logical-product",
        help="Emit platform logical product for Windows/Linux equivalence",
    )
    platform_product.add_argument("--bundle", type=Path)
    platform_product.add_argument("--output", type=Path, required=True)
    platform_compare = sub.add_parser(
        "compare-platform-logical",
        help="Compare Windows/Linux logical products",
    )
    platform_compare.add_argument("--windows", type=Path, required=True)
    platform_compare.add_argument("--linux", type=Path, required=True)
    platform_compare.add_argument("--evidence", type=Path, required=True)

    run = sub.add_parser("run", help="Dispatch runtime target")
    run.add_argument("target", choices=("api", "gui"))
    sub.add_parser("run-api", help="Reserved for M0-API-002")
    sub.add_parser("run-gui", help="Start the M0-GUI-001 Desktop shell")
    gui_smoke = sub.add_parser("gui-smoke", help="Run the M0-GUI-001 PySide6 startup/exit smoke")
    gui_smoke.add_argument("--headless", action="store_true")
    sub.add_parser("desktop-backend-smoke", help="Run the M0-GUI-002 local backend lifecycle smoke")
    ui_automation = sub.add_parser("ui-automation-smoke", help="Run the M0-GUI-004 Desktop UI automation smoke")
    ui_automation.add_argument("--show", action="store_true")
    ui_automation.add_argument("--timeout", type=float, default=30.0)
    sub.add_parser("verify-ci", help="Verify the M0 Windows/Linux CI orchestration contract")
    sub.add_parser("verify-governance", help="Verify M0 governance repository contracts")
    sub.add_parser("verify-repository-bootstrap", help="Verify M0-DEV-000 repository bootstrap substrate")
    sub.add_parser("verify-m0-delta-closure", help="Verify SDIB-1.0.1 48-task M0 delta closure record")
    sub.add_parser("verify-m1-entry-preparation", help="Verify M1 Entry preparation evidence without admitting M1")
    sub.add_parser("verify-m1-entry-gate-state", help="Verify the current M1 Entry review decision/state")
    sub.add_parser("verify-m1-detailed-design", help="Verify M1-A/B/C detailed design against frozen authorities")
    m1_fixture = sub.add_parser("m1-fixture-check", help="Validate governed M1 synthetic fixture bundles")
    m1_fixture.add_argument("--bundle")
    m1_fixture.add_argument("--evidence", type=Path)
    m1_source = sub.add_parser("m1-source-adapter-check", help="Verify M1-DATA-001 synthetic source adapter")
    m1_source.add_argument("--evidence", type=Path)
    m2_reference = sub.add_parser(
        "m2-reference-truth-check",
        help="Verify M2-DATA-001 reference-relative truth projection",
    )
    m2_reference.add_argument("--evidence", type=Path)
    m2_time = sub.add_parser(
        "m2-time-alignment-check",
        help="Verify M2-DATA-002 sensor/INS time-alignment input projection",
    )
    m2_time.add_argument("--evidence", type=Path)
    m2_mission = sub.add_parser(
        "m2-mission-system-check",
        help="Verify M2-DATA-003 RADAR mission-system identity/applicability",
    )
    m2_mission.add_argument("--evidence", type=Path)
    m2_measurement = sub.add_parser(
        "m2-measurement-alignment-check",
        help="Verify M2-DATA-004 measurement/reference quality projection",
    )
    m2_measurement.add_argument("--evidence", type=Path)
    m2_family = sub.add_parser(
        "m2-fixture-family-check",
        help="Verify M2-DATA-005 frozen fixture family",
    )
    m2_family.add_argument("--evidence", type=Path)
    m2_family_compare = sub.add_parser(
        "m2-fixture-family-compare",
        help="Compare Windows/Linux M2-DATA-005 fixture evidence",
    )
    m2_family_compare.add_argument("--windows", type=Path, required=True)
    m2_family_compare.add_argument("--linux", type=Path, required=True)
    m2_family_compare.add_argument("--expected-revision", required=True)
    m2_family_compare.add_argument("--evidence", type=Path, required=True)
    m2_reference_time_world = sub.add_parser(
        "m2-reference-time-world-check",
        help="Verify M2-WORLD-001 reference/time World products",
    )
    m2_reference_time_world.add_argument("--evidence", type=Path)
    m2_reference_time_world_compare = sub.add_parser(
        "m2-reference-time-world-compare",
        help="Compare Windows/Linux M2-WORLD-001 logical evidence",
    )
    m2_reference_time_world_compare.add_argument("--windows", type=Path, required=True)
    m2_reference_time_world_compare.add_argument("--linux", type=Path, required=True)
    m2_reference_time_world_compare.add_argument("--expected-revision", required=True)
    m2_reference_time_world_compare.add_argument("--evidence", type=Path, required=True)
    m2_radar_sensor_world = sub.add_parser(
        "m2-radar-sensor-world-check",
        help="Verify M2-WORLD-002 RADAR sensor World product",
    )
    m2_radar_sensor_world.add_argument("--evidence", type=Path)
    m2_radar_sensor_world_compare = sub.add_parser(
        "m2-radar-sensor-world-compare",
        help="Compare Windows/Linux M2-WORLD-002 logical evidence",
    )
    m2_radar_sensor_world_compare.add_argument("--windows", type=Path, required=True)
    m2_radar_sensor_world_compare.add_argument("--linux", type=Path, required=True)
    m2_radar_sensor_world_compare.add_argument("--expected-revision", required=True)
    m2_radar_sensor_world_compare.add_argument("--evidence", type=Path, required=True)
    m2_stage_world_lineage = sub.add_parser(
        "m2-stage-world-lineage-check",
        help="Verify M2-WORLD-003 Stage/World lineage and status",
    )
    m2_stage_world_lineage.add_argument("--evidence", type=Path)
    m2_stage_world_lineage_compare = sub.add_parser(
        "m2-stage-world-lineage-compare",
        help="Compare Windows/Linux M2-WORLD-003 logical evidence",
    )
    m2_stage_world_lineage_compare.add_argument("--windows", type=Path, required=True)
    m2_stage_world_lineage_compare.add_argument("--linux", type=Path, required=True)
    m2_stage_world_lineage_compare.add_argument("--expected-revision", required=True)
    m2_stage_world_lineage_compare.add_argument("--evidence", type=Path, required=True)
    m2_general_metric_engine = sub.add_parser(
        "m2-general-metric-engine-check",
        help="Verify M2-MET-001 Catalog-driven general Metric Engine",
    )
    m2_general_metric_engine.add_argument("--evidence", type=Path)
    m2_general_metric_engine_compare = sub.add_parser(
        "m2-general-metric-engine-compare",
        help="Compare Windows/Linux M2-MET-001 logical evidence",
    )
    m2_general_metric_engine_compare.add_argument("--windows", type=Path, required=True)
    m2_general_metric_engine_compare.add_argument("--linux", type=Path, required=True)
    m2_general_metric_engine_compare.add_argument("--expected-revision", required=True)
    m2_general_metric_engine_compare.add_argument("--evidence", type=Path, required=True)
    m2_qa_incremental = sub.add_parser(
        "m2-qa-foundation-incremental-check",
        help="Verify the authority-safe M2-MET-002 subset without task completion",
    )
    m2_qa_incremental.add_argument("--evidence", type=Path)
    m2_qa_incremental_compare = sub.add_parser(
        "m2-qa-foundation-incremental-compare",
        help="Compare Windows/Linux incremental M2-MET-002 QA evidence",
    )
    m2_qa_incremental_compare.add_argument("--windows", type=Path, required=True)
    m2_qa_incremental_compare.add_argument("--linux", type=Path, required=True)
    m2_qa_incremental_compare.add_argument("--expected-revision", required=True)
    m2_qa_incremental_compare.add_argument("--evidence", type=Path, required=True)
    m2_air_delivery = sub.add_parser(
        "m2-air-formal-delivery-check",
        help="Verify exact M2-MET-003 AIR formal delivery",
    )
    m2_air_delivery.add_argument("--evidence", type=Path)
    m2_air_delivery_compare = sub.add_parser(
        "m2-air-formal-delivery-compare",
        help="Compare Windows/Linux M2-MET-003 AIR formal-delivery evidence",
    )
    m2_air_delivery_compare.add_argument("--windows", type=Path, required=True)
    m2_air_delivery_compare.add_argument("--linux", type=Path, required=True)
    m2_air_delivery_compare.add_argument("--expected-revision", required=True)
    m2_air_delivery_compare.add_argument("--evidence", type=Path, required=True)
    m2_sns_detection = sub.add_parser(
        "m2-sns-detection-check",
        help="Verify exact M2-MET-004 SNS detection delivery",
    )
    m2_sns_detection.add_argument("--evidence", type=Path)
    m2_sns_detection_compare = sub.add_parser(
        "m2-sns-detection-compare",
        help="Compare Windows/Linux M2-MET-004 SNS detection evidence",
    )
    m2_sns_detection_compare.add_argument("--windows", type=Path, required=True)
    m2_sns_detection_compare.add_argument("--linux", type=Path, required=True)
    m2_sns_detection_compare.add_argument("--expected-revision", required=True)
    m2_sns_detection_compare.add_argument("--evidence", type=Path, required=True)
    m1_registry = sub.add_parser(
        "m1-source-registry-check",
        help="Verify M1-DATA-002 immutable source registry refs/hashes",
    )
    m1_registry.add_argument("--evidence", type=Path)
    m1_time = sub.add_parser(
        "m1-session-time-check",
        help="Verify M1-DATA-003 explicit Session Time transforms",
    )
    m1_time.add_argument("--evidence", type=Path)
    m1_aircraft = sub.add_parser(
        "m1-aircraft-identity-check",
        help="Verify M1-DATA-004 replay-stable governed aircraft identity",
    )
    m1_aircraft.add_argument("--evidence", type=Path)
    m1_canonical = sub.add_parser(
        "m1-canonical-flight-channels-check",
        help="Verify M1-DATA-005 Canonical aircraft flight channel projection",
    )
    m1_canonical.add_argument("--evidence", type=Path)
    m1_context = sub.add_parser(
        "m1-evaluation-context-check",
        help="Verify M1-DATA-006 immutable Evaluation Context resolution",
    )
    m1_context.add_argument("--evidence", type=Path)
    m1_lineage = sub.add_parser(
        "m1-lineage-quality-check",
        help="Verify M1-DATA-007 Canonical field lineage/quality propagation",
    )
    m1_lineage.add_argument("--evidence", type=Path)
    m1_episode = sub.add_parser(
        "m1-basic-episode-check",
        help="Verify M1-WORLD-001 replay-stable Basic Flight Episode detection",
    )
    m1_episode.add_argument("--evidence", type=Path)
    m1_stage = sub.add_parser(
        "m1-basic-stage-check",
        help="Verify M1-WORLD-002 governed BASIC_FLIGHT_V1 Stage projection",
    )
    m1_stage.add_argument("--evidence", type=Path)
    m1_stage_quality = sub.add_parser(
        "m1-stage-quality-check",
        help="Verify M1-WORLD-003 governed Stage quality/status projection",
    )
    m1_stage_quality.add_argument("--evidence", type=Path)
    m1_batch_1 = sub.add_parser(
        "m1-batch-1-core-check",
        help="Verify consolidated M1 Batch 1 core-product acceptance",
    )
    m1_batch_1.add_argument("--evidence", type=Path)
    m1_batch_1_compare = sub.add_parser(
        "m1-batch-1-compare",
        help="Compare Windows/Linux M1 Batch 1 logical evidence",
    )
    m1_batch_1_compare.add_argument("--windows", type=Path, required=True)
    m1_batch_1_compare.add_argument("--linux", type=Path, required=True)
    m1_batch_1_compare.add_argument("--expected-revision", required=True)
    m1_batch_1_compare.add_argument("--evidence", type=Path, required=True)
    m1_batch_2_service = sub.add_parser(
        "m1-batch-2-service-smoke",
        help="Run M1 Batch 2 cross-platform service smoke",
    )
    m1_batch_2_service.add_argument(
        "--expected-platform",
        choices=("windows", "linux"),
        required=True,
    )
    m1_batch_2_service.add_argument("--source-revision", required=True)
    m1_batch_2_service.add_argument("--evidence", type=Path, required=True)
    m1_batch_2_service_compare = sub.add_parser(
        "m1-batch-2-service-compare",
        help="Compare Windows/Linux M1 Batch 2 service evidence",
    )
    m1_batch_2_service_compare.add_argument("--windows", type=Path, required=True)
    m1_batch_2_service_compare.add_argument("--linux", type=Path, required=True)
    m1_batch_2_service_compare.add_argument("--evidence", type=Path, required=True)
    m1_batch_2_storage = sub.add_parser(
        "m1-batch-2-storage-parity",
        help="Verify real SQLite/PostgreSQL M1 Batch 2 publication parity",
    )
    m1_batch_2_storage.add_argument("--user", default="tpaa")
    m1_batch_2_storage.add_argument("--host")
    m1_batch_2_storage.add_argument("--port", type=int)
    m1_batch_2_storage.add_argument("--psql", default="psql")
    m1_batch_2_storage.add_argument("--admin-database", default="postgres")
    m1_batch_2_storage.add_argument(
        "--database",
        default="tpaa_m1_batch_2_parity",
    )
    m1_batch_2_storage.add_argument("--conninfo-template", required=True)
    m1_batch_2_storage.add_argument("--source-revision", required=True)
    m1_batch_2_storage.add_argument("--evidence", type=Path, required=True)
    m1_batch_2_backend = sub.add_parser(
        "m1-batch-2-backend-check",
        help="Verify consolidated M1 Batch 2 backend acceptance",
    )
    m1_batch_2_backend.add_argument(
        "--platform",
        choices=("windows", "linux"),
        required=True,
    )
    m1_batch_2_backend.add_argument("--source-revision", required=True)
    m1_batch_2_backend.add_argument("--evidence", type=Path, required=True)
    m1_batch_2_review = sub.add_parser(
        "m1-batch-2-review",
        help="Aggregate exact-revision M1 Batch 2 acceptance evidence",
    )
    m1_batch_2_review.add_argument("--expected-revision", required=True)
    m1_batch_2_review.add_argument("--windows-backend", type=Path, required=True)
    m1_batch_2_review.add_argument("--linux-backend", type=Path, required=True)
    m1_batch_2_review.add_argument("--windows-service", type=Path, required=True)
    m1_batch_2_review.add_argument("--linux-service", type=Path, required=True)
    m1_batch_2_review.add_argument("--service-logical", type=Path, required=True)
    m1_batch_2_review.add_argument("--storage-parity", type=Path, required=True)
    m1_batch_2_review.add_argument("--output", type=Path, required=True)
    m1_batch_3_e2e = sub.add_parser(
        "m1-batch-3-desktop-e2e",
        help="Run real M1 Batch 3 Desktop E2E evidence",
    )
    m1_batch_3_e2e.add_argument("--expected-platform", choices=("windows", "linux"), required=True)
    m1_batch_3_e2e.add_argument("--source-revision", required=True)
    m1_batch_3_e2e.add_argument("--evidence", type=Path, required=True)
    m1_batch_3_e2e.add_argument("--timeout", type=float, default=45.0)
    m1_batch_3_compare = sub.add_parser(
        "m1-batch-3-desktop-compare",
        help="Compare Windows/Linux M1 Batch 3 Desktop evidence",
    )
    m1_batch_3_compare.add_argument("--windows", type=Path, required=True)
    m1_batch_3_compare.add_argument("--linux", type=Path, required=True)
    m1_batch_3_compare.add_argument("--expected-revision", required=True)
    m1_batch_3_compare.add_argument("--evidence", type=Path, required=True)
    m1_batch_3_review = sub.add_parser(
        "m1-batch-3-review",
        help="Aggregate exact-revision M1 Batch 3 acceptance evidence",
    )
    m1_batch_3_review.add_argument("--windows", type=Path, required=True)
    m1_batch_3_review.add_argument("--linux", type=Path, required=True)
    m1_batch_3_review.add_argument("--logical", type=Path, required=True)
    m1_batch_3_review.add_argument("--expected-revision", required=True)
    m1_batch_3_review.add_argument("--output", type=Path, required=True)
    m1_batch_4_platform = sub.add_parser(
        "m1-batch-4-platform-check",
        help="Qualify integrated M1 on one clean platform workspace",
    )
    m1_batch_4_platform.add_argument("--batch1", type=Path, required=True)
    m1_batch_4_platform.add_argument("--batch2-service", type=Path, required=True)
    m1_batch_4_platform.add_argument("--batch3-desktop", type=Path, required=True)
    m1_batch_4_platform.add_argument("--expected-revision", required=True)
    m1_batch_4_platform.add_argument("--repo-root", type=Path, default=REPO_ROOT)
    m1_batch_4_platform.add_argument("--evidence", type=Path, required=True)
    m1_batch_4_compare = sub.add_parser(
        "m1-batch-4-compare",
        help="Compare integrated Windows/Linux M1 logical products",
    )
    m1_batch_4_compare.add_argument("--windows", type=Path, required=True)
    m1_batch_4_compare.add_argument("--linux", type=Path, required=True)
    m1_batch_4_compare.add_argument("--expected-revision", required=True)
    m1_batch_4_compare.add_argument("--evidence", type=Path, required=True)
    m1_exit_review = sub.add_parser(
        "m1-exit-review",
        help="Aggregate all M1 task evidence and gate M1 Exit GO on protected main",
    )
    m1_exit_review.add_argument("--artifact-root", type=Path, required=True)
    m1_exit_review.add_argument("--batch1-logical", type=Path, required=True)
    m1_exit_review.add_argument("--batch2-review", type=Path, required=True)
    m1_exit_review.add_argument("--batch3-review", type=Path, required=True)
    m1_exit_review.add_argument("--batch4-windows", type=Path, required=True)
    m1_exit_review.add_argument("--batch4-linux", type=Path, required=True)
    m1_exit_review.add_argument("--batch4-logical", type=Path, required=True)
    m1_exit_review.add_argument("--expected-revision", required=True)
    m1_exit_review.add_argument("--event-name", required=True)
    m1_exit_review.add_argument("--git-ref", required=True)
    m1_exit_review.add_argument("--output", type=Path, required=True)
    m1_activation = sub.add_parser(
        "m1-entry-activation",
        help="Verify/activate an M1 Entry admission candidate",
    )
    m1_activation.add_argument(
        "--mode",
        choices=("auto", "blocked", "candidate", "activate"),
        required=True,
    )
    m1_activation.add_argument("--event-name")
    m1_activation.add_argument("--git-ref")
    m1_activation.add_argument("--source-revision", required=True)
    m1_activation.add_argument("--windows-manifest", type=Path, required=True)
    m1_activation.add_argument("--linux-manifest", type=Path, required=True)
    m1_activation.add_argument("--output", type=Path, required=True)
    m1_roles = sub.add_parser(
        "m1-entry-assign-roles",
        help="Render explicit §19.1(8) role assignments into an admission candidate",
    )
    m1_roles.add_argument("--primary-ws-owner", required=True)
    m1_roles.add_argument("--golden-independent-reviewer", required=True)
    m1_roles.add_argument("--m1-exit-reviewer", required=True)
    m1_roles.add_argument("--golden-independence-attestation", required=True)
    m1_roles.add_argument("--roles-output", type=Path, required=True)
    m1_roles.add_argument("--review-output", type=Path, required=True)
    ci_check = sub.add_parser("ci-check", help="Run the governed M0 cross-platform CI gate set")
    ci_check.add_argument("--expected-platform", choices=("windows", "linux"))
    ci_check.add_argument("--evidence", type=Path)
    package = sub.add_parser("package", help="Build an M0 development package")
    package.add_argument("--profile", required=True)
    package.add_argument("--output", type=Path, required=True)
    sub.add_parser("package-smoke", help="Clean install/start/stop current-OS Desktop and Service bundles")
    manifest = sub.add_parser("manifest", help="Generate build/SBOM/license/native-dependency evidence")
    manifest.add_argument("--profile", required=True)
    manifest.add_argument("--output", type=Path, required=True)
    m1_manifest = sub.add_parser("m1-entry-manifest", help="Generate M1 Entry build-manifest evidence")
    m1_manifest.add_argument("--profile", required=True)
    m1_manifest.add_argument("--output", type=Path, required=True)
    cold_start = sub.add_parser("cold-start", help="Rebuild M0 from a clean clone and rerun gates")
    cold_start.add_argument("--expected-platform", choices=("windows", "linux"))
    cold_start.add_argument("--evidence", type=Path)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    command = args.command
    if command == "list":
        return cmd_list(args.json)
    if command == "bootstrap":
        return cmd_bootstrap(args.check_only, args.with_quality_tools)
    if command == "verify-baseline":
        return _baseline_check()
    if command == "verify-canonical":
        return _run([sys.executable, str(CANONICAL_VERIFY)])
    if command == "doctor":
        return cmd_doctor(args.strict)
    if command == "format":
        return cmd_quality("formatter", ["--check"] if args.check else [])
    if command == "lint":
        return cmd_quality("linter", [])
    if command == "typecheck":
        return cmd_quality("type_checker", [])
    if command == "test":
        return cmd_test(None)
    suite_paths = {
        "test-unit": "tests/unit",
        "test-contract": "tests/contract",
        "test-golden": "tests/golden",
        "test-replay": "tests/replay",
        "test-migration": "tests/migration",
        "test-e2e": "tests/e2e",
        "test-platform": "tests/platform",
    }
    if command in suite_paths:
        return cmd_test(suite_paths[command])
    if command == "fixture-check":
        fixture_args = [sys.executable, str(FIXTURE_HARNESS), "check"]
        if args.bundle is not None:
            fixture_args.extend(["--bundle", str(args.bundle)])
        if args.evidence is not None:
            fixture_args.extend(["--evidence", str(args.evidence)])
        return _run(fixture_args)
    if command == "platform-logical-product":
        product_args = [
            sys.executable,
            str(FIXTURE_HARNESS),
            "platform-product",
            "--output",
            str(args.output),
        ]
        if args.bundle is not None:
            product_args.extend(["--bundle", str(args.bundle)])
        return _run(product_args)
    if command == "compare-platform-logical":
        return _run(
            [
                sys.executable,
                str(FIXTURE_HARNESS),
                "compare-platform",
                "--windows",
                str(args.windows),
                "--linux",
                str(args.linux),
                "--evidence",
                str(args.evidence),
            ]
        )
    if command == "generate":
        args_out = [sys.executable, str(CODEGEN_GENERATE)]
        if args.check:
            args_out.append("--check")
        return _run(args_out)
    if command == "verify-generated":
        return _run([sys.executable, str(CODEGEN_VERIFY_GENERATED)])
    if command == "regenerate-diff":
        return _run([sys.executable, str(CODEGEN_REGENERATE_DIFF)])
    if command == "verify-architecture":
        return _run([sys.executable, str(ARCHITECTURE_VERIFY)])
    if command == "verify-repository-policy":
        return _run([sys.executable, str(REPOSITORY_POLICY_VERIFY)])
    if command == "verify-desktop-lifecycle-policy":
        return _run([sys.executable, str(DESKTOP_LIFECYCLE_POLICY_VERIFY)])
    if command == "api-smoke":
        return _run([sys.executable, str(API_SMOKE)])
    if command == "gui-smoke":
        gui_args = [sys.executable, str(GUI_SMOKE)]
        if args.headless:
            gui_args.append("--headless")
        return _run(gui_args)
    if command == "desktop-backend-smoke":
        return _run([sys.executable, str(DESKTOP_BACKEND_SMOKE)])
    if command == "ui-automation-smoke":
        automation_args = [sys.executable, str(UI_AUTOMATION_SMOKE), "--timeout", str(args.timeout)]
        if args.show:
            automation_args.append("--show")
        return _run(automation_args)
    if command == "verify-ci":
        return _run([sys.executable, str(CI_VERIFY)])
    if command == "verify-governance":
        return _run([sys.executable, str(GOVERNANCE_VERIFY)])
    if command == "verify-repository-bootstrap":
        return _run([sys.executable, str(REPOSITORY_BOOTSTRAP_VERIFY)])
    if command == "verify-m0-delta-closure":
        return _run([sys.executable, str(M0_DELTA_CLOSURE_VERIFY)])
    if command == "verify-m1-entry-preparation":
        return _run([sys.executable, "-m", M1_ENTRY_PREPARATION_MODULE])
    if command == "verify-m1-entry-gate-state":
        return _run([sys.executable, "-m", M1_ENTRY_GATE_STATE_MODULE])
    if command == "verify-m1-detailed-design":
        return _run([sys.executable, "-m", M1_DETAILED_DESIGN_VERIFY_MODULE])
    if command == "m1-source-adapter-check":
        source_args = [sys.executable, "-m", M1_SOURCE_ADAPTER_CHECK_MODULE]
        if args.evidence is not None:
            source_args.extend(["--evidence", str(args.evidence)])
        return _run(source_args)
    if command == "m2-reference-truth-check":
        reference_args = [sys.executable, "-m", M2_REFERENCE_TRUTH_CHECK_MODULE]
        if args.evidence is not None:
            reference_args.extend(["--evidence", str(args.evidence)])
        return _run(reference_args)
    if command == "m2-time-alignment-check":
        time_alignment_args = [sys.executable, "-m", M2_TIME_ALIGNMENT_CHECK_MODULE]
        if args.evidence is not None:
            time_alignment_args.extend(["--evidence", str(args.evidence)])
        return _run(time_alignment_args)
    if command == "m2-mission-system-check":
        mission_system_args = [sys.executable, "-m", M2_MISSION_SYSTEM_CHECK_MODULE]
        if args.evidence is not None:
            mission_system_args.extend(["--evidence", str(args.evidence)])
        return _run(mission_system_args)
    if command == "m2-measurement-alignment-check":
        measurement_args = [sys.executable, "-m", M2_MEASUREMENT_ALIGNMENT_CHECK_MODULE]
        if args.evidence is not None:
            measurement_args.extend(["--evidence", str(args.evidence)])
        return _run(measurement_args)
    if command == "m2-fixture-family-check":
        family_args = [sys.executable, "-m", M2_FIXTURE_FAMILY_CHECK_MODULE, "check"]
        if args.evidence is not None:
            family_args.extend(["--evidence", str(args.evidence)])
        return _run(family_args)
    if command == "m2-fixture-family-compare":
        return _run(
            [
                sys.executable,
                "-m",
                M2_FIXTURE_FAMILY_CHECK_MODULE,
                "compare",
                "--windows",
                str(args.windows),
                "--linux",
                str(args.linux),
                "--expected-revision",
                args.expected_revision,
                "--evidence",
                str(args.evidence),
            ]
        )
    if command == "m2-reference-time-world-check":
        world_args = [sys.executable, "-m", M2_REFERENCE_TIME_WORLD_CHECK_MODULE]
        if args.evidence is not None:
            world_args.extend(["--evidence", str(args.evidence)])
        return _run(world_args)
    if command == "m2-reference-time-world-compare":
        return _run(
            [
                sys.executable,
                "-m",
                M2_REFERENCE_TIME_WORLD_COMPARE_MODULE,
                "--windows",
                str(args.windows),
                "--linux",
                str(args.linux),
                "--expected-revision",
                args.expected_revision,
                "--evidence",
                str(args.evidence),
            ]
        )
    if command == "m2-radar-sensor-world-check":
        radar_args = [sys.executable, "-m", M2_RADAR_SENSOR_WORLD_CHECK_MODULE]
        if args.evidence is not None:
            radar_args.extend(["--evidence", str(args.evidence)])
        return _run(radar_args)
    if command == "m2-radar-sensor-world-compare":
        return _run(
            [
                sys.executable,
                "-m",
                M2_RADAR_SENSOR_WORLD_COMPARE_MODULE,
                "--windows",
                str(args.windows),
                "--linux",
                str(args.linux),
                "--expected-revision",
                args.expected_revision,
                "--evidence",
                str(args.evidence),
            ]
        )
    if command == "m2-stage-world-lineage-check":
        lineage_args = [sys.executable, "-m", M2_STAGE_WORLD_LINEAGE_CHECK_MODULE]
        if args.evidence is not None:
            lineage_args.extend(["--evidence", str(args.evidence)])
        return _run(lineage_args)
    if command == "m2-stage-world-lineage-compare":
        return _run(
            [
                sys.executable,
                "-m",
                M2_STAGE_WORLD_LINEAGE_COMPARE_MODULE,
                "--windows",
                str(args.windows),
                "--linux",
                str(args.linux),
                "--expected-revision",
                args.expected_revision,
                "--evidence",
                str(args.evidence),
            ]
        )
    if command == "m2-general-metric-engine-check":
        metric_args = [sys.executable, "-m", M2_GENERAL_METRIC_ENGINE_CHECK_MODULE]
        if args.evidence is not None:
            metric_args.extend(["--evidence", str(args.evidence)])
        return _run(metric_args)
    if command == "m2-general-metric-engine-compare":
        return _run(
            [
                sys.executable,
                "-m",
                M2_GENERAL_METRIC_ENGINE_COMPARE_MODULE,
                "--windows",
                str(args.windows),
                "--linux",
                str(args.linux),
                "--expected-revision",
                args.expected_revision,
                "--evidence",
                str(args.evidence),
            ]
        )
    if command == "m2-qa-foundation-incremental-check":
        qa_args = [sys.executable, "-m", M2_QA_FOUNDATION_INCREMENTAL_CHECK_MODULE]
        if args.evidence is not None:
            qa_args.extend(["--evidence", str(args.evidence)])
        return _run(qa_args)
    if command == "m2-qa-foundation-incremental-compare":
        return _run(
            [
                sys.executable,
                "-m",
                M2_QA_FOUNDATION_INCREMENTAL_COMPARE_MODULE,
                "--windows",
                str(args.windows),
                "--linux",
                str(args.linux),
                "--expected-revision",
                args.expected_revision,
                "--evidence",
                str(args.evidence),
            ]
        )
    if command == "m2-air-formal-delivery-check":
        air_args = [sys.executable, "-m", M2_AIR_FORMAL_DELIVERY_CHECK_MODULE]
        if args.evidence is not None:
            air_args.extend(["--evidence", str(args.evidence)])
        return _run(air_args)
    if command == "m2-air-formal-delivery-compare":
        return _run(
            [
                sys.executable,
                "-m",
                M2_AIR_FORMAL_DELIVERY_COMPARE_MODULE,
                "--windows",
                str(args.windows),
                "--linux",
                str(args.linux),
                "--expected-revision",
                args.expected_revision,
                "--evidence",
                str(args.evidence),
            ]
        )
    if command == "m2-sns-detection-check":
        sns_args = [sys.executable, "-m", M2_SNS_DETECTION_CHECK_MODULE]
        if args.evidence is not None:
            sns_args.extend(["--evidence", str(args.evidence)])
        return _run(sns_args)
    if command == "m2-sns-detection-compare":
        return _run(
            [
                sys.executable,
                "-m",
                M2_SNS_DETECTION_COMPARE_MODULE,
                "--windows",
                str(args.windows),
                "--linux",
                str(args.linux),
                "--expected-revision",
                args.expected_revision,
                "--evidence",
                str(args.evidence),
            ]
        )
    if command == "m1-source-registry-check":
        registry_args = [sys.executable, "-m", M1_SOURCE_REGISTRY_CHECK_MODULE]
        if args.evidence is not None:
            registry_args.extend(["--evidence", str(args.evidence)])
        return _run(registry_args)
    if command == "m1-session-time-check":
        time_args = [sys.executable, "-m", M1_SESSION_TIME_CHECK_MODULE]
        if args.evidence is not None:
            time_args.extend(["--evidence", str(args.evidence)])
        return _run(time_args)
    if command == "m1-aircraft-identity-check":
        aircraft_args = [sys.executable, "-m", M1_AIRCRAFT_IDENTITY_CHECK_MODULE]
        if args.evidence is not None:
            aircraft_args.extend(["--evidence", str(args.evidence)])
        return _run(aircraft_args)
    if command == "m1-canonical-flight-channels-check":
        canonical_args = [
            sys.executable,
            "-m",
            M1_CANONICAL_FLIGHT_CHANNELS_CHECK_MODULE,
        ]
        if args.evidence is not None:
            canonical_args.extend(["--evidence", str(args.evidence)])
        return _run(canonical_args)
    if command == "m1-evaluation-context-check":
        context_args = [sys.executable, "-m", M1_EVALUATION_CONTEXT_CHECK_MODULE]
        if args.evidence is not None:
            context_args.extend(["--evidence", str(args.evidence)])
        return _run(context_args)
    if command == "m1-lineage-quality-check":
        lineage_args = [sys.executable, "-m", M1_LINEAGE_QUALITY_CHECK_MODULE]
        if args.evidence is not None:
            lineage_args.extend(["--evidence", str(args.evidence)])
        return _run(lineage_args)
    if command == "m1-basic-episode-check":
        episode_args = [sys.executable, "-m", M1_BASIC_EPISODE_CHECK_MODULE]
        if args.evidence is not None:
            episode_args.extend(["--evidence", str(args.evidence)])
        return _run(episode_args)
    if command == "m1-basic-stage-check":
        stage_args = [sys.executable, "-m", M1_BASIC_STAGE_CHECK_MODULE]
        if args.evidence is not None:
            stage_args.extend(["--evidence", str(args.evidence)])
        return _run(stage_args)
    if command == "m1-stage-quality-check":
        quality_args = [sys.executable, "-m", M1_STAGE_QUALITY_CHECK_MODULE]
        if args.evidence is not None:
            quality_args.extend(["--evidence", str(args.evidence)])
        return _run(quality_args)
    if command == "m1-batch-1-core-check":
        batch_args = [sys.executable, "-m", M1_BATCH_1_CORE_CHECK_MODULE]
        if args.evidence is not None:
            batch_args.extend(["--evidence", str(args.evidence)])
        return _run(batch_args)
    if command == "m1-batch-1-compare":
        return _run(
            [
                sys.executable,
                "-m",
                M1_BATCH_1_COMPARE_MODULE,
                "--windows",
                str(args.windows),
                "--linux",
                str(args.linux),
                "--expected-revision",
                args.expected_revision,
                "--evidence",
                str(args.evidence),
            ]
        )
    if command == "m1-batch-2-service-smoke":
        return _run(
            [
                sys.executable,
                "-m",
                M1_BATCH_2_SERVICE_SMOKE_MODULE,
                "--expected-platform",
                args.expected_platform,
                "--source-revision",
                args.source_revision,
                "--evidence",
                str(args.evidence),
            ]
        )
    if command == "m1-batch-2-service-compare":
        return _run(
            [
                sys.executable,
                "-m",
                M1_BATCH_2_SERVICE_COMPARE_MODULE,
                "--windows",
                str(args.windows),
                "--linux",
                str(args.linux),
                "--evidence",
                str(args.evidence),
            ]
        )
    if command == "m1-batch-2-storage-parity":
        parity_args = [
            sys.executable,
            "-m",
            M1_BATCH_2_STORAGE_PARITY_MODULE,
            "--user",
            args.user,
            "--admin-database",
            args.admin_database,
            "--database",
            args.database,
            "--conninfo-template",
            args.conninfo_template,
            "--source-revision",
            args.source_revision,
            "--evidence",
            str(args.evidence),
        ]
        if args.host:
            parity_args.extend(["--host", args.host])
        if args.port is not None:
            parity_args.extend(["--port", str(args.port)])
        if args.psql:
            parity_args.extend(["--psql", args.psql])
        return _run(parity_args)
    if command == "m1-batch-2-backend-check":
        return _run(
            [
                sys.executable,
                "-m",
                M1_BATCH_2_BACKEND_CHECK_MODULE,
                "--platform",
                args.platform,
                "--source-revision",
                args.source_revision,
                "--evidence",
                str(args.evidence),
            ]
        )
    if command == "m1-batch-2-review":
        return _run(
            [
                sys.executable,
                "-m",
                M1_BATCH_2_REVIEW_MODULE,
                "--expected-revision",
                args.expected_revision,
                "--windows-backend",
                str(args.windows_backend),
                "--linux-backend",
                str(args.linux_backend),
                "--windows-service",
                str(args.windows_service),
                "--linux-service",
                str(args.linux_service),
                "--service-logical",
                str(args.service_logical),
                "--storage-parity",
                str(args.storage_parity),
                "--output",
                str(args.output),
            ]
        )
    if command == "m1-batch-3-desktop-e2e":
        return _run(
            [
                sys.executable,
                "-m",
                M1_BATCH_3_DESKTOP_E2E_MODULE,
                "--expected-platform",
                args.expected_platform,
                "--source-revision",
                args.source_revision,
                "--evidence",
                str(args.evidence),
                "--timeout",
                str(args.timeout),
            ]
        )
    if command == "m1-batch-3-desktop-compare":
        return _run(
            [
                sys.executable,
                "-m",
                M1_BATCH_3_DESKTOP_COMPARE_MODULE,
                "--windows",
                str(args.windows),
                "--linux",
                str(args.linux),
                "--expected-revision",
                args.expected_revision,
                "--evidence",
                str(args.evidence),
            ]
        )
    if command == "m1-batch-3-review":
        return _run(
            [
                sys.executable,
                "-m",
                M1_BATCH_3_REVIEW_MODULE,
                "--windows",
                str(args.windows),
                "--linux",
                str(args.linux),
                "--logical",
                str(args.logical),
                "--expected-revision",
                args.expected_revision,
                "--output",
                str(args.output),
            ]
        )
    if command == "m1-batch-4-platform-check":
        return _run(
            [
                sys.executable,
                "-m",
                M1_BATCH_4_PLATFORM_CHECK_MODULE,
                "--batch1",
                str(args.batch1),
                "--batch2-service",
                str(args.batch2_service),
                "--batch3-desktop",
                str(args.batch3_desktop),
                "--expected-revision",
                args.expected_revision,
                "--repo-root",
                str(args.repo_root),
                "--evidence",
                str(args.evidence),
            ]
        )
    if command == "m1-batch-4-compare":
        return _run(
            [
                sys.executable,
                "-m",
                M1_BATCH_4_COMPARE_MODULE,
                "--windows",
                str(args.windows),
                "--linux",
                str(args.linux),
                "--expected-revision",
                args.expected_revision,
                "--evidence",
                str(args.evidence),
            ]
        )
    if command == "m1-exit-review":
        return _run(
            [
                sys.executable,
                "-m",
                M1_EXIT_REVIEW_MODULE,
                "--artifact-root",
                str(args.artifact_root),
                "--batch1-logical",
                str(args.batch1_logical),
                "--batch2-review",
                str(args.batch2_review),
                "--batch3-review",
                str(args.batch3_review),
                "--batch4-windows",
                str(args.batch4_windows),
                "--batch4-linux",
                str(args.batch4_linux),
                "--batch4-logical",
                str(args.batch4_logical),
                "--expected-revision",
                args.expected_revision,
                "--event-name",
                args.event_name,
                "--git-ref",
                args.git_ref,
                "--output",
                str(args.output),
            ]
        )
    if command == "m1-fixture-check":
        fixture_args = [sys.executable, "-m", M1_FIXTURE_HARNESS_MODULE]
        if args.bundle is not None:
            fixture_args.extend(["--bundle", args.bundle])
        if args.evidence is not None:
            fixture_args.extend(["--evidence", str(args.evidence)])
        return _run(fixture_args)
    if command == "m1-entry-activation":
        return _run(
            [
                sys.executable,
                "-m",
                M1_ENTRY_ACTIVATION_MODULE,
                "--mode",
                args.mode,
                "--source-revision",
                args.source_revision,
                "--windows-manifest",
                str(args.windows_manifest),
                "--linux-manifest",
                str(args.linux_manifest),
                *(
                    ["--event-name", args.event_name]
                    if args.event_name is not None
                    else []
                ),
                *(
                    ["--git-ref", args.git_ref]
                    if args.git_ref is not None
                    else []
                ),
                "--output",
                str(args.output),
            ]
        )
    if command == "m1-entry-assign-roles":
        return _run(
            [
                sys.executable,
                "-m",
                M1_ENTRY_ASSIGN_ROLES_MODULE,
                "--primary-ws-owner",
                args.primary_ws_owner,
                "--golden-independent-reviewer",
                args.golden_independent_reviewer,
                "--m1-exit-reviewer",
                args.m1_exit_reviewer,
                "--golden-independence-attestation",
                args.golden_independence_attestation,
                "--roles-output",
                str(args.roles_output),
                "--review-output",
                str(args.review_output),
            ]
        )
    if command == "platform-smoke":
        return _run([sys.executable, str(PLATFORM_SMOKE)])
    if command == "openapi-snapshot":
        openapi_args = [sys.executable, str(OPENAPI_SNAPSHOT)]
        if args.check:
            openapi_args.append("--check")
        return _run(openapi_args)
    if command == "migration-smoke":
        return _run([sys.executable, str(MIGRATION_HARNESS)])
    if command == "backup-restore-smoke":
        return _run([sys.executable, str(BACKUP_RESTORE_SMOKE)])
    if command == "security-smoke":
        return _run([sys.executable, str(SECURITY_SMOKE)])
    if command == "manifest":
        return _run(
            [
                sys.executable,
                str(MANIFEST_TOOL),
                "--profile",
                args.profile,
                "--output",
                str(args.output),
            ]
        )
    if command == "m1-entry-manifest":
        return _run(
            [
                sys.executable,
                "-m",
                M1_ENTRY_MANIFEST_MODULE,
                "--profile",
                args.profile,
                "--output",
                str(args.output),
            ]
        )
    if command == "package":
        return _run(
            [
                sys.executable,
                str(PACKAGE_TOOL),
                "--profile",
                args.profile,
                "--output",
                str(args.output),
            ]
        )
    if command == "package-smoke":
        return _run([sys.executable, str(PACKAGE_SMOKE)])
    if command == "cold-start":
        cold_args = [sys.executable, str(COLD_START)]
        if args.expected_platform:
            cold_args.extend(["--expected-platform", args.expected_platform])
        if args.evidence is not None:
            cold_args.extend(["--evidence", str(args.evidence)])
        return _run(cold_args)
    if command == "ci-check":
        ci_args = [sys.executable, str(CI_GATE)]
        if args.expected_platform:
            ci_args.extend(["--expected-platform", args.expected_platform])
        if args.evidence is not None:
            ci_args.extend(["--evidence", str(args.evidence)])
        return _run(ci_args)
    if command == "db-bootstrap":
        return _run([sys.executable, str(STORAGE_BOOTSTRAP), "bootstrap", str(args.database)])
    if command == "db-verify":
        return _run([sys.executable, str(STORAGE_BOOTSTRAP), "verify", str(args.database)])
    if command == "db-sqlite-repository-acceptance":
        return _run([sys.executable, str(SQLITE_REPOSITORY), "acceptance"])
    if command == "db-postgres-repository-acceptance":
        repo_args = [sys.executable, str(POSTGRES_REPOSITORY)]
        if args.user:
            repo_args.extend(["--user", args.user])
        if args.host:
            repo_args.extend(["--host", args.host])
        if args.port is not None:
            repo_args.extend(["--port", str(args.port)])
        if args.psql:
            repo_args.extend(["--psql", args.psql])
        if args.docker_container:
            repo_args.extend(["--docker-container", args.docker_container])
        repo_args.extend([
            "--admin-database", args.admin_database,
            "--database", args.database,
            "--conninfo-template", args.conninfo_template,
        ])
        return _run(repo_args)
    if command in {"db-postgres-bootstrap", "db-postgres-verify", "db-postgres-acceptance"}:
        pg_args = [sys.executable, str(POSTGRES_STORAGE)]
        if args.user:
            pg_args.extend(["--user", args.user])
        if args.host:
            pg_args.extend(["--host", args.host])
        if args.port is not None:
            pg_args.extend(["--port", str(args.port)])
        if args.psql:
            pg_args.extend(["--psql", args.psql])
        if args.docker_container:
            pg_args.extend(["--docker-container", args.docker_container])
        if command == "db-postgres-acceptance":
            pg_args.extend(["acceptance", "--admin-database", args.admin_database, "--database", args.database])
        else:
            action = "bootstrap" if command == "db-postgres-bootstrap" else "verify"
            pg_args.extend([action, args.database])
        return _run(pg_args)
    if command == "run":
        if args.target == "gui":
            return _run([sys.executable, "-m", "tpaa_gui"])
        return _reserved("M0-API-002", "run api")
    reserved = {
        "run-api": "M0-API-002",
    }
    if command == "run-gui":
        return _run([sys.executable, "-m", "tpaa_gui"])
    if command in reserved:
        return _reserved(reserved[command], command)
    parser.error(f"unknown command: {command}")


if __name__ == "__main__":
    raise SystemExit(main())
