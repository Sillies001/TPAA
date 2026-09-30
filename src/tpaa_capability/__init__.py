"""P3 capability-model and aircraft-twin domain services."""

from .p3_model import (
    P3CapabilityModelBuild,
    P3CapabilityModelProduct,
    P3CapabilitySurfaceBuild,
    P3CapabilitySurfaceProduct,
    P3ModelExecutionProfile,
    P3ModelValidationResult,
    P3SurfaceEvaluation,
    P3TrainingDatasetSnapshot,
    build_capability_surface,
    evaluate_surface,
    evaluate_temporal_holdout,
    execute_capability_model,
    materialize_training_dataset,
)
from .p3_twin import (
    P3AircraftTwinRevision,
    P3CapabilityEstimate,
    P3TwinComponentBinding,
    evaluate_twin_capability_estimate,
    publish_aircraft_twin_revision,
)

__all__ = [
    "P3CapabilityModelBuild",
    "P3CapabilityModelProduct",
    "P3CapabilitySurfaceBuild",
    "P3CapabilitySurfaceProduct",
    "P3ModelExecutionProfile",
    "P3ModelValidationResult",
    "P3SurfaceEvaluation",
    "P3TrainingDatasetSnapshot",
    "P3AircraftTwinRevision",
    "P3CapabilityEstimate",
    "P3TwinComponentBinding",
    "build_capability_surface",
    "evaluate_surface",
    "evaluate_temporal_holdout",
    "execute_capability_model",
    "materialize_training_dataset",
    "evaluate_twin_capability_estimate",
    "publish_aircraft_twin_revision",
]
