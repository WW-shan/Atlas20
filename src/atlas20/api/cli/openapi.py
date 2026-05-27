"""Generate and check the frontend OpenAPI snapshot."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys
from typing import Any, Sequence

from atlas20.api.app import create_app
from atlas20.api.settings import get_settings


def default_schema_path() -> Path:
    return get_settings().project_root / "apps" / "web" / "src" / "lib" / "api-schema.json"


def generate_schema() -> dict[str, Any]:
    return create_app().openapi()


def render_schema(schema: dict[str, Any]) -> str:
    return json.dumps(schema, indent=2, sort_keys=True) + "\n"


def write_schema(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(render_schema(generate_schema()), encoding="utf-8")


def check_schema(path: Path) -> int:
    expected = render_schema(generate_schema())
    if not path.exists():
        print(f"OpenAPI snapshot missing: {path}", file=sys.stderr)
        return 1
    actual = path.read_text(encoding="utf-8")
    if actual != expected:
        print(
            f"OpenAPI snapshot is stale: {path}\n"
            "Run `python -m atlas20.api.openapi` and commit the updated snapshot.",
            file=sys.stderr,
        )
        return 1
    return 0


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true", help="fail if the snapshot differs from the generated schema")
    parser.add_argument("--output", type=Path, default=None, help="schema output path")
    args = parser.parse_args(argv)

    path = args.output or default_schema_path()
    if args.check:
        return check_schema(path)
    write_schema(path)
    print(f"OpenAPI snapshot: {path}")
    return 0
