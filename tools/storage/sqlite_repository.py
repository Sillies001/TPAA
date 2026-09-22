#!/usr/bin/env python3
"""M0-STO-002 SQLite Desktop Repository acceptance entry point."""

from __future__ import annotations

import argparse
import json
import sys
import tempfile
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
SRC_ROOT = REPO_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from tpaa_storage.bootstrap import bootstrap_sqlite  # noqa: E402
from tpaa_storage.sqlite_repository import (  # noqa: E402
    SQLiteRepositoryError,
    sqlite_repository_smoke,
)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="TPAA M0-STO-002 SQLite Repository diagnostics")
    sub = parser.add_subparsers(dest="command", required=True)
    smoke = sub.add_parser("smoke", help="Run Repository/UoW smoke against an existing DB")
    smoke.add_argument("database", type=Path)
    sub.add_parser("acceptance", help="Bootstrap a disposable DB and run the full M0-STO-002 smoke")
    return parser


def main() -> int:
    args = build_parser().parse_args()
    try:
        if args.command == "smoke":
            result = sqlite_repository_smoke(args.database)
        else:
            with tempfile.TemporaryDirectory(prefix="tpaa-m0-sto-002-") as directory:
                database = Path(directory) / "desktop.sqlite3"
                bootstrap_sqlite(database)
                result = sqlite_repository_smoke(database)
        print(json.dumps(result, indent=2, sort_keys=True))
        return 0
    except SQLiteRepositoryError as exc:
        print(str(exc), file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
