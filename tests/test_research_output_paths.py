from __future__ import annotations

from pathlib import Path

from atlas20.config import load_config


def test_convex_validation_default_output_is_not_inside_latest_snapshot() -> None:
    config = load_config("config/base.yaml")
    reports_dir = config.resolve_path(config.paths.reports_dir)

    default_output = reports_dir.parent / "top20_convex_validation"

    assert default_output == Path("reports/top20_convex_validation").resolve()
    assert reports_dir not in default_output.parents
