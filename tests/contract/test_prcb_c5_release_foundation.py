from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
BASE = ROOT / "docs" / "baseline" / "PRCB-1.0"


def test_prcb_c5_release_contract_freezes_four_production_profiles() -> None:
    contract = json.loads(
        (BASE / "C5_RELEASE_CONTRACT.json").read_text(encoding="utf-8")
    )
    assert contract["schema"] == "TPAA_PRCB_C5_RELEASE_CONTRACT_V1"
    assert contract["target_product_version"] == "1.0.1"
    assert contract["db_schema_version"] == "1.9.0"
    assert contract["mandatory_profiles"] == [
        "LINUX_DESKTOP_X64",
        "LINUX_SERVICE_X64",
        "WINDOWS_DESKTOP_X64",
        "WINDOWS_SERVICE_X64",
    ]
    policy = contract["package_policy"]
    assert policy["tests_packaged"] is False
    assert policy["fixtures_packaged"] is False
    assert policy["formal_release_claimed"] is False


def test_prcb_c5_package_path_is_separate_from_historical_piqb() -> None:
    packager = (ROOT / "tools" / "packaging" / "prcb_release_bundle.py").read_text(
        encoding="utf-8"
    )
    runtime = (ROOT / "tools" / "packaging" / "prcb_runtime_entry.py").read_text(
        encoding="utf-8"
    )
    assert "TPAA_1_0_1_CANDIDATE_NOT_QUALIFIED" in packager
    assert "prcb-release" in packager
    assert "app/tests/" in packager
    assert "/fixtures/" in packager
    assert "ProductRuntimeConfig" not in runtime
    assert "ProductionRuntimeConfig" in runtime
    assert "build_desktop_production_runtime" in runtime
    assert "build_service_production_runtime" in runtime
    assert "m1_fixture_root" not in runtime
    assert "desktop-e2e" in runtime
    assert "desktop-p1-e2e" in runtime
    assert "service-e2e" in runtime
    assert "P2_ATTRIBUTION" in runtime
    assert "P3_ESTIMATE" in runtime
    assert "P4_ASSESSMENT" in runtime
    assert "P5_ASSESSMENT" in runtime
    assert "P6_FORECAST" in runtime
    assert "P6_COUNTERFACTUAL" in runtime
    assert "prepare_prcb_c5_p2_workspace" in runtime
    assert "bootstrap_sqlite" in runtime
    assert "create_desktop_production_backup" in runtime
    assert "restore_desktop_production_backup" in runtime
    assert "SQLiteDesktopUnitOfWork" in runtime
    assert "formal_release_claimed" in runtime
    assert 'release.get("world_product_count") != 4' in runtime
    assert '"episode.episode_stage"' in runtime
    assert '"world.world_relation"' in runtime
    assert "PRCB_C2_NOMINAL_FLIGHT.json" in packager
    assert '%~1' in packager
    assert 'goto default' in packager
    assert '$#' in packager
    assert 'then set --' in packager


def test_prcb_c5_installed_desktop_qualification_runs_inside_existing_jobs() -> None:
    workflow = (ROOT / ".github" / "workflows" / "cross-platform-ci.yml").read_text(
        encoding="utf-8"
    )
    tool = (
        ROOT
        / "tools"
        / "testing"
        / "prcb_c5_installed_desktop_qualification.py"
    ).read_text(encoding="utf-8")
    assert "Execute PRCB C5 installed Desktop P1-P6 qualification" in workflow
    assert "prcb_c5_installed_desktop_qualification.py" in workflow
    assert "dist/prcb-c5/${{ matrix.platform }}" in workflow
    assert "TPAA_PRCB_C5_INSTALLED_DESKTOP_QUALIFICATION_V1" in tool
    assert "build_prcb_release_bundle" in tool
    assert "desktop-e2e" in tool
    assert "package_sha256" in tool
    assert "logical_product_sha256" in tool
    assert "app/tests/" in tool
    assert "/fixtures/" in tool


def test_prcb_c5_p2_qualification_seed_is_product_code_not_test_fixture() -> None:
    source = (
        ROOT / "src" / "tpaa_qualification" / "prcb_c5_p2.py"
    ).read_text(encoding="utf-8")
    assert "prepare_prcb_c5_p2_workspace" in source
    assert "P2PersistenceRepository" in source
    assert "register_workspace_inputs" in source
    assert "materialize_factor_feature_set" in source
    assert 'input_hash="8" * 64' not in source
    assert "exact_compute_input" in source
    assert "QUALIFICATION_AS_OF_UTC" in source
    assert "QUALIFICATION_EXECUTION_TIME_UTC" in source
    assert "datetime.now" not in source
    assert "tests/fixtures" not in source
    assert "tools.testing" not in source


def test_prcb_c5_qualification_package_keeps_reviewer_import_lightweight() -> None:
    package = (
        ROOT / "src" / "tpaa_qualification" / "__init__.py"
    ).read_text(encoding="utf-8")
    runtime = (
        ROOT / "tools" / "packaging" / "prcb_runtime_entry.py"
    ).read_text(encoding="utf-8")
    assert ".prcb_c5_p2 import" not in package
    assert "PRCBC5P2QualificationSeed" not in package
    assert "prepare_prcb_c5_p2_workspace" not in package
    assert "from tpaa_qualification.prcb_c5_p2 import" in runtime


def test_prcb_c5_installed_service_uses_postgres_and_frozen_roles() -> None:
    workflow = (ROOT / ".github" / "workflows" / "cross-platform-ci.yml").read_text(
        encoding="utf-8"
    )
    runtime = (ROOT / "tools" / "packaging" / "prcb_runtime_entry.py").read_text(
        encoding="utf-8"
    )
    service = (
        ROOT / "src" / "tpaa_qualification" / "prcb_c5_service_e2e.py"
    ).read_text(encoding="utf-8")
    api = (
        ROOT / "src" / "tpaa_qualification" / "prcb_c5_api_service.py"
    ).read_text(encoding="utf-8")
    tool = (
        ROOT / "tools" / "testing" / "prcb_c5_installed_service_qualification.py"
    ).read_text(encoding="utf-8")

    assert "Execute PRCB C5 installed Service PostgreSQL qualification" in workflow
    assert "prcb_c5_installed_service_qualification.py" in workflow
    assert "--profile LINUX_SERVICE_X64" in workflow
    assert "service-e2e" in runtime
    assert "TPAA_SERVICE_RESTORE_CONNINFO" in runtime
    assert "run_installed_service_e2e" in runtime
    assert "PostgreSQLServiceUnitOfWork" in service
    assert "build_service_production_runtime" in service
    assert "create_service_production_backup" in service
    assert "restore_service_production_backup" in service
    assert "verify_prcb_c5_service_api" in service
    assert "INSTRUCTOR_EVALUATOR" in service
    assert 'role="ANALYST"' in service
    assert 'role="MODEL_REVIEWER"' not in service
    assert "create_production_service_app" in api
    assert "PRCB_C5_SERVICE_MODEL_REVIEWER_ROLE_EXPANSION" in api
    assert "app/tests/" in tool
    assert "/fixtures/" in tool
    assert "bootstrap_postgres" in tool
    assert "verify_postgres" in tool
    assert "real_postgresql_executed" in tool
    assert "postgres_server_version" in tool
    assert "formal_release_claimed" in tool
    assert 'release.get("world_product_count") != 4' in service
    assert '"episode.episode_stage"' in service
    assert '"world.world_relation"' in service
    assert "Start Windows PostgreSQL for PRCB C5 Service qualification" in workflow
    assert "--profile WINDOWS_SERVICE_X64" in workflow
    assert "tpaa-prcb-c5-service-windows-" in workflow
    assert "tools.testing" not in service
    assert "tests/fixtures" not in service
    assert "InMemory" not in service


def test_prcb_c5_four_profile_logical_equivalence_is_gated_in_existing_job() -> None:
    workflow = (ROOT / ".github" / "workflows" / "cross-platform-ci.yml").read_text(
        encoding="utf-8"
    )
    compare = (
        ROOT / "tools" / "testing" / "prcb_c5_four_profile_equivalence.py"
    ).read_text(encoding="utf-8")
    runtime = (
        ROOT / "tools" / "packaging" / "prcb_runtime_entry.py"
    ).read_text(encoding="utf-8")

    assert "Review PRCB C5 four-profile installed logical equivalence" in workflow
    assert "prcb_c5_four_profile_equivalence.py" in workflow
    assert "evidence/prcb-c5/four-profile-logical-equivalence.json" in workflow
    assert "LINUX_DESKTOP_X64" in compare
    assert "WINDOWS_DESKTOP_X64" in compare
    assert "LINUX_SERVICE_X64" in compare
    assert "WINDOWS_SERVICE_X64" in compare
    assert "desktop_windows_linux_p2_semantic_equivalence" in compare
    assert "service_windows_linux_p2_semantic_equivalence" in compare
    assert "p2_runtime_provenance_by_profile" in compare
    assert '"world_product_count"' in compare
    assert '"stage_count"' in compare
    assert '"world_relation_count"' in compare
    assert "shared_p1_p3_p6_exact_identity_all_profiles" in compare
    assert "formal_release_claimed" in compare
    assert "p2_source_knowledge_time_utc" in runtime
    assert "tests/fixtures" not in compare
    assert "InMemory" not in compare


def test_prcb_c5_exit_review_binds_detached_attestation_to_immutable_evidence() -> None:
    workflow = (ROOT / ".github" / "workflows" / "cross-platform-ci.yml").read_text(
        encoding="utf-8"
    )
    equivalence = (
        ROOT / "tools" / "testing" / "prcb_c5_four_profile_equivalence.py"
    ).read_text(encoding="utf-8")
    reviewer = (
        ROOT / "tools" / "testing" / "prcb_c5_exit_review.py"
    ).read_text(encoding="utf-8")

    assert "installed_evidence_sha256_by_profile" in equivalence
    assert "Review PRCB C5 final installed product and detached attestation" in workflow
    assert "tpaa-prcb-c5-exit-review-" in workflow
    assert "prcb_c5_exit_review.py" in workflow
    assert "--required-jobs-success 14" in workflow
    assert "--required-jobs-total 14" in workflow
    assert "TPAA_PRCB_C5_EXIT_REVIEW_V1" in reviewer
    assert "TPAA_PRCB_C5_DETACHED_ATTESTATION_V1" in reviewer
    assert "TPAA_1_0_1_CANDIDATE_NOT_QUALIFIED" in reviewer
    assert "TPAA_1_0_1_QUALIFIED" in reviewer
    assert 'event_name == "push"' in reviewer
    assert 'git_ref == "refs/heads/main"' in reviewer
    assert "package_sha256_by_profile" in reviewer
    assert "installed_evidence_sha256_by_profile" in reviewer
    assert "attestation_payload_sha256" in reviewer
    assert "tests/fixtures" not in reviewer
    assert "InMemory" not in reviewer
    assert "\n  prcb-c5" not in workflow
