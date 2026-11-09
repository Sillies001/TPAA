"""Cross-platform byte handling for governed Canonical text artifacts.

Historical locks pin each artifact's original LF or CRLF representation.
Git checkouts are normalized to LF, but verification accepts either homogeneous
representation by matching the trusted lock's SHA-256 and byte count. Mixed
line endings and bare CR are always rejected.
"""

from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Literal, cast

GovernedTextRepresentation = Literal["LF", "CRLF"]
MatchedTextRepresentation = Literal["LF", "CRLF", "NONE"]


class GovernedTextLineEndingError(ValueError):
    """A governed text artifact contains mixed or invalid line endings."""


class GovernedTextLockMismatch(ValueError):
    """Neither homogeneous line-ending representation matches the trusted lock."""


def governed_text_candidates(data: bytes) -> tuple[bytes, bytes]:
    """Return equivalent LF and CRLF candidates, rejecting mixed or bare CR."""

    if b"\r" in data:
        remainder = data.replace(b"\r\n", b"")
        if b"\r" in remainder or b"\n" in remainder:
            raise GovernedTextLineEndingError(
                "expected homogeneous LF or CRLF line endings; mixed or bare CR/LF found"
            )
        crlf_bytes = data
        lf_bytes = data.replace(b"\r\n", b"\n")
        return lf_bytes, crlf_bytes

    lf_bytes = data
    crlf_bytes = data.replace(b"\n", b"\r\n")
    return lf_bytes, crlf_bytes


def canonicalize_governed_text_bytes(
    data: bytes, representation: GovernedTextRepresentation = "CRLF"
) -> bytes:
    """Return the requested homogeneous representation without changing content."""

    lf_bytes, crlf_bytes = governed_text_candidates(data)
    if representation == "LF":
        return lf_bytes
    if representation == "CRLF":
        return crlf_bytes
    raise ValueError(f"unsupported governed text representation: {representation!r}")


def match_governed_text_bytes(
    data: bytes, expected_sha256: str, expected_size: int | None = None
) -> tuple[bytes, MatchedTextRepresentation]:
    """Match LF or CRLF bytes against a trusted hash and optional byte count.

    Returns the exact canonical bytes and the matched representation. A file
    without line terminators is reported as NONE because LF and CRLF are identical.
    The caller must obtain expected values from an already trusted lock.
    """

    lf_bytes, crlf_bytes = governed_text_candidates(data)
    expected_digest = expected_sha256.lower()
    matches: list[tuple[bytes, GovernedTextRepresentation]] = []
    for representation, candidate in (("LF", lf_bytes), ("CRLF", crlf_bytes)):
        if expected_size is not None and len(candidate) != expected_size:
            continue
        digest = hashlib.sha256(candidate).hexdigest()
        if digest == expected_digest:
            matches.append((candidate, cast(GovernedTextRepresentation, representation)))

    if not matches:
        lf_digest = hashlib.sha256(lf_bytes).hexdigest()
        crlf_digest = hashlib.sha256(crlf_bytes).hexdigest()
        raise GovernedTextLockMismatch(
            f"expected_sha256={expected_digest} expected_bytes={expected_size!r}; "
            f"LF_bytes={len(lf_bytes)} LF_sha256={lf_digest}; "
            f"CRLF_bytes={len(crlf_bytes)} CRLF_sha256={crlf_digest}"
        )

    if len(matches) > 1 and matches[0][0] != matches[1][0]:
        raise GovernedTextLockMismatch(
            "ambiguous LF/CRLF match against trusted lock; refusing to choose a representation"
        )

    canonical_bytes, representation = matches[0]
    matched_representation: MatchedTextRepresentation = representation
    if len(matches) > 1:
        matched_representation = "NONE"
    return canonical_bytes, matched_representation


def normalize_governed_text_to_lf(data: bytes) -> bytes:
    """Return the repository deterministic LF checkout representation."""

    return governed_text_candidates(data)[0]


def governed_text_sha256(
    data: bytes, representation: GovernedTextRepresentation = "CRLF"
) -> str:
    """Hash the requested explicit historical representation (CRLF by default)."""

    canonical_bytes = canonicalize_governed_text_bytes(data, representation)
    return hashlib.sha256(canonical_bytes).hexdigest()


def governed_text_size(
    data: bytes, representation: GovernedTextRepresentation = "CRLF"
) -> int:
    """Return the byte count of the requested explicit representation."""

    return len(canonicalize_governed_text_bytes(data, representation))


def governed_text_line_ending(data: bytes) -> MatchedTextRepresentation:
    """Return the physical LF, CRLF, or NONE style after strict validation."""

    governed_text_candidates(data)
    if b"\r" in data:
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
