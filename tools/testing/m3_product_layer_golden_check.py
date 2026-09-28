#!/usr/bin/env python3
"""M3-TST-004 product-layer 48 Golden/applicability qualification."""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path
from typing import cast

REPO_ROOT = Path(__file__).resolve().parents[2]
TRACKING_ISSUE = 117

EXPECTED_CODES = {
    "TRK": tuple(f"P1-TRK-{index:03d}" for index in range(1, 8)),
    "ID": tuple(f"P1-ID-{index:03d}" for index in range(1, 13)),
    "PSV": tuple(f"P1-PSV-{index:03d}" for index in range(1, 8)),
    "ESM": tuple(f"P1-ESM-{index:03d}" for index in range(1, 7)),
    "DL": tuple(f"P1-DL-{index:03d}" for index in range(1, 9)),
    "FUS": tuple(f"P1-FUS-{index:03d}" for index in range(1, 9)),
}
EXPECTED_TASK_IDS = {
    "TRK": "M3-MET-003",
    "ID": "M3-MET-004",
    "PSV": "M3-MET-005",
    "ESM": "M3-MET-006",
    "DL": "M3-MET-007",
    "FUS": "M3-MET-008",
}
APPLICABILITY_CHECKS = {
    "TRK": (
        "product_applicability_contract_exact",
        "world_positive_local_track_product",
        "world_negative_product_fails_closed",
        "non_applicable_execution_exact_7",
        "runtime_contract_product_mode_enforced",
    ),
    "ID": (
        "product_applicability_contract_exact",
        "world_positive_association_identification_product",
        "world_negative_product_fails_closed",
        "non_applicable_execution_exact_12",
        "runtime_contract_product_mode_enforced",
    ),
    "PSV": (
        "system_type_set_exact_irst_eo",
        "world_irst_applicable",
        "world_eo_applicable",
        "world_radar_fails_closed",
        "radar_execution_fails_closed_exact_7",
        "runtime_contract_system_type_set_enforced",
    ),
    "ESM": (
        "system_type_set_exact",
        "world_rwr_applicable",
        "world_esm_applicable",
        "world_radar_negative",
        "non_applicable_execution_exact_6",
    ),
    "DL": (
        "system_type_exact_datalink",
        "world_datalink_applicable",
        "world_radar_negative",
        "non_applicable_execution_exact_8",
    ),
    "FUS": (
        "system_type_exact_fusion",
        "world_fusion_applicable",
        "world_radar_negative",
        "non_applicable_execution_exact_8",
    ),
}
NEGATIVE_NO_FAKE_CHECKS = {
    "TRK": (
        "world_negative_product_fails_closed",
        "non_applicable_execution_exact_7",
        "runtime_contract_product_mode_enforced",
    ),
    "ID": (
        "world_negative_product_fails_closed",
        "non_applicable_execution_exact_12",
        "runtime_contract_product_mode_enforced",
    ),
    "PSV": (
        "world_radar_fails_closed",
        "radar_execution_fails_closed_exact_7",
        "runtime_contract_system_type_set_enforced",
    ),
    "ESM": (
        "world_radar_negative",
        "non_applicable_execution_exact_6",
    ),
    "DL": (
        "world_radar_negative",
        "non_applicable_execution_exact_8",
    ),
    "FUS": (
        "world_radar_negative",
        "non_applicable_execution_exact_8",
    ),
}


def _git_revision() -> str:
    completed = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=REPO_ROOT,
        check=False,
        capture_output=True,
        text=True,
        timeout=10,
    )
    value = completed.stdout.strip()
    return value if len(value) == 40 else "UNKNOWN"


def _mapping(value: object, *, field: str) -> dict[str, object]:
    if not isinstance(value, dict) or not all(isinstance(key, str) for key in value):
        raise ValueError(f"{field} must be a string-keyed object")
    return cast(dict[str, object], value)


def _strings(value: object, *, field: str) -> tuple[str, ...]:
    if not isinstance(value, list) or not all(isinstance(item, str) for item in value):
        raise ValueError(f"{field} must be a string list")
    return tuple(cast(list[str], value))


def _all_true(acceptance: dict[str, object], names: tuple[str, ...]) -> bool:
    return all(acceptance.get(name) is True for name in names)


def verify() -> dict[str, object]:
    repo_root = str(REPO_ROOT)
    src_root = str(REPO_ROOT / "src")
    if repo_root not in sys.path:
        sys.path.insert(0, repo_root)
    if src_root not in sys.path:
        sys.path.insert(0, src_root)

    from tools.testing.m3_datalink_remainder_check import verify as verify_dl
    from tools.testing.m3_esm_remainder_check import verify as verify_esm
    from tools.testing.m3_fusion_remainder_check import verify as verify_fus
    from tools.testing.m3_identification_remainder_check import verify as verify_id
    from tools.testing.m3_passive_remainder_check import verify as verify_psv
    from tools.testing.m3_track_remainder_check import verify as verify_trk

    revision = _git_revision()
    sources = {
        "TRK": verify_trk(),
        "ID": verify_id(),
        "PSV": verify_psv(),
        "ESM": verify_esm(),
        "DL": verify_dl(),
        "FUS": verify_fus(),
    }

    source_acceptance = {
        family: _mapping(
            evidence.get("acceptance"),
            field=f"{family}.acceptance",
        )
        for family, evidence in sources.items()
    }
    source_logical = {
        family: _mapping(
            evidence.get("logical_product"),
            field=f"{family}.logical_product",
        )
        for family, evidence in sources.items()
    }
    source_scope = {
        family: _mapping(
            evidence.get("scope"),
            field=f"{family}.scope",
        )
        for family, evidence in sources.items()
    }

    family_codes = {
        family: _strings(
            source_logical[family].get("metric_codes"),
            field=f"{family}.logical_product.metric_codes",
        )
        for family in EXPECTED_CODES
    }
    family_golden_codes = {
        family: tuple(
            sorted(
                _mapping(
                    source_logical[family].get("golden_numeric"),
                    field=f"{family}.logical_product.golden_numeric",
                )
            )
        )
        for family in EXPECTED_CODES
    }
    combined_codes = tuple(
        code
        for family in EXPECTED_CODES
        for code in family_codes[family]
    )

    source_pass = all(
        evidence.get("task_id") == EXPECTED_TASK_IDS[family]
        and evidence.get("status") == "PASS"
        and evidence.get("task_complete") is True
        and evidence.get("implementation_complete") is True
        and evidence.get("source_revision") == revision
        and evidence.get("failed_acceptance") == []
        and bool(source_acceptance[family])
        and all(value is True for value in source_acceptance[family].values())
        for family, evidence in sources.items()
    )
    applicability_exact = all(
        _all_true(source_acceptance[family], APPLICABILITY_CHECKS[family])
        for family in EXPECTED_CODES
    )
    no_fake_observation = all(
        _all_true(source_acceptance[family], NEGATIVE_NO_FAKE_CHECKS[family])
        for family in EXPECTED_CODES
    )

    acceptance = {
        "source_m3_met_003_through_008_exact_head_pass": source_pass,
        "family_membership_exact_48": (
            all(
                family_codes[family] == EXPECTED_CODES[family]
                for family in EXPECTED_CODES
            )
            and len(combined_codes) == 48
            and len(set(combined_codes)) == 48
        ),
        "family_counts_exact": (
            {family: len(codes) for family, codes in family_codes.items()}
            == {"TRK": 7, "ID": 12, "PSV": 7, "ESM": 6, "DL": 8, "FUS": 8}
        ),
        "all_48_golden_outputs_present": all(
            family_golden_codes[family] == tuple(sorted(EXPECTED_CODES[family]))
            for family in EXPECTED_CODES
        ),
        "all_source_golden_negative_acceptance_pass": all(
            all(value is True for value in source_acceptance[family].values())
            for family in EXPECTED_CODES
        ),
        "exact_product_system_applicability_pass": applicability_exact,
        "wrong_product_system_fails_closed_no_fake_observation": (
            no_fake_observation
        ),
        "shared_catalog_engine_only": all(
            source_scope[family].get("shared_catalog_engine") is True
            and source_acceptance[family].get("single_catalog_engine_dispatch") is True
            for family in EXPECTED_CODES
        ),
        "no_persistence_or_publication_in_qualification": all(
            source_scope[family].get("persistence_executed") is False
            and source_scope[family].get("publication_executed") is False
            for family in EXPECTED_CODES
        ),
    }
    failed = sorted(key for key, passed in acceptance.items() if not passed)
    complete = not failed

    logical_product = {
        "family_metric_codes": {
            family: list(family_codes[family])
            for family in EXPECTED_CODES
        },
        "family_counts": {
            family: len(family_codes[family])
            for family in EXPECTED_CODES
        },
        "combined_metric_codes": list(combined_codes),
        "golden_metric_codes": {
            family: list(family_golden_codes[family])
            for family in EXPECTED_CODES
        },
        "applicability_checks": {
            family: list(APPLICABILITY_CHECKS[family])
            for family in EXPECTED_CODES
        },
        "negative_no_fake_observation_checks": {
            family: list(NEGATIVE_NO_FAKE_CHECKS[family])
            for family in EXPECTED_CODES
        },
        "source_task_ids": {
            family: sources[family].get("task_id")
            for family in EXPECTED_CODES
        },
        "source_schemas": {
            family: sources[family].get("schema")
            for family in EXPECTED_CODES
        },
    }

    return {
        "schema": "TPAA_M3_TST_004_PRODUCT_LAYER_GOLDEN_EVIDENCE_V1",
        "task_id": "M3-TST-004",
        "tracking_issue": TRACKING_ISSUE,
        "status": "PASS" if complete else "FAIL",
        "task_complete": complete,
        "implementation_complete": complete,
        "source_revision": revision,
        "logical_product": logical_product,
        "acceptance": acceptance,
        "failed_acceptance": failed,
        "scope": {
            "trk_id_psv_esm_dl_fus_exact_48_executed": True,
            "business_metric_semantics_executed": True,
            "golden_negative_cases_executed": True,
            "exact_product_system_applicability_executed": True,
            "wrong_product_system_no_fake_observation_enforced": True,
            "shared_catalog_metric_engine_only": True,
            "catalog_formulas_modified": False,
            "applicability_modified": False,
            "publication_routes_modified": False,
            "persistence_executed": False,
            "publication_executed": False,
        },
    }


def compare_evidence(
    windows_path: Path,
    linux_path: Path,
    *,
    expected_revision: str,
) -> dict[str, object]:
    windows = _mapping(
        json.loads(windows_path.read_text(encoding="utf-8")),
        field="windows",
    )
    linux = _mapping(
        json.loads(linux_path.read_text(encoding="utf-8")),
        field="linux",
    )
    checks = {
        "schemas_exact": (
            windows.get("schema")
            == linux.get("schema")
            == "TPAA_M3_TST_004_PRODUCT_LAYER_GOLDEN_EVIDENCE_V1"
        ),
        "tasks_exact": (
            windows.get("task_id") == linux.get("task_id") == "M3-TST-004"
        ),
        "statuses_pass": windows.get("status") == linux.get("status") == "PASS",
        "tasks_complete": (
            windows.get("task_complete") is True
            and linux.get("task_complete") is True
        ),
        "implementation_complete": (
            windows.get("implementation_complete") is True
            and linux.get("implementation_complete") is True
        ),
        "revisions_exact": (
            windows.get("source_revision")
            == linux.get("source_revision")
            == expected_revision
        ),
        "logical_product_equal": (
            windows.get("logical_product") == linux.get("logical_product")
        ),
        "acceptance_equal": windows.get("acceptance") == linux.get("acceptance"),
        "scope_equal": windows.get("scope") == linux.get("scope"),
        "failed_acceptance_empty": (
            windows.get("failed_acceptance") == []
            and linux.get("failed_acceptance") == []
        ),
    }
    failed = sorted(key for key, passed in checks.items() if not passed)
    complete = not failed
    return {
        "schema": (
            "TPAA_M3_TST_004_PRODUCT_LAYER_GOLDEN_"
            "CROSS_PLATFORM_EVIDENCE_V1"
        ),
        "task_id": "M3-TST-004",
        "tracking_issue": TRACKING_ISSUE,
        "status": "PASS" if complete else "FAIL",
        "task_complete": complete,
        "implementation_complete": complete,
        "source_revision": expected_revision,
        "windows_source_revision": windows.get("source_revision"),
        "linux_source_revision": linux.get("source_revision"),
        "logical_product": windows.get("logical_product"),
        "scope": windows.get("scope"),
        "checks": checks,
        "failed_acceptance": failed,
    }


def _write(payload: dict[str, object], path: Path | None) -> None:
    rendered = json.dumps(payload, indent=2, sort_keys=True) + "\n"
    print(rendered, end="")
    if path is not None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(rendered, encoding="utf-8", newline="\n")


def main() -> int:
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="mode", required=True)
    check = sub.add_parser("check")
    check.add_argument("--evidence", type=Path)
    compare = sub.add_parser("compare")
    compare.add_argument("--windows", type=Path, required=True)
    compare.add_argument("--linux", type=Path, required=True)
    compare.add_argument("--expected-revision", required=True)
    compare.add_argument("--evidence", type=Path, required=True)
    args = parser.parse_args()

    try:
        if args.mode == "check":
            payload = verify()
        else:
            payload = compare_evidence(
                args.windows,
                args.linux,
                expected_revision=args.expected_revision,
            )
        evidence = args.evidence
        code = 0 if payload["status"] == "PASS" else 2
    except Exception as exc:
        payload = {
            "schema": "TPAA_M3_TST_004_PRODUCT_LAYER_GOLDEN_EVIDENCE_V1",
            "task_id": "M3-TST-004",
            "tracking_issue": TRACKING_ISSUE,
            "status": "FAIL",
            "task_complete": False,
            "implementation_complete": False,
            "source_revision": _git_revision(),
            "error": f"{type(exc).__name__}: {exc}",
        }
        evidence = getattr(args, "evidence", None)
        code = 2
    _write(payload, evidence)
    return code


if __name__ == "__main__":
    raise SystemExit(main())
