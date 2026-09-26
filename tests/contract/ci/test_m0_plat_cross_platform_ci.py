from __future__ import annotations

import importlib.util
import json
import tomllib
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[3]
VERIFY_PATH = REPO_ROOT / "tools" / "ci" / "verify_ci.py"
WORKFLOW = REPO_ROOT / ".github" / "workflows" / "cross-platform-ci.yml"
DISPATCHER = REPO_ROOT / "tools" / "dev" / "tpaa_dev.py"
GATE_RUNNER = REPO_ROOT / "tools" / "ci" / "run_gate.py"
SOURCE_REVISION = "${{ github.event.pull_request.head.sha || github.sha }}"


def _load_verifier() -> Any:
    spec = importlib.util.spec_from_file_location("tpaa_ci_verify", VERIFY_PATH)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_ci_orchestration_contract_passes() -> None:
    verifier = _load_verifier()
    result = verifier.verify()
    assert result["status"] == "PASS", json.dumps(result, indent=2)


def test_workflow_is_real_windows_and_linux_matrix() -> None:
    text = WORKFLOW.read_text(encoding="utf-8")
    assert "runner: ubuntu-24.04" in text
    assert "runner: windows-2025" in text
    assert "fail-fast: false" in text
    assert "macos" not in text.lower()


def test_workflow_calls_one_governed_ci_gate_command() -> None:
    text = WORKFLOW.read_text(encoding="utf-8")
    assert "python tools/dev/tpaa_dev.py ci-check" in text
    assert "--expected-platform ${{ matrix.platform }}" in text
    assert "continue-on-error" not in text
    assert "|| true" not in text


def test_pull_request_ci_binds_evidence_to_exact_candidate_revision() -> None:
    text = WORKFLOW.read_text(encoding="utf-8")
    assert text.count(f"ref: {SOURCE_REVISION}") == 7
    assert "${{ github.sha }}" not in text
    assert f"pattern: tpaa-ci-*-{SOURCE_REVISION}" in text
    assert f"--expected-revision {SOURCE_REVISION}" in text
    assert f"--source-revision {SOURCE_REVISION}" in text


def test_dispatcher_exposes_step8_commands() -> None:
    text = DISPATCHER.read_text(encoding="utf-8")
    assert 'CommandSpec("verify-ci", "M0-PLAT-004/M0-PLAT-005", "IMPLEMENTED"' in text
    assert 'CommandSpec("ci-check", "M0-PLAT-004/M0-PLAT-005", "IMPLEMENTED"' in text


def test_ci_gate_contains_formal_step8_minimum_and_current_required_gates() -> None:
    text = GATE_RUNNER.read_text(encoding="utf-8")
    required = (
        '_dispatcher("bootstrap", "--check-only")',
        '_dispatcher("test-unit")',
        '_dispatcher("verify-repository-bootstrap")',
        '_dispatcher("verify-m0-delta-closure")',
        '_dispatcher("verify-governance")',
        '_dispatcher("openapi-snapshot", "--check")',
        '_dispatcher("migration-smoke")',
        '_dispatcher("backup-restore-smoke")',
        '_dispatcher("security-smoke")',
        '_dispatcher("package-smoke")',
        '"cold-start"',
        '_dispatcher("test-contract")',
        '_dispatcher("test-golden")',
        '_dispatcher("test-replay")',
        '_dispatcher("test-e2e")',
        '_dispatcher("test-platform")',
        '_dispatcher("platform-smoke")',
        '_dispatcher("api-smoke")',
        '_dispatcher("gui-smoke", "--headless")',
        '_dispatcher("ui-automation-smoke")',
        '_dispatcher("verify-baseline")',
        '_dispatcher("verify-generated")',
        '_dispatcher("verify-architecture")',
        '_dispatcher("lint")',
        '_dispatcher("typecheck")',
        '_dispatcher("m1-batch-1-core-check")',
    )
    for token in required:
        assert token in text


def test_ci_gate_dispatches_step10_package_and_cold_start_fail_closed() -> None:
    text = GATE_RUNNER.read_text(encoding="utf-8")
    assert '_dispatcher("package-smoke")' in text
    assert '"cold-start"' in text
    assert "TPAA_COLD_START_INNER" in text


def test_linux_runner_installs_required_qt_egl_runtime() -> None:
    text = WORKFLOW.read_text(encoding="utf-8")
    assert "if: ${{ matrix.platform == 'linux' }}" in text
    assert "sudo apt-get update && sudo apt-get install --no-install-recommends -y libegl1" in text


def test_pytest_and_mypy_resolve_repository_tool_packages() -> None:
    config = tomllib.loads((REPO_ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    assert config["tool"]["pytest"]["ini_options"]["pythonpath"] == [".", "src"]
    mypy = config["tool"]["mypy"]
    assert mypy["explicit_package_bases"] is True
    assert mypy["mypy_path"] == ["src", "."]
    assert mypy["files"] == ["tools", "src"]
    assert "tests" not in mypy["files"]


def test_step9_fixture_and_logical_equivalence_are_fail_closed_in_ci() -> None:
    text = WORKFLOW.read_text(encoding="utf-8")
    assert "python tools/dev/tpaa_dev.py fixture-check" in text
    assert "--evidence evidence/tests/framework-${{ matrix.platform }}.json" in text
    assert "python tools/dev/tpaa_dev.py platform-logical-product" in text
    assert "--output evidence/cross-platform/${{ matrix.platform }}.json" in text
    assert "m0-logical-equivalence:" in text
    assert "needs: m0-cross-platform" in text
    assert "actions/download-artifact@3e5f45b2cfb9172054b4087a40e8e0b5a5461e7c" in text
    assert "python tools/dev/tpaa_dev.py compare-platform-logical" in text
    assert "--windows downloaded/evidence/cross-platform/windows.json" in text
    assert "--linux downloaded/evidence/cross-platform/linux.json" in text
    assert "--evidence evidence/cross-platform/logical-equivalence.json" in text


def test_step10_workflow_archives_build_evidence_and_packages() -> None:
    text = WORKFLOW.read_text(encoding="utf-8")
    assert "python tools/dev/tpaa_dev.py manifest" in text
    assert "python tools/dev/tpaa_dev.py package" in text
    assert "evidence/devops/${{ matrix.platform }}" in text
    assert "dist/" in text


def test_m1_entry_preparation_is_fail_closed_and_archived() -> None:
    text = WORKFLOW.read_text(encoding="utf-8")
    assert "python tools/dev/tpaa_dev.py verify-m1-entry-preparation" in text
    assert "python tools/dev/tpaa_dev.py m1-entry-manifest" in text
    assert "--profile ${{ matrix.desktop_profile }}" in text
    assert "--output evidence/m1-entry/${{ matrix.platform }}/build-manifest.json" in text
    assert "evidence/m1-entry/${{ matrix.platform }}/build-manifest.json" in text


def test_m1_entry_gate_state_is_verified_in_ci() -> None:
    text = WORKFLOW.read_text(encoding="utf-8")
    assert "python tools/dev/tpaa_dev.py verify-m1-entry-gate-state" in text


def test_m1_detailed_design_is_verified_on_both_platforms() -> None:
    text = WORKFLOW.read_text(encoding="utf-8")
    assert "- name: Verify M1 detailed-design runway" in text
    assert "python tools/dev/tpaa_dev.py verify-m1-detailed-design" in text


def test_m1_tst_001_fixture_evidence_is_archived_on_both_platforms() -> None:
    text = WORKFLOW.read_text(encoding="utf-8")
    assert "- name: Emit M1-TST-001 fixture evidence" in text
    assert "python tools/dev/tpaa_dev.py m1-fixture-check" in text
    assert (
        "--evidence evidence/m1-fixtures/${{ matrix.platform }}/fixture-evidence.json"
        in text
    )
    assert (
        "evidence/m1-fixtures/${{ matrix.platform }}/fixture-evidence.json"
        in text
    )


def test_m1_entry_activation_is_inside_required_exit_review_check() -> None:
    text = WORKFLOW.read_text(encoding="utf-8")
    assert "m0-exit-review:" in text
    assert "- name: Verify or activate M1 Entry" in text
    assert "python tools/dev/tpaa_dev.py m1-entry-activation" in text
    assert "--mode auto" in text
    assert "--event-name ${{ github.event_name }}" in text
    assert "--git-ref ${{ github.ref }}" in text
    assert f"--source-revision {SOURCE_REVISION}" in text
    assert "--windows-manifest downloaded/platform/evidence/m1-entry/windows/build-manifest.json" in text
    assert "--linux-manifest downloaded/platform/evidence/m1-entry/linux/build-manifest.json" in text
    assert "--output evidence/m1-entry/activation.json" in text
    assert f"tpaa-m1-entry-activation-{SOURCE_REVISION}" in text
    assert "m1-entry-activation:" not in text


def test_m0_exit_postgres_and_review_jobs_are_fail_closed() -> None:
    text = WORKFLOW.read_text(encoding="utf-8")
    assert "m0-exit-postgres:" in text
    assert "image: postgres:16" in text
    assert "python tools/dev/tpaa_dev.py db-postgres-acceptance" in text
    assert "python tools/dev/tpaa_dev.py db-postgres-repository-acceptance" in text
    assert "python tools/ci/cold_start.py" in text
    assert "--postgres-conninfo-template" in text
    assert "m0-exit-review:" in text
    assert "needs:" in text
    assert "python tools/ci/m0_exit_review.py" in text
    assert "--output evidence/m0-exit/review.json" in text


def test_m1_data_001_source_adapter_evidence_is_governed_in_ci() -> None:
    text = WORKFLOW.read_text(encoding="utf-8")
    assert "- name: Emit M1-DATA-001 source-adapter evidence" in text
    assert "python tools/dev/tpaa_dev.py m1-source-adapter-check" in text
    assert "--evidence evidence/m1-data-001/${{ matrix.platform }}/source-adapter.json" in text
    assert "evidence/m1-data-001/${{ matrix.platform }}/source-adapter.json" in text
    gate = GATE_RUNNER.read_text(encoding="utf-8")
    assert '_dispatcher("m1-source-adapter-check")' in gate


def test_m1_data_002_source_registry_evidence_is_governed_in_ci() -> None:
    text = WORKFLOW.read_text(encoding="utf-8")
    assert "- name: Emit M1-DATA-002 source-registry evidence" in text
    assert "python tools/dev/tpaa_dev.py m1-source-registry-check" in text
    assert (
        "--evidence evidence/m1-data-002/${{ matrix.platform }}/source-registry.json"
        in text
    )
    assert (
        "evidence/m1-data-002/${{ matrix.platform }}/source-registry.json"
        in text
    )
    gate = GATE_RUNNER.read_text(encoding="utf-8")
    assert '_dispatcher("m1-source-registry-check")' in gate


def test_m1_data_003_session_time_evidence_is_governed_in_ci() -> None:
    text = WORKFLOW.read_text(encoding="utf-8")
    assert "- name: Emit M1-DATA-003 Session Time evidence" in text
    assert "python tools/dev/tpaa_dev.py m1-session-time-check" in text
    assert (
        "--evidence evidence/m1-data-003/${{ matrix.platform }}/session-time.json"
        in text
    )
    assert (
        "evidence/m1-data-003/${{ matrix.platform }}/session-time.json"
        in text
    )
    gate = GATE_RUNNER.read_text(encoding="utf-8")
    assert '_dispatcher("m1-session-time-check")' in gate



def test_m1_data_004_aircraft_identity_evidence_is_governed_in_ci() -> None:
    text = WORKFLOW.read_text(encoding="utf-8")
    assert "- name: Emit M1-DATA-004 aircraft-identity evidence" in text
    assert "python tools/dev/tpaa_dev.py m1-aircraft-identity-check" in text
    assert (
        "--evidence evidence/m1-data-004/${{ matrix.platform }}/aircraft-identity.json"
        in text
    )
    assert (
        "evidence/m1-data-004/${{ matrix.platform }}/aircraft-identity.json"
        in text
    )
    gate = GATE_RUNNER.read_text(encoding="utf-8")
    assert '_dispatcher("m1-aircraft-identity-check")' in gate



def test_m1_data_005_canonical_flight_channel_evidence_is_governed_in_ci() -> None:
    text = WORKFLOW.read_text(encoding="utf-8")
    assert "- name: Emit M1-DATA-005 Canonical-flight-channel evidence" in text
    assert "python tools/dev/tpaa_dev.py m1-canonical-flight-channels-check" in text
    assert (
        "--evidence evidence/m1-data-005/${{ matrix.platform }}/canonical-flight-channels.json"
        in text
    )
    assert (
        "evidence/m1-data-005/${{ matrix.platform }}/canonical-flight-channels.json"
        in text
    )
    gate = GATE_RUNNER.read_text(encoding="utf-8")
    assert '_dispatcher("m1-canonical-flight-channels-check")' in gate


def test_m1_data_006_evaluation_context_evidence_is_governed_in_ci() -> None:
    text = WORKFLOW.read_text(encoding="utf-8")
    assert "- name: Emit M1-DATA-006 Evaluation Context evidence" in text
    assert "python tools/dev/tpaa_dev.py m1-evaluation-context-check" in text
    assert (
        "--evidence evidence/m1-data-006/${{ matrix.platform }}/evaluation-context.json"
        in text
    )
    assert (
        "evidence/m1-data-006/${{ matrix.platform }}/evaluation-context.json"
        in text
    )
    gate = GATE_RUNNER.read_text(encoding="utf-8")
    assert '_dispatcher("m1-evaluation-context-check")' in gate


def test_m1_data_007_lineage_quality_evidence_is_governed_in_ci() -> None:
    text = WORKFLOW.read_text(encoding="utf-8")
    assert "- name: Emit M1-DATA-007 lineage-quality evidence" in text
    assert "python tools/dev/tpaa_dev.py m1-lineage-quality-check" in text
    assert (
        "--evidence evidence/m1-data-007/${{ matrix.platform }}/lineage-quality.json"
        in text
    )
    assert (
        "evidence/m1-data-007/${{ matrix.platform }}/lineage-quality.json"
        in text
    )
    gate = GATE_RUNNER.read_text(encoding="utf-8")
    assert '_dispatcher("m1-lineage-quality-check")' in gate


def test_m1_world_002_basic_stage_evidence_is_governed_in_ci() -> None:
    text = WORKFLOW.read_text(encoding="utf-8")
    assert "- name: Emit M1-WORLD-002 BASIC_FLIGHT_V1 Stage evidence" in text
    assert "python tools/dev/tpaa_dev.py m1-basic-stage-check" in text
    assert (
        "--evidence evidence/m1-world-002/${{ matrix.platform }}/basic-stage.json"
        in text
    )
    assert (
        "evidence/m1-world-002/${{ matrix.platform }}/basic-stage.json"
        in text
    )
    gate = GATE_RUNNER.read_text(encoding="utf-8")
    assert '_dispatcher("m1-basic-stage-check")' in gate


def test_m1_world_003_stage_quality_evidence_is_governed_in_ci() -> None:
    text = WORKFLOW.read_text(encoding="utf-8")
    assert "- name: Emit M1-WORLD-003 Stage quality/status evidence" in text
    assert "python tools/dev/tpaa_dev.py m1-stage-quality-check" in text
    assert (
        "--evidence evidence/m1-world-003/${{ matrix.platform }}/stage-quality.json"
        in text
    )
    assert (
        "evidence/m1-world-003/${{ matrix.platform }}/stage-quality.json"
        in text
    )
    gate = GATE_RUNNER.read_text(encoding="utf-8")
    assert '_dispatcher("m1-stage-quality-check")' in gate


def test_m1_batch_1_core_evidence_is_consolidated_and_cross_platform_compared() -> None:
    text = WORKFLOW.read_text(encoding="utf-8")
    assert "- name: Emit consolidated M1 Batch 1 core evidence" in text
    assert "python tools/dev/tpaa_dev.py m1-batch-1-core-check" in text
    assert (
        "--evidence evidence/m1-batch-1/${{ matrix.platform }}/core-product.json"
        in text
    )
    assert "python tools/dev/tpaa_dev.py m1-batch-1-compare" in text
    assert (
        "--windows downloaded/evidence/m1-batch-1/windows/core-product.json"
        in text
    )
    assert (
        "--linux downloaded/evidence/m1-batch-1/linux/core-product.json"
        in text
    )
    assert (
        "--evidence evidence/cross-platform/m1-batch-1-logical-equivalence.json"
        in text
    )
    gate = GATE_RUNNER.read_text(encoding="utf-8")
    assert '_dispatcher("m1-batch-1-core-check")' in gate


def test_m2_met_003_air_formal_delivery_is_cross_platform_compared() -> None:
    text = WORKFLOW.read_text(encoding="utf-8")
    assert "- name: Emit M2-MET-003 AIR formal-delivery evidence" in text
    assert "python tools/dev/tpaa_dev.py m2-air-formal-delivery-check" in text
    assert (
        "--evidence evidence/m2-met-003/${{ matrix.platform }}/air-formal-delivery.json"
        in text
    )
    assert "- name: Compare Windows and Linux M2-MET-003 AIR formal delivery" in text
    assert "python tools/dev/tpaa_dev.py m2-air-formal-delivery-compare" in text
    assert (
        "--windows downloaded/evidence/m2-met-003/windows/air-formal-delivery.json"
        in text
    )
    assert (
        "--linux downloaded/evidence/m2-met-003/linux/air-formal-delivery.json"
        in text
    )
    assert (
        "--evidence evidence/cross-platform/m2-met-003-logical-equivalence.json"
        in text
    )


def test_m2_met_004_sns_detection_is_cross_platform_compared() -> None:
    text = WORKFLOW.read_text(encoding="utf-8")
    assert "- name: Emit M2-MET-004 SNS detection evidence" in text
    assert "python tools/dev/tpaa_dev.py m2-sns-detection-check" in text
    assert "evidence/m2-met-004/${{ matrix.platform }}/sns-detection.json" in text
    assert "- name: Compare Windows and Linux M2-MET-004 SNS detection" in text
    assert "python tools/dev/tpaa_dev.py m2-sns-detection-compare" in text
    assert "downloaded/evidence/m2-met-004/windows/sns-detection.json" in text
    assert "downloaded/evidence/m2-met-004/linux/sns-detection.json" in text
    assert "evidence/cross-platform/m2-met-004-logical-equivalence.json" in text
    assert "python tools/dev/tpaa_dev.py m2-sns-accuracy-incremental-check" in text
    assert (
        "evidence/m2-met-005/${{ matrix.platform }}/sns-accuracy-incremental.json"
        in text
    )
    assert "python tools/dev/tpaa_dev.py m2-sns-accuracy-incremental-compare" in text
    assert (
        "downloaded/evidence/m2-met-005/windows/sns-accuracy-incremental.json"
        in text
    )
    assert (
        "downloaded/evidence/m2-met-005/linux/sns-accuracy-incremental.json"
        in text
    )
    assert "evidence/cross-platform/m2-met-005-incremental-logical-equivalence.json" in text


def test_m1_batch_2_service_smoke_is_cross_platform_and_logically_compared() -> None:
    text = WORKFLOW.read_text(encoding="utf-8")
    assert "- name: Emit M1 Batch 2 service smoke evidence" in text
    assert "python tools/dev/tpaa_dev.py m1-batch-2-service-smoke" in text
    assert "--expected-platform ${{ matrix.platform }}" in text
    assert f"--source-revision {SOURCE_REVISION}" in text
    assert (
        "--evidence evidence/m1-batch-2/${{ matrix.platform }}/service-smoke.json"
        in text
    )
    assert "evidence/m1-batch-2/${{ matrix.platform }}/service-smoke.json" in text
    assert "- name: Compare Windows and Linux M1 Batch 2 service products" in text
    assert "python tools/dev/tpaa_dev.py m1-batch-2-service-compare" in text
    assert (
        "--windows downloaded/evidence/m1-batch-2/windows/service-smoke.json"
        in text
    )
    assert (
        "--linux downloaded/evidence/m1-batch-2/linux/service-smoke.json"
        in text
    )
    assert (
        "--evidence evidence/cross-platform/m1-batch-2-service-logical-equivalence.json"
        in text
    )
    assert "evidence/cross-platform/m1-batch-2-service-logical-equivalence.json" in text


def test_m1_batch_2_storage_parity_is_real_postgres_hosted_evidence() -> None:
    text = WORKFLOW.read_text(encoding="utf-8")
    assert "- name: Emit M1 Batch 2 SQLite PostgreSQL parity evidence" in text
    assert "python tools/dev/tpaa_dev.py m1-batch-2-storage-parity" in text
    assert "--database tpaa_m1_batch_2_parity" in text
    assert f"--source-revision {SOURCE_REVISION}" in text
    assert "--evidence evidence/m1-batch-2/postgres/storage-parity.json" in text
    assert "- name: Upload M1 Batch 2 PostgreSQL parity evidence" in text
    assert f"tpaa-m1-batch-2-postgres-{SOURCE_REVISION}" in text
    assert "evidence/m1-batch-2/postgres/storage-parity.json" in text


def test_m1_batch_2_backend_acceptance_is_emitted_on_both_platforms() -> None:
    text = WORKFLOW.read_text(encoding="utf-8")
    assert "- name: Emit consolidated M1 Batch 2 backend evidence" in text
    assert "python tools/dev/tpaa_dev.py m1-batch-2-backend-check" in text
    assert "--platform ${{ matrix.platform }}" in text
    assert f"--source-revision {SOURCE_REVISION}" in text
    assert "--evidence evidence/m1-batch-2/${{ matrix.platform }}/backend.json" in text
    assert "evidence/m1-batch-2/${{ matrix.platform }}/backend.json" in text


def test_m1_batch_2_review_aggregates_exact_revision_evidence() -> None:
    text = WORKFLOW.read_text(encoding="utf-8")
    assert "m1-batch-2-review:" in text
    assert "name: M1 Batch 2 Review" in text
    assert "python tools/dev/tpaa_dev.py m1-batch-2-review" in text
    assert f"--expected-revision {SOURCE_REVISION}" in text
    assert (
        "--windows-backend downloaded/platform/evidence/m1-batch-2/windows/backend.json"
        in text
    )
    assert (
        "--linux-backend downloaded/platform/evidence/m1-batch-2/linux/backend.json"
        in text
    )
    assert (
        "--windows-service downloaded/platform/evidence/m1-batch-2/windows/service-smoke.json"
        in text
    )
    assert (
        "--linux-service downloaded/platform/evidence/m1-batch-2/linux/service-smoke.json"
        in text
    )
    assert (
        "--service-logical downloaded/logical/m1-batch-2-service-logical-equivalence.json"
        in text
    )
    assert "--storage-parity downloaded/postgres/storage-parity.json" in text
    assert "--output evidence/m1-batch-2/review.json" in text
    assert f"tpaa-m1-batch-2-review-{SOURCE_REVISION}" in text


def test_m1_batch_3_desktop_e2e_is_cross_platform_compared_and_reviewed() -> None:
    text = WORKFLOW.read_text(encoding="utf-8")
    assert "- name: Emit M1 Batch 3 Desktop E2E evidence" in text
    assert "python tools/dev/tpaa_dev.py m1-batch-3-desktop-e2e" in text
    assert "--expected-platform ${{ matrix.platform }}" in text
    assert f"--source-revision {SOURCE_REVISION}" in text
    assert "--evidence evidence/m1-batch-3/${{ matrix.platform }}/desktop-e2e.json" in text
    assert "- name: Compare Windows and Linux M1 Batch 3 Desktop products" in text
    assert "python tools/dev/tpaa_dev.py m1-batch-3-desktop-compare" in text
    assert "--windows downloaded/evidence/m1-batch-3/windows/desktop-e2e.json" in text
    assert "--linux downloaded/evidence/m1-batch-3/linux/desktop-e2e.json" in text
    assert "--evidence evidence/cross-platform/m1-batch-3-desktop-logical-equivalence.json" in text
    assert "m1-batch-3-review:" in text
    assert "name: M1 Batch 3 Review" in text
    assert "python tools/dev/tpaa_dev.py m1-batch-3-review" in text
    assert "--windows downloaded/platform/evidence/m1-batch-3/windows/desktop-e2e.json" in text
    assert "--linux downloaded/platform/evidence/m1-batch-3/linux/desktop-e2e.json" in text
    assert "--logical downloaded/logical/m1-batch-3-desktop-logical-equivalence.json" in text
    assert "--output evidence/m1-batch-3/review.json" in text
    assert f"tpaa-m1-batch-3-review-{SOURCE_REVISION}" in text



def test_m2_met_006_runtime_contract_increment_is_cross_platform_compared() -> None:
    text = WORKFLOW.read_text(encoding="utf-8")
    assert "- name: Emit incremental M2-MET-006 runtime-contract evidence" in text
    assert "python tools/dev/tpaa_dev.py m2-runtime-contract-incremental-check" in text
    assert (
        text.count(
            "evidence/m2-met-006/${{ matrix.platform }}/runtime-contract-incremental.json"
        )
        >= 2
    )
    assert (
        "- name: Compare Windows and Linux incremental M2-MET-006 runtime contract"
        in text
    )
    assert "python tools/dev/tpaa_dev.py m2-runtime-contract-incremental-compare" in text
    assert (
        "downloaded/evidence/m2-met-006/windows/runtime-contract-incremental.json"
        in text
    )
    assert (
        "downloaded/evidence/m2-met-006/linux/runtime-contract-incremental.json"
        in text
    )
    assert (
        text.count(
            "evidence/cross-platform/m2-met-006-incremental-logical-equivalence.json"
        )
        >= 2
    )



def test_m2_met_007_batch_replay_increment_is_cross_platform_compared() -> None:
    text = WORKFLOW.read_text(encoding="utf-8")
    assert "- name: Emit incremental M2-MET-007 batch/replay evidence" in text
    assert "python tools/dev/tpaa_dev.py m2-batch-replay-incremental-check" in text
    assert (
        text.count(
            "evidence/m2-met-007/${{ matrix.platform }}/batch-replay-incremental.json"
        )
        >= 2
    )
    assert (
        "- name: Compare Windows and Linux incremental M2-MET-007 batch/replay"
        in text
    )
    assert "python tools/dev/tpaa_dev.py m2-batch-replay-incremental-compare" in text
    assert (
        "downloaded/evidence/m2-met-007/windows/batch-replay-incremental.json"
        in text
    )
    assert (
        "downloaded/evidence/m2-met-007/linux/batch-replay-incremental.json"
        in text
    )
    assert (
        text.count(
            "evidence/cross-platform/m2-met-007-incremental-logical-equivalence.json"
        )
        >= 2
    )



def test_m2_batch_2_authority_gap_sentinel_is_cross_platform_compared() -> None:
    text = WORKFLOW.read_text(encoding="utf-8")
    assert "- name: Emit M2 Batch 2 authority-gap sentinel evidence" in text
    assert "python tools/dev/tpaa_dev.py m2-authority-gap-sentinel-check" in text
    assert (
        text.count(
            "evidence/m2-authority-gap/${{ matrix.platform }}/sentinel.json"
        )
        >= 2
    )
    assert (
        "- name: Compare Windows and Linux M2 Batch 2 authority-gap sentinel"
        in text
    )
    assert "python tools/dev/tpaa_dev.py m2-authority-gap-sentinel-compare" in text
    assert "downloaded/evidence/m2-authority-gap/windows/sentinel.json" in text
    assert "downloaded/evidence/m2-authority-gap/linux/sentinel.json" in text
    assert text.count("evidence/cross-platform/m2-authority-gap-sentinel.json") >= 2



def test_m2_batch_2_review_aggregates_exact_revision_without_unblocking() -> None:
    text = WORKFLOW.read_text(encoding="utf-8")
    assert "- name: Review M2 Batch 2 exact-revision gate" in text
    assert "python tools/dev/tpaa_dev.py m2-batch-2-review" in text
    assert "--platform-root downloaded/evidence" in text
    assert "--logical-root evidence/cross-platform" in text
    assert "--expected-revision ${{ github.event.pull_request.head.sha || github.sha }}" in text
    assert "--output evidence/m2-batch-2/review.json" in text

    logical_upload = text.split(
        "- name: Upload logical-equivalence evidence", 1
    )[1].split("- name: Upload M2 Batch 2 review evidence", 1)[0]
    assert "evidence/m2-batch-2/review.json" not in logical_upload

    review_upload = text.split("- name: Upload M2 Batch 2 review evidence", 1)[1]
    assert (
        "name: tpaa-m2-batch-2-review-${{ github.event.pull_request.head.sha || github.sha }}"
        in review_upload
    )
    assert "path: evidence/m2-batch-2/review.json" in review_upload
