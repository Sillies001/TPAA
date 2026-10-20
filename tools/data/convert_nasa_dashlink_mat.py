"""Convert one de-identified NASA DASHlink MATLAB record to W2 governed CSV.

Run in an isolated tooling environment; scipy is intentionally not a TPAA
runtime dependency:

    uv run --with scipy==1.16.3 python tools/data/convert_nasa_dashlink_mat.py ...
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
from collections.abc import Sequence
from pathlib import Path
from typing import Any, cast

MAPPING_PROFILE = "NASA_DASHLINK_186_PARAMETER_TO_TPAA_FLIGHT_CSV_V1"
EXPECTED = {
    "ROLL": (8, "DEG", "ROLL ANGLE LSP"),
    "VRTG": (8, "G", "VERTICAL ACCELERATION"),
    "TH": (4, "DEG", "TRUE HEADING LSP"),
    "TAS": (4, "KNOTS", "TRUE AIRSPEED LSP"),
    "MACH": (4, "MACH", "MACH LSP"),
}


def _plain_series(value: object, *, field: str) -> list[float]:
    if not isinstance(value, Sequence) and not hasattr(value, "tolist"):
        raise ValueError(f"W2_NASA_PARAMETER_INVALID:{field}.data")
    raw = (
        list(value)
        if isinstance(value, Sequence)
        else cast(Any, value).tolist()
    )
    if not isinstance(raw, list):
        raw = [raw]
    result = [float(item) for item in raw]
    if not result or any(not math.isfinite(item) for item in result):
        raise ValueError(f"W2_NASA_PARAMETER_INVALID:{field}.data")
    return result


def _parameter(document: dict[str, Any], name: str) -> tuple[list[float], int]:
    value = document.get(name)
    if value is None:
        raise ValueError(f"W2_NASA_PARAMETER_MISSING:{name}")
    rate, unit, description = EXPECTED[name]
    if int(value.Rate) != rate or str(value.Units) != unit:
        raise ValueError(f"W2_NASA_PARAMETER_PROFILE_DRIFT:{name}")
    if str(value.Description) != description:
        raise ValueError(f"W2_NASA_PARAMETER_DESCRIPTION_DRIFT:{name}")
    return _plain_series(value.data, field=name), rate


def convert(source: Path, target: Path) -> dict[str, object]:
    from scipy.io import loadmat  # type: ignore[import-untyped]

    source_bytes = source.read_bytes()
    if not source_bytes.startswith(b"MATLAB 5.0 MAT-file"):
        raise ValueError("W2_NASA_MATLAB_V5_REQUIRED")
    document = loadmat(source, squeeze_me=True, struct_as_record=False)
    roll, _ = _parameter(document, "ROLL")
    nz, _ = _parameter(document, "VRTG")
    heading, rate = _parameter(document, "TH")
    tas, _ = _parameter(document, "TAS")
    mach, _ = _parameter(document, "MACH")
    count = len(heading)
    if len(tas) != count or len(mach) != count or len(roll) != count * 2:
        raise ValueError("W2_NASA_PARAMETER_LENGTH_DRIFT")
    if len(nz) != count * 2:
        raise ValueError("W2_NASA_PARAMETER_LENGTH_DRIFT")

    target.parent.mkdir(parents=True, exist_ok=True)
    with target.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.writer(stream, lineterminator="\n")
        writer.writerow(
            (
                "source_time_us",
                "session_time_us",
                "p_deg_s",
                "nz_g",
                "heading_deg_true",
                "tas_kt",
                "mach",
                "quality_mask",
            )
        )
        for index in range(count):
            time_us = index * (1_000_000 // rate)
            roll_start = roll[index * 2]
            roll_end = roll[index * 2 + 1]
            p_deg_s = (roll_end - roll_start) * 8.0
            writer.writerow(
                (
                    time_us,
                    time_us,
                    format(p_deg_s, ".17g"),
                    format((nz[index * 2] + nz[index * 2 + 1]) / 2.0, ".17g"),
                    format(heading[index] % 360.0, ".17g"),
                    format(tas[index], ".17g"),
                    format(mach[index], ".17g"),
                    0,
                )
            )
    target_bytes = target.read_bytes()
    manifest: dict[str, object] = {
        "schema": "TPAA_W2_REAL_DATA_GOLDEN_MANIFEST_V1",
        "mapping_profile": MAPPING_PROFILE,
        "source_name": source.name,
        "source_sha256": hashlib.sha256(source_bytes).hexdigest(),
        "source_bytes": len(source_bytes),
        "source_privacy": "PUBLIC_DE_IDENTIFIED_NASA_DASHLINK",
        "target_name": target.name,
        "target_sha256": hashlib.sha256(target_bytes).hexdigest(),
        "target_bytes": len(target_bytes),
        "row_count": count,
        "sample_rate_hz": rate,
        "mappings": {
            "ROLL": "derived p_deg_s from adjacent 8 Hz samples",
            "VRTG": "nz_g averaged to 4 Hz",
            "TH": "heading_deg_true",
            "TAS": "tas_kt",
            "MACH": "mach",
        },
    }
    manifest_path = target.with_suffix(target.suffix + ".manifest.json")
    manifest_path.write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return manifest


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("source", type=Path)
    parser.add_argument("target", type=Path)
    args = parser.parse_args()
    print(json.dumps(convert(args.source, args.target), indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
