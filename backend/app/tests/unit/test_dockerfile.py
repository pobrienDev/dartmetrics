"""Guards the Dockerfile's layer order.

Docker caches each instruction's result and reuses it until that instruction
or anything before it changes. Copying the application source *before*
installing dependencies means every source edit throws the dependency layer
away and reinstalls everything. The image still works, so nothing else would
notice: builds just get slow. These tests read the Dockerfile as text and pin
the order, so the regression can't come back quietly.

No Docker needed; the docker-build CI job proves the image actually builds
and boots.
"""

from pathlib import Path

import pytest

DOCKERFILE = Path(__file__).resolve().parents[4] / "Dockerfile"


def api_stage_instructions():
    """Instructions of the final (API) stage, with continuation lines joined."""
    if not DOCKERFILE.exists():
        pytest.skip("Dockerfile not present (tests running outside the repo checkout)")
    text = DOCKERFILE.read_text(encoding="utf-8").replace("\\\n", " ")
    lines = [ln.strip() for ln in text.splitlines() if ln.strip() and not ln.strip().startswith("#")]
    last_from = max(i for i, ln in enumerate(lines) if ln.upper().startswith("FROM "))
    return lines[last_from + 1 :]


def index_of(instructions, *needles):
    matches = [i for i, ln in enumerate(instructions) if all(n in ln for n in needles)]
    assert matches, f"no instruction containing {needles}"
    return matches[0]


def test_dependencies_install_before_the_source_is_copied():
    steps = api_stage_instructions()

    manifest = index_of(steps, "COPY", "pyproject.toml")
    install_deps = index_of(steps, "RUN", "pip install -r")
    copy_source = index_of(steps, "COPY", "backend/app")

    assert manifest < install_deps < copy_source


def test_nothing_but_the_manifest_is_copied_before_dependencies_install():
    steps = api_stage_instructions()
    install_deps = index_of(steps, "RUN", "pip install -r")

    copied_first = [ln for ln in steps[:install_deps] if ln.startswith("COPY")]

    assert copied_first == ["COPY backend/pyproject.toml ./"]


def test_the_app_is_installed_without_re_resolving_dependencies():
    steps = api_stage_instructions()

    copy_source = index_of(steps, "COPY", "backend/app")
    install_app = index_of(steps, "RUN", "pip install --no-deps .")

    assert copy_source < install_app


def test_dependency_list_comes_from_pyproject_not_a_second_file():
    # One source of truth: no requirements.txt to drift out of sync.
    steps = api_stage_instructions()
    install_deps = steps[index_of(steps, "RUN", "pip install -r")]

    assert "tomllib" in install_deps and "pyproject.toml" in install_deps
    assert not (DOCKERFILE.parent / "backend" / "requirements.txt").exists()
