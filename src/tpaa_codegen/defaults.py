from __future__ import annotations

from .generators import (
    BaselineMetadataGenerator,
    DtoTypesGenerator,
    GeneratedPackageInitGenerator,
    MetricRegistryGenerator,
    ProgramRegistryGenerator,
    StageRegistryGenerator,
)
from .protocol import Generator


def default_generators() -> tuple[Generator, ...]:
    return (
        BaselineMetadataGenerator(),
        GeneratedPackageInitGenerator(),
        ProgramRegistryGenerator(),
        StageRegistryGenerator(),
        MetricRegistryGenerator(),
        DtoTypesGenerator(),
    )
