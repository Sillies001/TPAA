"""Fail-closed PIQB B2 schema persistence-fit gate."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, cast

FIT_STATUSES = frozenset(
    {
        "FIT",
        "FIT_EXISTING",
        "FIT_EXISTING_SUBSTRATE",
        "FIT_WITH_DERIVATIONS",
    }
)


class PersistenceFitError(RuntimeError):
    """A requested production persistence path lacks canonical schema authority."""

    def __init__(self, product_family: str, status: str) -> None:
        self.product_family = product_family
        self.status = status
        super().__init__(
            "PIQB_B2_PERSISTENCE_FIT_BLOCKED "
            f"product_family={product_family} status={status}"
        )


@dataclass(frozen=True, slots=True)
class PersistenceFitRecord:
    product_family: str
    status: str
    blockers: tuple[str, ...]

    @property
    def production_allowed(self) -> bool:
        return self.status in FIT_STATUSES and not self.blockers


class ProductPersistenceFitGate:
    """Load the frozen B2 fit audit and guard production adapter construction."""

    def __init__(self, records: dict[str, PersistenceFitRecord]) -> None:
        self._records = dict(records)

    @classmethod
    def from_baseline(
        cls,
        path: Path | None = None,
    ) -> ProductPersistenceFitGate:
        source = (
            Path(__file__).resolve().parents[2]
            / "docs"
            / "baseline"
            / "PIQB-1.0"
            / "B2_SCHEMA_PERSISTENCE_FIT.json"
            if path is None
            else path
        )
        raw: Any = json.loads(source.read_text(encoding="utf-8"))
        if not isinstance(raw, dict):
            raise PersistenceFitError("BASELINE", "INVALID_ROOT")
        payload = cast(dict[str, Any], raw)
        if payload.get("schema") != "TPAA_PIQB_B2_SCHEMA_PERSISTENCE_FIT_V1":
            raise PersistenceFitError("BASELINE", "SCHEMA_MISMATCH")
        if payload.get("db_schema_version") != "1.6.0":
            raise PersistenceFitError("BASELINE", "DB_SCHEMA_MISMATCH")
        if payload.get("no_shadow_schema") is not True:
            raise PersistenceFitError("BASELINE", "SHADOW_SCHEMA_NOT_FORBIDDEN")

        records: dict[str, PersistenceFitRecord] = {}
        families = payload.get("families")
        if not isinstance(families, list):
            raise PersistenceFitError("BASELINE", "FAMILIES_INVALID")
        for item in families:
            if not isinstance(item, dict):
                raise PersistenceFitError("BASELINE", "FAMILY_INVALID")
            family = item.get("product_family")
            status = item.get("status")
            blockers_raw = item.get("blockers", [])
            if not isinstance(family, str) or not isinstance(status, str):
                raise PersistenceFitError("BASELINE", "FAMILY_IDENTITY_INVALID")
            if not isinstance(blockers_raw, list):
                raise PersistenceFitError(family, "BLOCKERS_INVALID")
            blockers: list[str] = []
            for blocker in blockers_raw:
                if not isinstance(blocker, dict):
                    raise PersistenceFitError(family, "BLOCKER_INVALID")
                field = blocker.get("field")
                reason = blocker.get("reason")
                if not isinstance(field, str) or not isinstance(reason, str):
                    raise PersistenceFitError(family, "BLOCKER_INVALID")
                blockers.append(f"{field}: {reason}")
            records[family] = PersistenceFitRecord(
                product_family=family,
                status=status,
                blockers=tuple(blockers),
            )
        return cls(records)

    def record(self, product_family: str) -> PersistenceFitRecord:
        try:
            return self._records[product_family]
        except KeyError as exc:
            raise PersistenceFitError(
                product_family,
                "UNREVIEWED_PRODUCT_FAMILY",
            ) from exc

    def assert_production_allowed(self, product_family: str) -> None:
        record = self.record(product_family)
        if not record.production_allowed:
            raise PersistenceFitError(product_family, record.status)
