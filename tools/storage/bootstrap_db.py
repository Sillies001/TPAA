#!/usr/bin/env python3
"""CLI entry point for M0-STO-001 SQLite bootstrap/readiness verification."""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import asdict
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
SRC_ROOT = REPO_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from tpaa_storage.bootstrap import BootstrapError, bootstrap_sqlite, verify_sqlite  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("command", choices=("bootstrap", "verify"))
    parser.add_argument("database", type=Path)
    args = parser.parse_args()
    try:
        result = (
            bootstrap_sqlite(args.database)
            if args.command == "bootstrap"
            else verify_sqlite(args.database)
        )
    except BootstrapError as exc:
        print(str(exc))
        return 1
    print(json.dumps(asdict(result), indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
