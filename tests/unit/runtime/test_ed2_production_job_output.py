from __future__ import annotations

from pathlib import Path
from uuid import uuid4

import pytest

from tpaa_runtime.production_job_output import (
    ProductionJobOutputError,
    ProductionJobOutputRepository,
)
from tpaa_storage import SQLiteDesktopUnitOfWork, bootstrap_sqlite


def test_ed2_production_job_output_receipt_is_restart_exact_and_immutable(
    tmp_path: Path,
) -> None:
    database = tmp_path / "tpaa.db"
    bootstrap_sqlite(database)
    job_id = str(uuid4())
    product_id = str(uuid4())

    with SQLiteDesktopUnitOfWork(database, write=True) as uow:
        repository = ProductionJobOutputRepository(uow.canonical_rows)
        created = repository.register(
            job_id=job_id,
            command="P3_BUILD_PRODUCTS",
            product_refs=(("twin_revision_id", product_id),),
        )
        assert repository.exact(
            job_id=job_id,
            command="P3_BUILD_PRODUCTS",
        ) == created
        uow.commit()

    with SQLiteDesktopUnitOfWork(database) as uow:
        restarted = ProductionJobOutputRepository(uow.canonical_rows)
        exact = restarted.exact(
            job_id=job_id,
            command="P3_BUILD_PRODUCTS",
        )
        assert exact.mapping() == {"twin_revision_id": product_id}
        uow.commit()

    with SQLiteDesktopUnitOfWork(database, write=True) as uow:
        repository = ProductionJobOutputRepository(uow.canonical_rows)
        with pytest.raises(
            ProductionJobOutputError,
            match="ED2_JOB_OUTPUT_IMMUTABLE_CONFLICT",
        ):
            repository.register(
                job_id=job_id,
                command="P3_BUILD_PRODUCTS",
                product_refs=(("twin_revision_id", str(uuid4())),),
            )


def test_ed2_production_job_output_requires_exact_nonempty_role_refs(
    tmp_path: Path,
) -> None:
    database = tmp_path / "tpaa.db"
    bootstrap_sqlite(database)
    job_id = str(uuid4())

    with SQLiteDesktopUnitOfWork(database, write=True) as uow:
        repository = ProductionJobOutputRepository(uow.canonical_rows)
        with pytest.raises(
            ProductionJobOutputError,
            match="ED2_JOB_OUTPUT_REFS_INVALID",
        ):
            repository.register(
                job_id=job_id,
                command="P4_ASSESSMENT",
                product_refs=(),
            )
