"""Shared install-shadowing diagnostic.

Both the API process (`app.py` lifespan) and the worker process
(`worker.main.main`) emit a warning when an installed copy of `atlas20`
shadows the repo `src/` tree. Living in a tiny module of its own lets the
worker call it without dragging in FastAPI, middleware, routes, and the
scheduler that `app.py` imports at module load time.
"""

from __future__ import annotations

import logging
from pathlib import Path

logger = logging.getLogger(__name__)


def warn_if_shadow_install() -> None:
    """Warn when an installed copy of `atlas20` shadows the repo `src/` tree.

    A non-editable `pip install .` plants the package in site-packages, which
    sys.path resolves before the repo's `src/` layout. Edits to `src/` then
    have no runtime effect, while pytest still passes because pyproject sets
    `pythonpath=["src"]`. This is silent in Docker (the image has no
    `src/atlas20/__init__.py` at `/app`) and silent under PYTHONPATH=src or
    editable installs (atlas20.__file__ already lives under the repo).
    """
    import atlas20

    repo_init = Path.cwd() / "src" / "atlas20" / "__init__.py"
    if not repo_init.exists():
        return
    loaded_from = Path(atlas20.__file__).resolve()
    expected_under = repo_init.parent.resolve()
    try:
        loaded_from.relative_to(expected_under)
    except ValueError:
        logger.warning(
            "atlas20 was imported from %s but the repo has src/atlas20/ at %s; "
            "runtime is using a stale installed copy. Run "
            "`python -m pip install -e .` or set PYTHONPATH=src so edits take effect.",
            loaded_from,
            expected_under,
        )
