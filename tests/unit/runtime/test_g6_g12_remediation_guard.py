from __future__ import annotations

import pytest

from tools.gui.remediation_guard import RemediationGuardError, require_reclosure_ready


@pytest.mark.parametrize("phase", ["G6", "G7", "G8", "G9", "G10", "G11", "G12"])
def test_post_closure_remediation_blocks_legacy_reclosure(phase: str) -> None:
    with pytest.raises(RemediationGuardError, match=rf"{phase}_RECLOSURE_BLOCKED"):
        require_reclosure_ready(phase)
