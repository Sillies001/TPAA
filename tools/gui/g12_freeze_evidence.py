#!/usr/bin/env python3
"""Record the G12 design-freeze decision: W9 stays NO_GO until external doors close."""

from __future__ import annotations

import hashlib
import json
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools.baseline.adopt_g12_successor import check_successor  # noqa: E402
from tools.gui.remediation_guard import (  # noqa: E402
    RemediationGuardError,
    require_reclosure_ready,
)

BASELINE = ROOT / "baseline" / "CB-1.17.0"
MATRIX = ROOT / "evidence" / "gui-g12-v33-visual-matrix.json"
EVIDENCE = ROOT / "evidence" / "gui-g12-v33-freeze.json"

EXPECTED_CAPTURES = 156
PREREQUISITE_PHASES = tuple(f"G{index}" for index in range(6, 12))


class G12FreezeError(RuntimeError):
    pass


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _write(payload: dict[str, object]) -> None:
    EVIDENCE.parent.mkdir(parents=True, exist_ok=True)
    content = json.dumps(payload, ensure_ascii=False, indent=2) + "\n"
    with tempfile.NamedTemporaryFile(
        "w", encoding="utf-8", newline="\n", delete=False, dir=EVIDENCE.parent
    ) as temporary:
        temporary.write(content)
        candidate = Path(temporary.name)
    candidate.replace(EVIDENCE)


def record() -> dict[str, object]:
    require_reclosure_ready("G12")
    check_successor()
    for phase in PREREQUISITE_PHASES:
        evidence = ROOT / "evidence" / f"gui-{phase.lower()}-v33-closure.json"
        phase_payload = json.loads(evidence.read_text(encoding="utf-8"))
        if phase_payload.get("phase_status") != "CLOSED_LOCAL_WITH_GATES":
            raise G12FreezeError(f"prerequisite phase is not closed: {phase}")
    if not MATRIX.is_file():
        raise G12FreezeError("missing full visual matrix evidence")
    matrix = json.loads(MATRIX.read_text(encoding="utf-8"))
    captures = matrix.get("captures")
    if matrix.get("status") != "AUTOMATED_STRUCTURAL_PASS" or not isinstance(captures, list):
        raise G12FreezeError("visual matrix is not an automated structural PASS")
    if len(captures) != EXPECTED_CAPTURES:
        raise G12FreezeError(f"expected {EXPECTED_CAPTURES} captures, got {len(captures)}")
    views = {str(c.get("view")) for c in captures if isinstance(c, dict)}
    if views != {f"V{index:02d}" for index in range(1, 27)}:
        raise G12FreezeError(f"view coverage drifted: {sorted(views)}")
    for capture in captures:
        box = capture.get("box_model")
        if not isinstance(box, dict) or box.get("overlapCount") != 0 or box.get("overflow") is not False:
            raise G12FreezeError(f"box model overlap/overflow: {capture!r}")
        file_value = capture.get("file")
        sha_value = capture.get("sha256")
        if not isinstance(file_value, str) or not isinstance(sha_value, str):
            raise G12FreezeError("capture missing file/sha256")
        path = ROOT / file_value
        if not path.is_file() or _sha(path) != sha_value:
            raise G12FreezeError(f"capture drift: {file_value}")
    w9 = json.loads(
        (BASELINE / "canonical" / "W9_REAGGREGATION.json").read_text(encoding="utf-8")
    )
    if w9.get("product_complete") is not True:
        raise G12FreezeError("PRODUCT_COMPLETE eligibility has not been established")
    payload: dict[str, object] = {
        "schema": "TPAA_G12_V33_DESIGN_FREEZE_EVIDENCE_V1",
        "phase": "G12",
        "phase_status": "IN_PROGRESS_EXTERNAL_DOORS_OPEN",
        "recorded_at": "2026-11-07",
        "core_baseline": "CB-1.17.0",
        "parent_core_baseline": "CB-1.16.0",
        "baseline_lock_sha256": _sha(BASELINE / "BASELINE_LOCK.json"),
        "visual_matrix": {
            "views": 26,
            "captures": EXPECTED_CAPTURES,
            "status": "AUTOMATED_STRUCTURAL_PASS",
        },
        "w9": {
            "status": w9.get("w9_status"),
            "product_complete": w9.get("product_complete"),
            "release_ready": w9.get("release_ready"),
            "external_doors_open": w9.get("external_doors_open"),
        },
        "delivered": [
            "CB-1.17.0 设计冻结后继（路由 103 冻结；G12_DESIGN_FREEZE_AUTHORITY）",
            "26 视图 x 3 主题 x Ribbon 两态 全量视觉矩阵（盒模型无重叠，逐帧 sha256）",
            "W9 重新聚合记录（NO_GO，外部门清单固化）",
        ],
        "remaining_external_doors": w9.get("external_doors_open"),
        "restrictions": {"push": False, "production_deployment": False, "release_claim": False},
    }
    _write(payload)
    return payload


def main() -> int:
    try:
        result = record()
    except (OSError, ValueError, KeyError, G12FreezeError, RemediationGuardError) as exc:
        print(f"G12_FREEZE_FAIL {exc}")
        return 2
    matrix = result["visual_matrix"]
    w9 = result["w9"]
    assert isinstance(matrix, dict) and isinstance(w9, dict)
    print(
        "G12_FREEZE_RECORDED "
        f"status={result['phase_status']} captures={matrix['captures']} w9={w9['status']}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
