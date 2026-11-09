#!/usr/bin/env python3
"""Generate Python/TypeScript DTOs and documentation from CB-1.18.0 task metrics."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any

from tpaa_canonical.byte_stability import write_utf8_lf
from tpaa_canonical.loader import F1_CANDIDATE_CORE_BASELINE, trusted_loader_for_baseline

ROOT = Path(__file__).resolve().parents[2]
CANDIDATE_ROOT = ROOT / "baseline" / F1_CANDIDATE_CORE_BASELINE
METRIC_IDS = ("KILL_RATIO", "EXCHANGE_RATIO", "MISSION_COMPLETION_RATE")
PYTHON_OUTPUT = "src/tpaa_generated/task_metric_dto.py"
TYPESCRIPT_OUTPUT = "frontend/gui-v33/src/generated/task-metrics.ts"
MARKDOWN_OUTPUT = "docs/metric-definitions/TASK_METRICS.md"
MANIFEST_OUTPUT = "generated/task-metrics/manifest.json"
ALLOWED_ADMISSION = {
    "CANDIDATE_TEST_ONLY",
    "CANDIDATE_AWAITING_BUSINESS_APPROVAL",
}


class CodegenError(RuntimeError):
    """Task metric authority or generated output is inconsistent."""


def _canonical_hash(value: dict[str, Any]) -> str:
    canonical = json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(canonical).hexdigest()


def _load_definitions() -> tuple[dict[str, Any], ...]:
    loader = trusted_loader_for_baseline(CANDIDATE_ROOT)
    definitions = tuple(dict(loader.load(metric_id).payload) for metric_id in METRIC_IDS)
    for metric_id, definition in zip(METRIC_IDS, definitions, strict=True):
        if definition.get("semantic_id") != metric_id:
            raise CodegenError(f"{metric_id} semantic identity mismatch")
        declared_hash = definition.get("definition_sha256")
        if not isinstance(declared_hash, str):
            raise CodegenError(f"{metric_id} definition_sha256 is missing")
        payload = {key: value for key, value in definition.items() if key != "definition_sha256"}
        if _canonical_hash(payload) != declared_hash:
            raise CodegenError(f"{metric_id} definition self-hash mismatch")
        if definition.get("admission_status") not in ALLOWED_ADMISSION:
            raise CodegenError(f"{metric_id} has an unsupported admission status")
    return definitions


def _render_python() -> str:
    return '''"""Generated task-level Assessment Metric DTO contracts; do not edit."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal, Mapping

TaskMetricStatus = Literal[
    "READY", "PENDING", "N_A", "INSUFFICIENT", "INVALID", "ERROR", "INCOMPARABLE"
]
TaskMetricAdmissionStatus = Literal[
    "CANDIDATE_TEST_ONLY", "CANDIDATE_AWAITING_BUSINESS_APPROVAL", "ADMITTED", "RETIRED"
]


@dataclass(frozen=True, slots=True)
class TaskMetricDefinitionDTO:
    semantic_id: str
    definition_version: str
    definition_sha256: str
    name_zh: str
    name_en: str
    value_kind: str
    unit: str
    direction: str
    applicable_training_types: tuple[str, ...]
    admission_status: TaskMetricAdmissionStatus
    display_decimal_places: int


@dataclass(frozen=True, slots=True)
class TaskMetricResultDTO:
    result_id: str
    semantic_id: str
    definition_version: str
    definition_sha256: str
    batch_id: str
    session_id: str
    release_id: str
    context_id: str
    evaluated_side: str
    numerator: str | None
    denominator: str | None
    value: str | None
    status: TaskMetricStatus
    reason_codes: tuple[str, ...]
    coverage: float
    j_state: str
    source_refs: tuple[Mapping[str, object], ...]
    evidence_refs: tuple[Mapping[str, object], ...]
    computed_at: str
    algorithm_contract_sha256: str


@dataclass(frozen=True, slots=True)
class TaskMetricCompareRequestDTO:
    semantic_id: str
    definition_version: str
    batch_scopes: tuple[Mapping[str, str], ...]
    evaluated_side: str
    phase_scope: str
    start_session_time_us: str
    end_session_time_us: str


@dataclass(frozen=True, slots=True)
class TaskMetricEvidenceDTO:
    semantic_id: str
    definition_sha256: str
    source_refs: tuple[Mapping[str, object], ...]
    evidence_refs: tuple[Mapping[str, object], ...]
    scope_hash: str
    result_sha256: str
'''


def _render_typescript() -> str:
    return '''/* Generated from Canonical CB-1.18.0-candidate; do not edit. */

export type DecimalString = string;
export type TaskMetricStatus =
  | "READY"
  | "PENDING"
  | "N_A"
  | "INSUFFICIENT"
  | "INVALID"
  | "ERROR"
  | "INCOMPARABLE";

export type TaskMetricAdmissionStatus =
  | "CANDIDATE_TEST_ONLY"
  | "CANDIDATE_AWAITING_BUSINESS_APPROVAL"
  | "ADMITTED"
  | "RETIRED";

export interface TaskMetricDefinitionDTO {
  semantic_id: string;
  definition_version: string;
  definition_sha256: string;
  name_zh: string;
  name_en: string;
  value_kind: string;
  unit: string;
  direction: string;
  applicable_training_types: readonly string[];
  admission_status: TaskMetricAdmissionStatus;
  display_decimal_places: number;
}

export interface TaskMetricResultDTO {
  result_id: string;
  semantic_id: string;
  definition_version: string;
  definition_sha256: string;
  batch_id: string;
  session_id: string;
  release_id: string;
  context_id: string;
  evaluated_side: "RED" | "BLUE";
  numerator: DecimalString | null;
  denominator: DecimalString | null;
  value: DecimalString | null;
  status: TaskMetricStatus;
  reason_codes: readonly string[];
  coverage: number;
  j_state: string;
  source_refs: readonly Readonly<Record<string, unknown>>[];
  evidence_refs: readonly Readonly<Record<string, unknown>>[];
  computed_at: string;
  algorithm_contract_sha256: string;
}

export interface ExactBatchScopeDTO {
  batch_id: string;
  session_id: string;
  release_id: string;
  context_id: string;
}

export interface TaskMetricCompareRequestDTO {
  semantic_id: string;
  definition_version: string;
  batch_scopes: readonly ExactBatchScopeDTO[];
  evaluated_side: "RED" | "BLUE";
  phase_scope: string;
  start_session_time_us: DecimalString;
  end_session_time_us: DecimalString;
}

export interface TaskMetricEvidenceDTO {
  semantic_id: string;
  definition_sha256: string;
  source_refs: readonly Readonly<Record<string, unknown>>[];
  evidence_refs: readonly Readonly<Record<string, unknown>>[];
  scope_hash: string;
  result_sha256: string;
}
'''


def _render_markdown(definitions: tuple[dict[str, Any], ...]) -> str:
    lines = [
        "# 任务评估指标候选定义",
        "",
        "> 本文由 Canonical 自动生成。当前三个定义均为候选口径，不构成业务批准、正式裁决或发布声明。",
        "",
        "| 指标 | 候选版本 | 适用训练 | 状态 |",
        "|---|---|---|---|",
    ]
    for item in definitions:
        training = "、".join(str(value) for value in item["applicable_training_types"])
        lines.append(
            f"| {item['name_zh']}（{item['semantic_id']}） | "
            f"{item['definition_version']} | {training} | {item['admission_status']} |"
        )
    lines.extend(
        [
            "",
            "## 口径冻结约束",
            "",
            "- **击落比**：分子是对手方最终确认损失的唯一 loss_id；分母是符合准入条件的唯一 BVR/WVR 交战事件。发射次数不是分母。",
            "- **交换比**：分子是对手方最终确认损失数，分母是评价方最终确认损失数。评价方零损失时结果为 N_A，不得输出 infinity。",
            "- **任务完成率**：只统计任务开始时冻结的 required objective plan；分子是已最终确认完成的 required objective，分母是有效 required objective。optional objective 不进入分母。",
            "- **去重**：同一损失即使关联多个 Weapon Event 或证据引用，也只能按一个 loss_id 计一次。",
            "- **J 状态**：pending/unknown 不得按失败或 0 处理；冲突必须显式返回 INVALID。",
            "- **跨批次聚合**：先合计分子和分母，再计算比值；禁止对各批次 ratio 做简单算术平均。",
            "- **范围**：每个结果绑定精确 batch/session/release/context/evaluated_side/phase/time window；禁止 latest 回退和跨批次借数。",
            "- **独立性**：这三项属于 Assessment Metric authority，不修改、不冒充 P1 116 项指标。",
            "",
        ]
    )
    return "\n".join(lines)


def _render_outputs() -> dict[str, bytes]:
    definitions = _load_definitions()
    loader = trusted_loader_for_baseline(CANDIDATE_ROOT)
    base_outputs = {
        PYTHON_OUTPUT: _render_python().encode("utf-8"),
        TYPESCRIPT_OUTPUT: _render_typescript().encode("utf-8"),
        MARKDOWN_OUTPUT: _render_markdown(definitions).encode("utf-8"),
    }
    manifest = {
        "schema": "TPAA_TASK_METRIC_CODEGEN_MANIFEST_V1",
        "source_core_baseline": F1_CANDIDATE_CORE_BASELINE,
        "source_baseline_lock_sha256": loader.trusted_lock_sha256,
        "definitions": [
            {
                "semantic_id": item["semantic_id"],
                "definition_version": item["definition_version"],
                "definition_sha256": item["definition_sha256"],
                "admission_status": item["admission_status"],
            }
            for item in definitions
        ],
        "outputs": {
            path: hashlib.sha256(content).hexdigest()
            for path, content in sorted(base_outputs.items())
        },
        "business_approval": "REQUIRED",
        "release_claim": False,
    }
    base_outputs[MANIFEST_OUTPUT] = (
        json.dumps(manifest, ensure_ascii=False, sort_keys=True, indent=2) + "\n"
    ).encode("utf-8")
    return base_outputs


def check() -> None:
    for relative_path, expected in _render_outputs().items():
        path = ROOT / relative_path
        if not path.is_file():
            raise CodegenError(f"missing generated output: {relative_path}")
        if path.read_bytes() != expected:
            raise CodegenError(f"generated output drift: {relative_path}")


def write() -> None:
    for relative_path, content in _render_outputs().items():
        write_utf8_lf(ROOT / relative_path, content.decode("utf-8"))


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--check", action="store_true")
    group.add_argument("--write", action="store_true")
    args = parser.parse_args()
    if args.check:
        check()
    else:
        write()
    print("TASK_METRIC_CODEGEN_PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
