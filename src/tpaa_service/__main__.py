"""Run the durable TPAA Service profile."""

from __future__ import annotations

import argparse
import json
import sys
from collections.abc import Sequence
from pathlib import Path

import uvicorn

from . import create_app, service_preflight


def main(
    argv: Sequence[str] | None = None,
    *,
    app_root: Path | None = None,
) -> int:
    parser = argparse.ArgumentParser(prog="python -m tpaa_service")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8000)
    parser.add_argument(
        "--check-config",
        action="store_true",
        help="validate configuration and live dependencies without binding a socket",
    )
    args = parser.parse_args(argv)
    try:
        if args.check_config:
            payload = service_preflight(app_root=app_root)
            print(json.dumps(payload, sort_keys=True))
            return 0 if payload.get("status") == "READY" else 2
        app = create_app(app_root=app_root)
        uvicorn.run(
            app,
            host=args.host,
            port=args.port,
            log_config=None,
            access_log=False,
            server_header=False,
            date_header=False,
        )
    except Exception as exc:
        print(
            json.dumps(
                {
                    "schema": "TPAA_SERVICE_STARTUP_ERROR_V1",
                    "status": "FAILED",
                    "error_type": type(exc).__name__,
                },
                sort_keys=True,
            ),
            file=sys.stderr,
        )
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
