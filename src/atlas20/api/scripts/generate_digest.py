"""Generate the featured digest outside the scheduler."""

from __future__ import annotations

import argparse

from atlas20.api.scheduler import generate_featured_digest


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Generate the featured Atlas20 digest from a recently-completed run. "
            "Use --week N to replay the Nth most recent completed run (counter, "
            "NOT an ISO calendar week)."
        ),
    )
    parser.add_argument(
        "--week",
        type=int,
        default=0,
        help=(
            "Completed-run offset to replay (0 = newest completed run, 1 = the "
            "one before, etc). This is a run counter, not an ISO calendar week."
        ),
    )
    args = parser.parse_args(argv)
    files = generate_featured_digest(week=args.week)
    print(f"generated {len(files)} report files")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
