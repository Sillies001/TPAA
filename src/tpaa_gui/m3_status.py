"""M3 status and Evidence presentation over immutable Release projections.

This module is presentation-only. It validates and formats already-projected
workspace and Evidence payloads; it never resolves applicability, recomputes a
Metric, reads persistence, or substitutes current/latest state for a Release ID.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import cast

M3_GUI_RESULT_STATUSES = frozenset(
    {"VALID", "N_A", "INSUFFICIENT_DATA", "INVALID", "REVIEW_REQUIRED"}
)
M3_GUI_STATUS_STYLES = {
    "VALID": "QLabel { border: 1px solid; padding: 4px; }",
    "N_A": "QLabel { border: 2px dashed; padding: 4px; }",
    "INSUFFICIENT_DATA": "QLabel { border: 2px dotted; padding: 4px; }",
    "INVALID": "QLabel { border: 3px solid; padding: 4px; font-weight: bold; }",
    "REVIEW_REQUIRED": "QLabel { border: 3px double; padding: 4px; }",
    "NOT_APPLICABLE": (
        "QLabel { border: 2px groove; padding: 4px; font-style: italic; }"
    ),
    "MIXED_RESULT_STATES": (
        "QLabel { border: 2px solid; padding: 4px; font-style: italic; }"
    ),
    "SYSTEM_ERROR": (
        "QLabel { border: 4px double; padding: 4px; font-weight: bold; }"
    ),
}


class M3StatusPresentationError(RuntimeError):
    """Fail-closed M3 presentation-contract error."""


@dataclass(frozen=True)
class M3MetricStatusPresentation:
    release_id: str
    metric_code: str
    family_code: str
    applicable: bool
    kind: str
    label: str
    reason_codes: tuple[str, ...]
    result_statuses: tuple[str, ...]
    system_type: str | None
    style_sheet: str

    def projection(self) -> dict[str, object]:
        return {
            "release_id": self.release_id,
            "metric_code": self.metric_code,
            "family_code": self.family_code,
            "applicable": self.applicable,
            "kind": self.kind,
            "label": self.label,
            "reason_codes": list(self.reason_codes),
            "result_statuses": list(self.result_statuses),
            "system_type": self.system_type,
            "style_sheet": self.style_sheet,
        }


@dataclass(frozen=True)
class M3EvidenceDrilldown:
    release_id: str
    metric_code: str
    definition_hash: str
    execution_record_hash: str
    evidence_hash: str
    payload: Mapping[str, object]
    manifest_hash: str
    provenance_hash: str

    def projection(self) -> dict[str, object]:
        return {
            "release_id": self.release_id,
            "metric_code": self.metric_code,
            "definition_hash": self.definition_hash,
            "execution_record_hash": self.execution_record_hash,
            "evidence_hash": self.evidence_hash,
            "payload": dict(self.payload),
            "release_provenance": {
                "manifest_hash": self.manifest_hash,
                "provenance_hash": self.provenance_hash,
            },
        }


def _text(value: object, *, field: str) -> str:
    if not isinstance(value, str) or not value:
        raise M3StatusPresentationError(f"M3_GUI_STATUS_FIELD_INVALID:{field}")
    return value


def _hash(value: object, *, field: str) -> str:
    result = _text(value, field=field)
    if len(result) != 64:
        raise M3StatusPresentationError(f"M3_GUI_STATUS_HASH_INVALID:{field}")
    return result


def _mapping(value: object, *, field: str) -> Mapping[str, object]:
    if not isinstance(value, Mapping):
        raise M3StatusPresentationError(f"M3_GUI_STATUS_MAPPING_INVALID:{field}")
    return cast(Mapping[str, object], value)


def _string_tuple(
    value: object,
    *,
    field: str,
    required: bool = False,
) -> tuple[str, ...]:
    if not isinstance(value, list) or not all(
        isinstance(item, str) and item for item in value
    ):
        raise M3StatusPresentationError(
            f"M3_GUI_STATUS_REASON_CODES_INVALID:{field}"
        )
    result = tuple(cast(list[str], value))
    if required and not result:
        raise M3StatusPresentationError(
            f"M3_GUI_STATUS_REASON_CODES_REQUIRED:{field}"
        )
    return result


def build_m3_metric_status_presentations(
    workspace_projection: Mapping[str, object],
    *,
    expected_release_id: str,
) -> tuple[M3MetricStatusPresentation, ...]:
    """Preserve projected applicability/result states without recomputation."""

    release_id = _text(workspace_projection.get("release_id"), field="release_id")
    if release_id != expected_release_id:
        raise M3StatusPresentationError(
            f"M3_GUI_STATUS_RELEASE_MISMATCH:{expected_release_id}:{release_id}"
        )
    raw_metrics = workspace_projection.get("metrics")
    if not isinstance(raw_metrics, list) or len(raw_metrics) != 116:
        raise M3StatusPresentationError("M3_GUI_STATUS_METRIC_MEMBERSHIP_INVALID")

    presentations: list[M3MetricStatusPresentation] = []
    for index, raw_metric in enumerate(raw_metrics):
        metric = _mapping(raw_metric, field=f"metrics[{index}]")
        metric_release_id = _text(
            metric.get("release_id"),
            field=f"metrics[{index}].release_id",
        )
        if metric_release_id != release_id:
            raise M3StatusPresentationError(
                f"M3_GUI_STATUS_METRIC_RELEASE_DRIFT:{index}"
            )
        metric_code = _text(
            metric.get("metric_code"),
            field=f"metrics[{index}].metric_code",
        )
        family_code = _text(
            metric.get("family_code"),
            field=f"metrics[{index}].family_code",
        )
        applicability = _mapping(
            metric.get("applicability"),
            field=f"metrics[{index}].applicability",
        )
        applicable = applicability.get("applicable")
        if not isinstance(applicable, bool):
            raise M3StatusPresentationError(
                f"M3_GUI_STATUS_APPLICABILITY_INVALID:{metric_code}"
            )
        applicability_reasons = _string_tuple(
            applicability.get("reason_codes"),
            field=f"{metric_code}.applicability.reason_codes",
            required=not applicable,
        )
        system_type_value = applicability.get("system_type")
        system_type = (
            None
            if system_type_value is None
            else _text(
                system_type_value,
                field=f"{metric_code}.applicability.system_type",
            )
        )
        raw_instances = metric.get("instances")
        if not isinstance(raw_instances, list):
            raise M3StatusPresentationError(
                f"M3_GUI_STATUS_INSTANCES_INVALID:{metric_code}"
            )

        if not applicable:
            if raw_instances:
                raise M3StatusPresentationError(
                    f"M3_GUI_STATUS_NOT_APPLICABLE_INSTANCES_PRESENT:{metric_code}"
                )
            kind = "NOT_APPLICABLE"
            presentations.append(
                M3MetricStatusPresentation(
                    release_id=release_id,
                    metric_code=metric_code,
                    family_code=family_code,
                    applicable=False,
                    kind=kind,
                    label="NOT_APPLICABLE",
                    reason_codes=applicability_reasons,
                    result_statuses=(),
                    system_type=system_type,
                    style_sheet=M3_GUI_STATUS_STYLES[kind],
                )
            )
            continue

        if not raw_instances:
            raise M3StatusPresentationError(
                f"M3_GUI_STATUS_INSTANCES_REQUIRED:{metric_code}"
            )
        statuses: list[str] = []
        result_reasons: set[str] = set()
        for instance_index, raw_instance in enumerate(raw_instances):
            instance = _mapping(
                raw_instance,
                field=f"{metric_code}.instances[{instance_index}]",
            )
            status = _text(
                instance.get("status"),
                field=f"{metric_code}.instances[{instance_index}].status",
            )
            if status not in M3_GUI_RESULT_STATUSES:
                raise M3StatusPresentationError(
                    f"M3_GUI_STATUS_RESULT_INVALID:{metric_code}:{status}"
                )
            reasons = _string_tuple(
                instance.get("reason_codes"),
                field=f"{metric_code}.instances[{instance_index}].reason_codes",
                required=status != "VALID",
            )
            statuses.append(status)
            result_reasons.update(reasons)

        unique_statuses = tuple(sorted(set(statuses)))
        kind = (
            unique_statuses[0]
            if len(unique_statuses) == 1
            else "MIXED_RESULT_STATES"
        )
        label = (
            kind
            if kind != "MIXED_RESULT_STATES"
            else f"MIXED · {', '.join(unique_statuses)}"
        )
        presentations.append(
            M3MetricStatusPresentation(
                release_id=release_id,
                metric_code=metric_code,
                family_code=family_code,
                applicable=True,
                kind=kind,
                label=label,
                reason_codes=tuple(sorted(result_reasons)),
                result_statuses=unique_statuses,
                system_type=system_type,
                style_sheet=M3_GUI_STATUS_STYLES[kind],
            )
        )

    if len({item.metric_code for item in presentations}) != 116:
        raise M3StatusPresentationError("M3_GUI_STATUS_METRIC_MEMBERSHIP_INVALID")
    return tuple(presentations)


def build_m3_evidence_drilldown(
    evidence_projection: Mapping[str, object],
    *,
    expected_release_id: str,
    expected_metric_code: str,
) -> M3EvidenceDrilldown:
    """Validate one API-projected Evidence payload against explicit identity."""

    release_id = _text(evidence_projection.get("release_id"), field="release_id")
    if release_id != expected_release_id:
        raise M3StatusPresentationError(
            f"M3_GUI_EVIDENCE_RELEASE_MISMATCH:{expected_release_id}:{release_id}"
        )
    metric_code = _text(
        evidence_projection.get("metric_code"),
        field="metric_code",
    )
    if metric_code != expected_metric_code:
        raise M3StatusPresentationError(
            f"M3_GUI_EVIDENCE_METRIC_MISMATCH:{expected_metric_code}:{metric_code}"
        )
    payload = _mapping(evidence_projection.get("payload"), field="payload")
    provenance = _mapping(
        evidence_projection.get("release_provenance"),
        field="release_provenance",
    )
    return M3EvidenceDrilldown(
        release_id=release_id,
        metric_code=metric_code,
        definition_hash=_hash(
            evidence_projection.get("definition_hash"),
            field="definition_hash",
        ),
        execution_record_hash=_hash(
            evidence_projection.get("execution_record_hash"),
            field="execution_record_hash",
        ),
        evidence_hash=_hash(
            evidence_projection.get("evidence_hash"),
            field="evidence_hash",
        ),
        payload=payload,
        manifest_hash=_hash(
            provenance.get("manifest_hash"),
            field="release_provenance.manifest_hash",
        ),
        provenance_hash=_hash(
            provenance.get("provenance_hash"),
            field="release_provenance.provenance_hash",
        ),
    )
