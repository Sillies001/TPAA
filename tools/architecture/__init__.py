"""Static architecture dependency verification for TPAA."""

from .dependency_policy import ArchitecturePolicy, ArchitectureViolation, load_policy, scan_architecture

__all__ = [
    "ArchitecturePolicy",
    "ArchitectureViolation",
    "load_policy",
    "scan_architecture",
]
