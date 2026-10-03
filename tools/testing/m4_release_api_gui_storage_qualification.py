#!/usr/bin/env python3
"""M4-TST-005 cross-platform + storage qualification aggregator."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import cast

TRACKING_ISSUE = 129
TASK_ID = "M4-TST-005"
PLATFORM_SCHEMA = "TPAA_M4_TST_005_PLATFORM_EVIDENCE_V1"
CROSS_SCHEMA = "TPAA_M4_TST_005_CROSS_PLATFORM_EVIDENCE_V1"
QUAL_SCHEMA = "TPAA_M4_TST_005_STORAGE_QUALIFICATION_V1"
STORAGE_SCHEMA = "TPAA_M4_TST_005_STORAGE_PARITY_V1"

SOURCE_FILES = {
    "batch1": ("m4-batch-1", "longitudinal-sample.json"),
    "batch2": ("m4-batch-2", "trend-release.json"),
    "batch3": ("m4-batch-3", "api-gui-debrief.json"),
    "tst004": ("m4-tst-004", "coverage.json"),
}
EXPECTED_GROUP_TASKS = {
    "batch1": (
        "M4-GOV-001","M4-GOV-002","M4-LONG-001","M4-LONG-002","M4-LONG-003","M4-TST-001"
    ),
    "batch2": (
        "M4-LONG-004","M4-LONG-005","M4-OBS-001","M4-OBS-002","M4-OBS-003","M4-TST-002"
    ),
    "batch3": (
        "M4-API-001","M4-API-002","M4-GUI-001","M4-GUI-002","M4-GUI-003","M4-TST-003"
    ),
    "tst004": ("M4-TST-004",),
}
PRE_TST005_TASKS = tuple(
    task for key in ("batch1","batch2","batch3","tst004")
    for task in EXPECTED_GROUP_TASKS[key]
)


def _load(path: Path) -> dict[str, object]:
    raw: object = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(raw, dict):
        raise ValueError(f"{path}: root must be object")
    return cast(dict[str, object], raw)


def _hash_bytes(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _hash(value: object) -> str:
    return hashlib.sha256(
        json.dumps(value,sort_keys=True,separators=(",",":"),ensure_ascii=True,allow_nan=False).encode("ascii")
    ).hexdigest()


def _group_tasks(payload: dict[str, object]) -> tuple[str, ...]:
    if isinstance(payload.get("task_ids"), list):
        return tuple(str(x) for x in cast(list[object], payload["task_ids"]))
    if isinstance(payload.get("task_id"), str):
        return (cast(str, payload["task_id"]),)
    return ()


def _all_acceptance(payload: dict[str, object]) -> bool:
    acceptance = payload.get("acceptance")
    return (
        isinstance(acceptance, dict)
        and bool(acceptance)
        and all(value is True for value in acceptance.values())
    )


def check_platform(
    *,
    evidence_root: Path,
    platform: str,
    expected_revision: str,
) -> dict[str, object]:
    if platform not in {"windows","linux"}:
        raise ValueError("platform must be windows or linux")
    if len(expected_revision) != 40:
        raise ValueError("expected_revision must be exact SHA")

    sources: dict[str, dict[str, object]] = {}
    paths: dict[str, Path] = {}
    for key,(directory,filename) in SOURCE_FILES.items():
        path=evidence_root/directory/platform/filename
        paths[key]=path
        sources[key]=_load(path)

    source_pass = all(
        payload.get("status") == "PASS"
        and payload.get("implementation_complete") is True
        and payload.get("source_revision") == expected_revision
        and payload.get("failed_acceptance") == []
        and _all_acceptance(payload)
        and _group_tasks(payload) == EXPECTED_GROUP_TASKS[key]
        for key,payload in sources.items()
    )
    source_task_ids = tuple(
        task for key in ("batch1","batch2","batch3","tst004")
        for task in _group_tasks(sources[key])
    )
    coverage = cast(dict[str, object], sources["tst004"]["logical_product"])
    eligible = cast(list[object], coverage["eligible"])
    excluded = cast(list[object], coverage["excluded"])

    task_evidence_hashes: dict[str,str] = {}
    for key in ("batch1","batch2","batch3","tst004"):
        digest=_hash_bytes(paths[key])
        for task in EXPECTED_GROUP_TASKS[key]:
            task_evidence_hashes[task]=digest

    acceptance = {
        "all_source_evidence_exact_head_pass": source_pass,
        "source_task_inventory_exact_19": source_task_ids == PRE_TST005_TASKS,
        "eligible_exact_104": len(eligible) == 104,
        "excluded_exact_12": len(excluded) == 12,
        "batch2_release_replay_trend_qualified": _all_acceptance(sources["batch2"]),
        "batch3_api_gui_debrief_annotation_qualified": _all_acceptance(sources["batch3"]),
        "no_shadow_schema": all(
            isinstance(payload.get("scope"),dict)
            and cast(dict[str,object],payload["scope"]).get("shadow_schema_created") is False
            for payload in sources.values()
        ),
        "p4_p5_inactive": all(
            cast(dict[str,object],payload.get("scope",{})).get(
                "p4_p5_human_team_assessment_active"
            ) is False
            for payload in sources.values()
        ),
        "m5_qualification_not_claimed": all(
            cast(dict[str,object],payload.get("scope",{})).get(
                "m5_formal_product_qualification_claimed"
            ) is False
            for payload in sources.values()
        ),
    }
    failed=sorted(k for k,v in acceptance.items() if v is not True)
    logical_product={
        "platform":platform,
        "source_task_ids":list(source_task_ids),
        "task_evidence_hashes":task_evidence_hashes,
        "source_logical_hashes":{
            key:_hash(payload.get("logical_product")) for key,payload in sources.items()
        },
        "eligible_codes":[cast(dict[str,object],row)["metric_code"] for row in eligible],
        "excluded_codes":[cast(dict[str,object],row)["metric_code"] for row in excluded],
    }
    return {
        "schema":PLATFORM_SCHEMA,
        "task_id":TASK_ID,
        "tracking_issue":TRACKING_ISSUE,
        "status":"PASS" if not failed else "FAIL",
        "implementation_complete":not failed,
        "task_complete":False,
        "completion_gate":"EXACT_HEAD_AND_PROTECTED_MAIN_HOSTED_CI_REQUIRED",
        "source_revision":expected_revision,
        "logical_product":logical_product,
        "acceptance":acceptance,
        "failed_acceptance":failed,
    }


def compare_platform(
    windows_path: Path,
    linux_path: Path,
    *,
    expected_revision: str,
) -> dict[str, object]:
    windows = _load(windows_path)
    linux = _load(linux_path)
    windows_product = cast(
        dict[str, object],
        windows.get("logical_product", {}),
    )
    linux_product = cast(
        dict[str, object],
        linux.get("logical_product", {}),
    )
    windows_stable = dict(windows_product)
    linux_stable = dict(linux_product)
    windows_stable.pop("platform", None)
    linux_stable.pop("platform", None)
    checks={
        "schemas_exact":windows.get("schema")==linux.get("schema")==PLATFORM_SCHEMA,
        "statuses_pass":windows.get("status")==linux.get("status")=="PASS",
        "implementation_complete":windows.get("implementation_complete") is True and linux.get("implementation_complete") is True,
        "revisions_exact":windows.get("source_revision")==linux.get("source_revision")==expected_revision,
        "logical_product_equal":windows_stable == linux_stable,
        "acceptance_equal":windows.get("acceptance")==linux.get("acceptance"),
        "failed_acceptance_empty":windows.get("failed_acceptance")==[] and linux.get("failed_acceptance")==[],
    }
    failed=sorted(k for k,v in checks.items() if v is not True)
    return {
        "schema":CROSS_SCHEMA,
        "task_id":TASK_ID,
        "tracking_issue":TRACKING_ISSUE,
        "status":"PASS" if not failed else "FAIL",
        "implementation_complete":not failed,
        "task_complete":False,
        "source_revision":expected_revision,
        "logical_product": windows_stable,
        "checks":checks,
        "failed_acceptance":failed,
    }


def qualify(
    *,
    cross_path: Path,
    storage_path: Path,
    expected_revision: str,
) -> dict[str, object]:
    cross = _load(cross_path)
    storage = _load(storage_path)
    cp = cast(dict[str, object], cross.get("logical_product", {}))
    source_tasks=tuple(str(x) for x in cast(list[object],cp.get("source_task_ids",[])))
    storage_accept=cast(dict[str,object],storage.get("acceptance",{}))
    eligible=tuple(str(x) for x in cast(list[object],cp.get("eligible_codes",[])))
    excluded=tuple(str(x) for x in cast(list[object],cp.get("excluded_codes",[])))
    acceptance={
        "windows_linux_logical_equivalence_pass":(
            cross.get("schema")==CROSS_SCHEMA
            and cross.get("status")=="PASS"
            and cross.get("implementation_complete") is True
            and cross.get("source_revision")==expected_revision
            and cross.get("failed_acceptance")==[]
        ),
        "sqlite_postgresql_longitudinal_membership_parity_pass":(
            storage.get("schema")==STORAGE_SCHEMA
            and storage.get("status")=="PASS"
            and storage.get("implementation_complete") is True
            and storage.get("source_revision")==expected_revision
            and storage.get("failed_acceptance")==[]
            and bool(storage_accept)
            and all(v is True for v in storage_accept.values())
        ),
        "single_candidate_sha_exact":cross.get("source_revision")==storage.get("source_revision")==expected_revision,
        "source_task_inventory_exact_19":source_tasks==PRE_TST005_TASKS,
        "exact_104_12_preserved":len(eligible)==104 and len(set(eligible))==104 and len(excluded)==12 and len(set(excluded))==12,
        "release_history_replay_api_gui_debrief_annotation_qualified":cast(dict[str,object],cross.get("checks",{})).get("failed_acceptance_empty") is True,
    }
    failed=sorted(k for k,v in acceptance.items() if v is not True)
    task_hashes=cast(dict[str,object],cp.get("task_evidence_hashes",{}))
    logical_product={
        "qualified_task_ids":[*source_tasks,TASK_ID],
        "task_evidence_hashes":task_hashes,
        "eligible_codes":list(eligible),
        "excluded_codes":list(excluded),
        "cross_platform_logical_hash":_hash(cp),
        "storage_membership_hash":storage.get("membership_hash"),
        "storage_release_id":storage.get("longitudinal_release_id"),
    }
    return {
        "schema":QUAL_SCHEMA,
        "task_id":TASK_ID,
        "tracking_issue":TRACKING_ISSUE,
        "status":"PASS" if not failed else "FAIL",
        "implementation_complete":not failed,
        "task_complete":False,
        "completion_gate":"EXACT_HEAD_AND_PROTECTED_MAIN_HOSTED_CI_REQUIRED",
        "source_revision":expected_revision,
        "logical_product":logical_product,
        "acceptance":acceptance,
        "failed_acceptance":failed,
        "scope":{
            "db_schema_version":"1.7.0",
            "shadow_schema_created":False,
            "windows_linux_logical_equivalence":True,
            "sqlite_postgresql_longitudinal_release_membership_parity":True,
            "historical_current_latest_fallback":False,
            "p4_p5_human_team_assessment_active":False,
            "m5_formal_product_qualification_claimed":False,
        },
    }


def _write(payload: dict[str,object], path: Path) -> int:
    rendered=json.dumps(payload,indent=2,sort_keys=True,allow_nan=False)+"\n"
    path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(rendered,encoding="utf-8",newline="\n")
    print(rendered,end="")
    return 0 if payload["status"]=="PASS" else 2


def main() -> int:
    parser=argparse.ArgumentParser()
    sub=parser.add_subparsers(dest="mode",required=True)
    check=sub.add_parser("check")
    check.add_argument("--evidence-root",type=Path,required=True)
    check.add_argument("--platform",required=True)
    check.add_argument("--expected-revision",required=True)
    check.add_argument("--evidence",type=Path,required=True)
    compare=sub.add_parser("compare")
    compare.add_argument("--windows",type=Path,required=True)
    compare.add_argument("--linux",type=Path,required=True)
    compare.add_argument("--expected-revision",required=True)
    compare.add_argument("--evidence",type=Path,required=True)
    final=sub.add_parser("qualify")
    final.add_argument("--cross-platform",type=Path,required=True)
    final.add_argument("--storage",type=Path,required=True)
    final.add_argument("--expected-revision",required=True)
    final.add_argument("--evidence",type=Path,required=True)
    args=parser.parse_args()
    try:
        if args.mode=="check":
            payload=check_platform(evidence_root=args.evidence_root,platform=args.platform,expected_revision=args.expected_revision)
        elif args.mode=="compare":
            payload=compare_platform(args.windows,args.linux,expected_revision=args.expected_revision)
        else:
            payload=qualify(cross_path=args.cross_platform,storage_path=args.storage,expected_revision=args.expected_revision)
    except Exception as exc:
        payload={
            "schema":QUAL_SCHEMA,"task_id":TASK_ID,"tracking_issue":TRACKING_ISSUE,
            "status":"FAIL","implementation_complete":False,"task_complete":False,
            "source_revision":getattr(args,"expected_revision","UNKNOWN"),
            "error":f"{type(exc).__name__}: {exc}",
        }
    return _write(payload,args.evidence)


if __name__=="__main__":
    raise SystemExit(main())
