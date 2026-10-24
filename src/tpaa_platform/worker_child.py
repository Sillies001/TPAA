"""Binary stdio bootstrap for one isolated governed worker invocation."""

from __future__ import annotations

import pickle
import sys

from .worker import WorkerPayload, _execute_command


def main() -> int:
    try:
        payload = pickle.loads(sys.stdin.buffer.read())
    except Exception:
        return 2
    if not isinstance(payload, WorkerPayload):
        return 2
    result = _execute_command(payload)
    sys.stdout.buffer.write(pickle.dumps(result, protocol=pickle.HIGHEST_PROTOCOL))
    sys.stdout.buffer.flush()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
