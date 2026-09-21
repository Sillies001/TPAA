from __future__ import annotations

from tpaa_codegen.models import SourceArtifactRef
from tpaa_codegen.provenance import GENERATED_MARKER, decorate_python_source, provenance_header


def test_provenance_header_is_deterministic_and_source_sorted() -> None:
    sources = (
        SourceArtifactRef("Z_SOURCE", "2.0", "b" * 64),
        SourceArtifactRef("A_SOURCE", "1.0", "a" * 64),
    )
    header = provenance_header(generator_id="g", generator_version="0.2.0", sources=sources)
    assert header.decode().splitlines() == [
        GENERATED_MARKER,
        "# generator_id=g",
        "# generator_version=0.2.0",
        f"# source artifact_id=A_SOURCE version=1.0 sha256={'a' * 64}",
        f"# source artifact_id=Z_SOURCE version=2.0 sha256={'b' * 64}",
    ]


def test_decorate_python_source_places_governance_before_module_body() -> None:
    source = SourceArtifactRef("BASELINE_LOCK", "CB-1.4.0", "a" * 64)
    rendered = decorate_python_source(
        b'"""module"""\nvalue = 1\n',
        generator_id="baseline-metadata",
        generator_version="0.2.0",
        sources=(source,),
    )
    assert rendered.startswith((GENERATED_MARKER + "\n").encode())
    assert b"# generator_version=0.2.0\n" in rendered
    assert b"artifact_id=BASELINE_LOCK version=CB-1.4.0" in rendered
    assert rendered.endswith(b'"""module"""\nvalue = 1\n')
