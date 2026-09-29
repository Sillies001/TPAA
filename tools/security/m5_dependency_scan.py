#!/usr/bin/env python3
"""M5 dependency/advisory and high-confidence secret scanning helpers."""

from __future__ import annotations

import hashlib
import json
import math
import re
import urllib.parse
import urllib.request
from collections.abc import Mapping
from pathlib import Path
from typing import Any, cast

OSV_QUERY_BATCH = "https://api.osv.dev/v1/querybatch"
OSV_VULN = "https://api.osv.dev/v1/vulns/"
USER_AGENT = "TPAA-M5-Qualification/1.0"

_PRIVATE_KEY = re.compile(rb"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----")
_GITHUB_TOKEN = re.compile(rb"\bgh[pousr]_[A-Za-z0-9]{30,}\b")
_AWS_KEY = re.compile(rb"\bAKIA[0-9A-Z]{16}\b")
_BEARER = re.compile(rb"\bBearer [A-Za-z0-9._~-]{20,}\b")


def _canonical_hash(value: object) -> str:
    return hashlib.sha256(
        json.dumps(
            value,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
            allow_nan=False,
        ).encode("utf-8")
    ).hexdigest()


def _request_json(
    url: str,
    *,
    payload: object | None = None,
    timeout: float = 30.0,
) -> Any:
    data = None
    headers = {
        "Accept": "application/json",
        "User-Agent": USER_AGENT,
    }
    if payload is not None:
        data = json.dumps(payload, separators=(",", ":")).encode("utf-8")
        headers["Content-Type"] = "application/json"
    request = urllib.request.Request(url, data=data, headers=headers)
    with urllib.request.urlopen(request, timeout=timeout) as response:
        return json.load(response)


def _round_up_1(value: float) -> float:
    return math.ceil((value - 1e-12) * 10.0) / 10.0


def cvss31_base_score(vector: str) -> float:
    parts = vector.split("/")
    if not parts or parts[0] != "CVSS:3.1":
        raise ValueError(f"not a CVSS 3.1 vector: {vector}")
    metrics: dict[str, str] = {}
    for part in parts[1:]:
        key, separator, value = part.partition(":")
        if not separator:
            raise ValueError(f"invalid CVSS metric: {part}")
        metrics[key] = value

    av = {"N": 0.85, "A": 0.62, "L": 0.55, "P": 0.20}[metrics["AV"]]
    ac = {"L": 0.77, "H": 0.44}[metrics["AC"]]
    scope = metrics["S"]
    pr = (
        {"N": 0.85, "L": 0.62, "H": 0.27}
        if scope == "U"
        else {"N": 0.85, "L": 0.68, "H": 0.50}
    )[metrics["PR"]]
    ui = {"N": 0.85, "R": 0.62}[metrics["UI"]]
    c = {"N": 0.0, "L": 0.22, "H": 0.56}[metrics["C"]]
    i = {"N": 0.0, "L": 0.22, "H": 0.56}[metrics["I"]]
    a = {"N": 0.0, "L": 0.22, "H": 0.56}[metrics["A"]]

    exploitability = 8.22 * av * ac * pr * ui
    isc_base = 1.0 - ((1.0 - c) * (1.0 - i) * (1.0 - a))
    if scope == "U":
        impact = 6.42 * isc_base
    else:
        impact = 7.52 * (isc_base - 0.029) - 3.25 * ((isc_base - 0.02) ** 15)

    if impact <= 0.0:
        return 0.0
    if scope == "U":
        base = min(impact + exploitability, 10.0)
    else:
        base = min(1.08 * (impact + exploitability), 10.0)
    return _round_up_1(base)


def _severity_from_score(score: float) -> str:
    if score >= 9.0:
        return "CRITICAL"
    if score >= 7.0:
        return "HIGH"
    if score >= 4.0:
        return "MEDIUM"
    return "LOW"


def _cvss31_vectors(vulnerability: Mapping[str, Any]) -> tuple[str, ...]:
    raw = vulnerability.get("severity", ())
    if not isinstance(raw, list):
        return ()
    result: list[str] = []
    for item in raw:
        if not isinstance(item, Mapping):
            continue
        kind = item.get("type")
        score = item.get("score")
        if (
            isinstance(kind, str)
            and kind.startswith("CVSS_V3")
            and isinstance(score, str)
            and score.startswith("CVSS:3.1/")
        ):
            result.append(score)
    return tuple(result)


def scan_osv_components(
    components: list[dict[str, str]],
) -> dict[str, Any]:
    queries = [
        {
            "package": {
                "ecosystem": "PyPI",
                "name": item["name"],
            },
            "version": item["version"],
        }
        for item in components
    ]
    batch = cast(dict[str, Any], _request_json(OSV_QUERY_BATCH, payload={"queries": queries}))
    results = batch.get("results")
    if not isinstance(results, list) or len(results) != len(queries):
        raise RuntimeError("OSV querybatch shape mismatch")

    ids: set[str] = set()
    component_vulns: list[dict[str, Any]] = []
    for component, result in zip(components, results, strict=True):
        if not isinstance(result, Mapping):
            raise RuntimeError("OSV result row must be object")
        raw_vulns = result.get("vulns", ())
        vuln_ids: list[str] = []
        if isinstance(raw_vulns, list):
            for item in raw_vulns:
                if isinstance(item, Mapping) and isinstance(item.get("id"), str):
                    vuln_id = cast(str, item["id"])
                    ids.add(vuln_id)
                    vuln_ids.append(vuln_id)
        component_vulns.append(
            {
                "name": component["name"],
                "version": component["version"],
                "vulnerability_ids": sorted(vuln_ids),
            }
        )

    severities: dict[str, int] = {
        "CRITICAL": 0,
        "HIGH": 0,
        "MEDIUM": 0,
        "LOW": 0,
    }
    unscored = 0
    snapshots: list[dict[str, Any]] = []
    for vuln_id in sorted(ids):
        encoded = urllib.parse.quote(vuln_id, safe="")
        vulnerability = cast(
            dict[str, Any],
            _request_json(OSV_VULN + encoded),
        )
        vectors = _cvss31_vectors(vulnerability)
        if not vectors:
            unscored += 1
            snapshots.append(
                {
                    "id": vuln_id,
                    "modified": vulnerability.get("modified"),
                    "cvss31_vectors": [],
                    "severity": "UNSCORED",
                }
            )
            continue
        scores = [cvss31_base_score(vector) for vector in vectors]
        severity = _severity_from_score(max(scores))
        severities[severity] += 1
        snapshots.append(
            {
                "id": vuln_id,
                "modified": vulnerability.get("modified"),
                "cvss31_vectors": sorted(vectors),
                "base_scores": sorted(scores),
                "severity": severity,
            }
        )

    snapshot = {
        "schema": "TPAA_M5_OSV_ADVISORY_SNAPSHOT_V1",
        "severity_model": "CVSS_V3_1",
        "components": component_vulns,
        "vulnerabilities": snapshots,
    }
    return {
        "snapshot": snapshot,
        "advisory_snapshot_sha256": _canonical_hash(snapshot),
        "critical_unwaived_count": severities["CRITICAL"],
        "high_unwaived_count": severities["HIGH"],
        "medium_unwaived_count": severities["MEDIUM"],
        "low_unwaived_count": severities["LOW"],
        "unscored_advisory_count": unscored,
    }


def scan_sbom(sbom_path: Path) -> dict[str, Any]:
    payload = cast(
        dict[str, Any],
        json.loads(sbom_path.read_text(encoding="utf-8")),
    )
    raw_components = payload.get("components")
    if not isinstance(raw_components, list):
        raise RuntimeError("CycloneDX components missing")
    components: list[dict[str, str]] = []
    for raw in raw_components:
        if not isinstance(raw, Mapping):
            continue
        name = raw.get("name")
        version = raw.get("version")
        if isinstance(name, str) and isinstance(version, str):
            components.append({"name": name, "version": version})
    if not components:
        raise RuntimeError("CycloneDX component inventory empty")
    return scan_osv_components(components)


def unknown_license_count(license_report_path: Path) -> int:
    payload = cast(
        dict[str, Any],
        json.loads(license_report_path.read_text(encoding="utf-8")),
    )
    packages = payload.get("packages")
    if not isinstance(packages, list):
        raise RuntimeError("license package inventory missing")
    return sum(
        1
        for item in packages
        if isinstance(item, Mapping)
        and item.get("declared_license") == "UNKNOWN_REQUIRES_REVIEW"
    )


def high_confidence_secret_findings(root: Path) -> list[dict[str, str]]:
    patterns = (
        ("PRIVATE_KEY", _PRIVATE_KEY),
        ("GITHUB_TOKEN", _GITHUB_TOKEN),
        ("AWS_ACCESS_KEY", _AWS_KEY),
        ("BEARER_TOKEN", _BEARER),
    )
    findings: list[dict[str, str]] = []
    scan_roots = [root / "app" / "src", root / "build-evidence"]
    for scan_root in scan_roots:
        if not scan_root.exists():
            continue
        for path in sorted(p for p in scan_root.rglob("*") if p.is_file()):
            if path.stat().st_size > 5_000_000:
                continue
            data = path.read_bytes()
            for kind, pattern in patterns:
                if pattern.search(data):
                    findings.append(
                        {
                            "kind": kind,
                            "path": path.relative_to(root).as_posix(),
                        }
                    )
    return findings
