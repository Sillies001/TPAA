from __future__ import annotations

import json
from typing import Any


def render_python(lines: list[str] | tuple[str, ...]) -> bytes:
    return ("\n".join(lines).rstrip("\n") + "\n").encode("utf-8")


def render_json(value: Any) -> bytes:
    text = json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True)
    return (text + "\n").encode("utf-8")
