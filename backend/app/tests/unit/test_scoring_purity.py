"""The scoring package must stay framework-free.

Everything under app/scoring is pure game logic: rules, checkouts, and the
bot. It should import nothing but the standard library and its own modules,
so it can be tested, reused, or reasoned about without a database, a web
framework, or settings.

Each module is imported in a fresh interpreter, because by the time this
test runs the rest of the suite has already loaded SQLAlchemy and FastAPI
into this one.
"""

import pkgutil
import subprocess
import sys

import pytest

import app.scoring

FRAMEWORKS = ("sqlalchemy", "fastapi", "pydantic", "starlette", "alembic")
MODULES = sorted(m.name for m in pkgutil.iter_modules(app.scoring.__path__, "app.scoring."))


def test_every_scoring_module_is_checked():
    # Guards the guard: a new module is picked up automatically.
    assert {"app.scoring.engine", "app.scoring.bot", "app.scoring.domain"} <= set(MODULES)


@pytest.mark.parametrize("module", MODULES)
def test_scoring_module_imports_no_framework(module):
    probe = (
        "import importlib, sys\n"
        f"importlib.import_module({module!r})\n"
        f"loaded = sorted(f for f in {FRAMEWORKS!r} if f in sys.modules)\n"
        "print(','.join(loaded))\n"
    )
    result = subprocess.run([sys.executable, "-c", probe], capture_output=True, text=True, check=False)

    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == "", f"{module} pulled in: {result.stdout.strip()}"
