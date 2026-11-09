"""Cross-platform byte normalization for governed text artifacts.

Historical Canonical locks were authored over CRLF bytes while Git checkouts are
pinned to LF. Hashes and byte counts therefore use one explicit CRLF
representation. Homogeneous LF and CRLF inputs are accepted; mixed or bare-CR
line endings are rejected.
"""

from __future__ import annotations

import hashlib
from pathlib import Path


class GovernedTextLineEndingError(ValueError):
    """A governed text artifact contains mixed or invalid line endings."""


def canonicalize_governed_text_bytes(data: bytes) -> bytes:
    """Return the historical CRLF representation without changing content.

    LF-only and CRLF-only inputs are equivalent. Mixed LF/CRLF and bare CR
    inputs fail closed so normalization cannot conceal arbitrary byte changes.
    """

    if b"\r" not in data:
        return data.replace(b"\n", b"\r\n")

    remainder = data.replace(b"\r\n", b"")
    if b"\r" in remainder or b"\n" in remainder:
        raise GovernedTextLineEndingError(
            "expected homogeneous LF or CRLF line endings; mixed or bare CR/LF found"
        )
    return data


def normalize_governed_text_to_lf(data: bytes) -> bytes:
    """Return the repository deterministic LF checkout representation."""

    return canonicalize_governed_text_bytes(data).replace(b"\r\n", b"\n")


def governed_text_sha256(data: bytes) -> str:
    """Hash the explicit historical CRLF representation."""

    return hashlib.sha256(canonicalize_governed_text_bytes(data)).hexdigest()


def governed_text_size(data: bytes) -> int:
    """Return the byte count of the explicit historical CRLF representation."""

    return len(canonicalize_governed_text_bytes(data))


def governed_text_line_ending(data: bytes) -> str:
    """Return LF, CRLF, or NONE, rejecting mixed or invalid line endings."""

    if b"\r" in data:
        canonicalize_governed_text_bytes(data)
        return "CRLF"
    if b"\n" in data:
        return "LF"
    return "NONE"


def write_utf8_lf(path: Path, text: str) -> None:
    """Write UTF-8 text with LF newlines on every operating system."""

    normalized = text.replace("\r\n", "\n")
    if "\r" in normalized:
        raise GovernedTextLineEndingError("writer input contains a bare carriage return")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(normalized.encode("utf-8"))
