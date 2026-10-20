"""PostgreSQL advisory-lock write drain for managed Service transactions."""

from __future__ import annotations

import hashlib
from collections.abc import Callable
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from importlib import import_module
from time import monotonic, sleep
from typing import Any

from tpaa_storage import SERVICE_WRITE_GATE_LOCK_ID


class ServiceWriteDrainError(RuntimeError):
    """The Service managed-write gate could not be acquired or released safely."""


ConnectionFactory = Callable[[str], Any]


def _connect(conninfo: str) -> Any:
    try:
        psycopg = import_module("psycopg")
        return psycopg.connect(conninfo, autocommit=False)
    except Exception as exc:
        raise ServiceWriteDrainError("Service write-drain database connection failed") from exc


def _utc_now() -> str:
    return datetime.now(tz=UTC).isoformat().replace("+00:00", "Z")


@dataclass(frozen=True, slots=True)
class ServiceWriteDrainReceipt:
    """Secret-free evidence that the managed PostgreSQL write gate is held."""

    schema: str
    state: str
    acquired_at_utc: str
    lock_id: int
    database_identity_sha256: str
    transaction_snapshot: str
    wal_lsn: str

    def record(self) -> dict[str, object]:
        return asdict(self)


class PostgreSQLServiceWriteDrain:
    """Hold the exclusive peer of every managed Service write-UOW lock."""

    def __init__(
        self,
        conninfo: str,
        *,
        timeout_seconds: float = 30.0,
        poll_interval_seconds: float = 0.1,
        connection_factory: ConnectionFactory | None = None,
    ) -> None:
        if timeout_seconds < 0:
            raise ValueError("write-drain timeout must be non-negative")
        if poll_interval_seconds <= 0:
            raise ValueError("write-drain poll interval must be positive")
        self._conninfo = conninfo
        self._timeout_seconds = timeout_seconds
        self._poll_interval_seconds = poll_interval_seconds
        self._connection_factory = connection_factory or _connect
        self._connection: Any | None = None
        self._receipt: ServiceWriteDrainReceipt | None = None

    @property
    def receipt(self) -> ServiceWriteDrainReceipt:
        if self._receipt is None:
            raise ServiceWriteDrainError("Service write drain is not active")
        return self._receipt

    def _release(self, connection: Any) -> None:
        try:
            with connection.cursor() as cursor:
                cursor.execute(
                    "SELECT pg_advisory_unlock(%s)",
                    (SERVICE_WRITE_GATE_LOCK_ID,),
                )
                row = cursor.fetchone()
            connection.commit()
            if row is None or row[0] is not True:
                raise ServiceWriteDrainError("Service write-drain lock was not held")
        finally:
            connection.close()

    def __enter__(self) -> ServiceWriteDrainReceipt:
        if self._connection is not None:
            raise ServiceWriteDrainError("Service write drain is already active")
        connection = self._connection_factory(self._conninfo)
        acquired = False
        deadline = monotonic() + self._timeout_seconds
        try:
            while True:
                with connection.cursor() as cursor:
                    cursor.execute(
                        "SELECT pg_try_advisory_lock(%s)",
                        (SERVICE_WRITE_GATE_LOCK_ID,),
                    )
                    row = cursor.fetchone()
                connection.commit()
                acquired = row is not None and row[0] is True
                if acquired:
                    break
                if monotonic() >= deadline:
                    raise ServiceWriteDrainError(
                        "Service write-drain timed out waiting for managed writes"
                    )
                sleep(self._poll_interval_seconds)

            with connection.cursor() as cursor:
                cursor.execute(
                    "SELECT current_database(), "
                    "txid_current_snapshot()::text, "
                    "pg_current_wal_lsn()::text"
                )
                watermark = cursor.fetchone()
            connection.commit()
            if watermark is None or len(watermark) != 3:
                raise ServiceWriteDrainError("Service write-drain watermark unavailable")
            database_identity = hashlib.sha256(str(watermark[0]).encode("utf-8")).hexdigest()
            receipt = ServiceWriteDrainReceipt(
                schema="TPAA_SERVICE_WRITE_DRAIN_V1",
                state="MANAGED_WRITES_BLOCKED",
                acquired_at_utc=_utc_now(),
                lock_id=SERVICE_WRITE_GATE_LOCK_ID,
                database_identity_sha256=database_identity,
                transaction_snapshot=str(watermark[1]),
                wal_lsn=str(watermark[2]),
            )
            self._connection = connection
            self._receipt = receipt
            return receipt
        except Exception:
            if acquired:
                self._release(connection)
            else:
                connection.close()
            raise

    def __exit__(self, exc_type: object, exc: object, traceback: object) -> None:
        connection = self._connection
        self._connection = None
        self._receipt = None
        if connection is None:
            return
        try:
            self._release(connection)
        except ServiceWriteDrainError:
            if exc is None:
                raise


__all__ = [
    "PostgreSQLServiceWriteDrain",
    "ServiceWriteDrainError",
    "ServiceWriteDrainReceipt",
]
