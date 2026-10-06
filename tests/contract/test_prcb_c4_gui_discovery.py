from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def test_prcb_c4_product_workspaces_use_discovery_not_manual_exact_id_entry() -> None:
    sources = {
        name: (ROOT / "src" / "tpaa_gui" / name).read_text(encoding="utf-8")
        for name in (
            "product_shell.py",
            "m4_workspace.py",
            "m6_workspace.py",
            "m7_workspace.py",
            "m8_workspace.py",
            "m9_workspace.py",
        )
    }

    assert "TPAA_TRAJECTORY_PRESENTATION_V1 JSON" not in sources["product_shell.py"]
    assert "tpaaC4SessionReleaseBrowser" in sources["product_shell.py"]
    assert "session_release_items" in sources["product_shell.py"]
    assert "tpaaB5M3ReleaseRefresh" in sources["product_shell.py"]
    assert "tpaaB5TrajectoryRefresh" in sources["product_shell.py"]

    checks = {
        "m4_workspace.py": (
            "tpaaM4ReleaseInput",
            "tpaaM4RetrospectiveReleaseInput",
            "tpaaM4ReleaseRefresh",
        ),
        "m6_workspace.py": (
            "tpaaM6P2ReleaseInput",
            "tpaaM6EstimateInput",
            "tpaaM6DiscoveryRefresh",
        ),
        "m7_workspace.py": (
            "tpaaM7TwinRevisionInput",
            "tpaaM7EstimateInput",
            "tpaaM7DiscoveryRefresh",
        ),
        "m8_workspace.py": (
            "tpaaM8P4RevisionInput",
            "tpaaM8P5RevisionInput",
            "tpaaM8DiscoveryRefresh",
        ),
        "m9_workspace.py": (
            "tpaaM9ForecastRevisionInput",
            "tpaaM9CounterfactualRevisionInput",
            "tpaaM9RecommendationRevisionInput",
            "tpaaM9DiscoveryRefresh",
        ),
    }
    for name, object_names in checks.items():
        source = sources[name]
        assert "product_request_json" in source
        for object_name in object_names:
            assert object_name in source

    assert '"M4_RELEASE"' in sources["m4_workspace.py"]
    assert "update_retrospective" in sources["m4_workspace.py"]
    assert "fallback_forecasts" not in sources["m9_workspace.py"]
    assert "fallback_counterfactuals" not in sources["m9_workspace.py"]
