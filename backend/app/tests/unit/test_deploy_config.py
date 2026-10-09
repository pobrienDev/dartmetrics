"""Guards the Render blueprint's deploy gating.

The container applies migrations to the production database on start,
so a push to main must only deploy after CI has passed. Read as text
like the Dockerfile tests: no YAML parser is needed to pin one key.
"""

from pathlib import Path

import pytest

RENDER_YAML = Path(__file__).resolve().parents[4] / "render.yaml"


def blueprint_lines() -> list[str]:
    if not RENDER_YAML.exists():
        pytest.skip("render.yaml not present (tests running outside the repo checkout)")
    text = RENDER_YAML.read_text(encoding="utf-8")
    return [ln.strip() for ln in text.splitlines() if ln.strip() and not ln.strip().startswith("#")]


def test_deploys_wait_for_ci_checks():
    lines = blueprint_lines()
    assert "autoDeployTrigger: checksPass" in lines
    # The deprecated key would take effect if autoDeployTrigger were ever removed.
    assert not any(ln.startswith("autoDeploy:") for ln in lines)
