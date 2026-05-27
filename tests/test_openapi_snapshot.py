from __future__ import annotations

from atlas20.api.cli.openapi import default_schema_path, generate_schema, render_schema
from atlas20.api.settings import get_settings


def test_openapi_snapshot_matches_generated_schema() -> None:
    get_settings.cache_clear()
    snapshot_path = default_schema_path()

    assert snapshot_path.read_text(encoding="utf-8") == render_schema(generate_schema())
