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
    install_deps = index_of(steps, "RUN", "uv sync", "--no-install-project")
    copy_source = index_of(steps, "COPY", "backend/app")

    assert manifest < install_deps < copy_source


def test_nothing_but_the_manifest_and_lock_are_copied_before_dependencies_install():
    steps = api_stage_instructions()
    install_deps = index_of(steps, "RUN", "uv sync", "--no-install-project")

    # The uv binary comes from its own image; everything else must wait.
    copied_first = [
        ln for ln in steps[:install_deps] if ln.startswith("COPY") and "--from=" not in ln
    ]

    assert copied_first == ["COPY backend/pyproject.toml backend/uv.lock ./"]


def test_the_app_is_installed_without_re_resolving_dependencies():
    steps = api_stage_instructions()

    copy_source = index_of(steps, "COPY", "backend/app")
    install_app = index_of(steps, "RUN", "uv sync", "--no-editable")

    assert copy_source < install_app


def test_dependencies_come_from_the_lock_file():
    """Reproducible builds: every install step uses --locked, so the image
    gets exactly the versions in uv.lock (the ones CI tested) and the
    build fails if the lock has drifted from pyproject.toml. No
    requirements.txt exists to drift the other way."""
    steps = api_stage_instructions()
    syncs = [ln for ln in steps if ln.startswith("RUN") and "uv sync" in ln]

    assert len(syncs) == 2
    assert all("--locked" in ln for ln in syncs)
    assert (DOCKERFILE.parent / "backend" / "uv.lock").exists()
    assert not (DOCKERFILE.parent / "backend" / "requirements.txt").exists()


def test_base_images_are_pinned_by_digest():
    text = DOCKERFILE.read_text(encoding="utf-8")
    froms = [ln for ln in text.splitlines() if ln.startswith("FROM ") or "COPY --from=" in ln]
    assert len(froms) >= 3  # node, python, uv
    for ln in froms:
        assert "@sha256:" in ln or "--from=frontend" in ln, ln
