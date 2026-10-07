from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def test_prcb_c5_downstream_qualification_is_product_owned_and_explicit() -> None:
    paths = (
        ROOT / "src" / "tpaa_qualification" / "prcb_c5_p3_seed.py",
        ROOT / "src" / "tpaa_qualification" / "prcb_c5_p4_p5_seed.py",
        ROOT / "src" / "tpaa_qualification" / "prcb_c5_p6_seed.py",
        ROOT / "src" / "tpaa_qualification" / "prcb_c5_downstream.py",
    )
    source = "\n".join(path.read_text(encoding="utf-8") for path in paths)
    package = (
        ROOT / "src" / "tpaa_qualification" / "__init__.py"
    ).read_text(encoding="utf-8")
    assert "tools.testing" not in source
    assert "tests/fixtures" not in source
    assert "prepare_prcb_c5_p3" in source
    assert "prepare_prcb_c5_p4" in source
    assert "prepare_prcb_c5_p5" in source
    assert "prepare_prcb_c5_p6" in source
    assert "P3PersistenceRepository" in source
    assert "P4P5ComputeInputRepository" in source
    assert "P6PersistenceRepository" in source
    assert ".prcb_c5_downstream import" not in package
    assert ".prcb_c5_p3_seed import" not in package
    assert ".prcb_c5_p4_p5_seed import" not in package
    assert ".prcb_c5_p6_seed import" not in package
    assert "seed_p3_upstream: bool = True" in source
    assert '"PRCB-C5-P45-AIRCRAFT"' in source
    p45_seed = paths[1].read_text(encoding="utf-8")
    assert '"PRCB-C5-AIRCRAFT"' not in p45_seed
    p6_seed = paths[2].read_text(encoding="utf-8")
    assert "source.estimate" in p6_seed
    assert "if order == 4" in p6_seed

    runtime = (
        ROOT / "tools" / "packaging" / "prcb_runtime_entry.py"
    ).read_text(encoding="utf-8")
    assert "from tpaa_qualification.prcb_c5_downstream import" in runtime
    assert "TPAA_PRCB_C5_INSTALLED_DESKTOP_P1_P6_E2E_V1" in runtime
    assert '"confidence": "0.9"' in runtime
    assert '"confidence": "0.8"' in runtime
    for command in (
        "P3_ESTIMATE",
        "P4_ASSESSMENT",
        "P5_ASSESSMENT",
        "P6_FORECAST",
        "P6_COUNTERFACTUAL",
    ):
        assert command in runtime
