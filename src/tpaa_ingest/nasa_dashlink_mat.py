"""Manifest and byte inspection for NASA DASHlink MATLAB flight records.

Decoding is deliberately an external adapter concern because scipy is not a
TPAA Core runtime dependency.  ``tools/data/convert_nasa_dashlink_mat.py``
performs the versioned decode into the governed Flight Recorder CSV profile.
"""

from __future__ import annotations

import hashlib

from .production_source import (
    ProductionSourceAdapterError,
    SourceAdapterDescriptor,
    SourceArtifactEnvelope,
    SourceFamily,
)

NASA_DASHLINK_MAT_ADAPTER_ID = "nasa-dashlink-mat-v5"
NASA_DASHLINK_MAT_ADAPTER_VERSION = "1.0.0"
NASA_DASHLINK_MAT_MEDIA_TYPE = "application/x-matlab-data"
NASA_DASHLINK_MAPPING_PROFILE = "NASA_DASHLINK_186_PARAMETER_TO_TPAA_FLIGHT_CSV_V1"


class NasaDashlinkMatAdapter:
    """Byte-level gate for the public de-identified NASA MATLAB source."""

    @property
    def descriptor(self) -> SourceAdapterDescriptor:
        return SourceAdapterDescriptor(
            adapter_id=NASA_DASHLINK_MAT_ADAPTER_ID,
            adapter_version=NASA_DASHLINK_MAT_ADAPTER_VERSION,
            source_family=SourceFamily.FLIGHT,
            media_types=(NASA_DASHLINK_MAT_MEDIA_TYPE,),
            external_decoder=True,
        )

    def inspect(
        self,
        *,
        source_ref: str,
        data: bytes,
        media_type: str,
        classification_label: str | None = None,
    ) -> SourceArtifactEnvelope:
        if media_type != NASA_DASHLINK_MAT_MEDIA_TYPE:
            raise ProductionSourceAdapterError(
                "B3_SOURCE_ADAPTER_MEDIA_TYPE_UNSUPPORTED", media_type
            )
        if not data.startswith(b"MATLAB 5.0 MAT-file"):
            raise ProductionSourceAdapterError(
                "W2_NASA_DASHLINK_MAT_UNSUPPORTED", "MATLAB_V5_HEADER_REQUIRED"
            )
        if not source_ref or source_ref.strip() != source_ref:
            raise ProductionSourceAdapterError(
                "B3_SOURCE_ADAPTER_DESCRIPTOR_INVALID", "source_ref"
            )
        return SourceArtifactEnvelope(
            source_family=SourceFamily.FLIGHT,
            adapter_id=NASA_DASHLINK_MAT_ADAPTER_ID,
            adapter_version=NASA_DASHLINK_MAT_ADAPTER_VERSION,
            source_ref=source_ref,
            artifact_sha256=hashlib.sha256(data).hexdigest(),
            size_bytes=len(data),
            media_type=media_type,
            classification_label=classification_label,
        )
