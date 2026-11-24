"""Run one production node under a wall-clock deadline.

The data node is a sequence of independent programs.  A per-provider timeout
inside ``refresh_daily_data.py`` cannot stop a later Bitget or Top50 command
from running after 08:50 Beijing.  This supervisor starts the whole node in
its own process group, terminates that group when the deadline expires, and
returns the existing fail-closed status 3.
"""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import os
from pathlib import Path
import signal
import subprocess
import sys
from typing import Sequence


def _utc(value: str) -> datetime:
    moment = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if moment.tzinfo is None:
        return moment.replace(tzinfo=timezone.utc)
    return moment.astimezone(timezone.utc)


def command(
    *,
    deadline_utc: str,
    command: Sequence[str],
) -> list[str]:
    """Return a self-supervising command."""

    _utc(deadline_utc)
    if not command:
        raise ValueError("command must not be empty")
    return [
        sys.executable,
        str(Path(__file__).resolve()),
        "--deadline-utc",
        deadline_utc,
        "--",
        *command,
    ]


def run(*, deadline_utc: str, command: Sequence[str]) -> int:
    if not command:
        print("node deadline: no command supplied", file=sys.stderr)
        return 2
    deadline = _utc(deadline_utc)
    remaining = (deadline - datetime.now(timezone.utc)).total_seconds()
    if remaining <= 0.0:
        print(
            f"node deadline reached at {deadline.isoformat()}; refusing to start",
            file=sys.stderr,
        )
        return 3

    process = subprocess.Popen(
        list(command),
        start_new_session=True,
    )
    try:
        return int(process.wait(timeout=remaining))
    except subprocess.TimeoutExpired:
        print(
            f"node deadline reached at {deadline.isoformat()}; terminating process group",
            file=sys.stderr,
        )
        try:
            os.killpg(process.pid, signal.SIGTERM)
        except ProcessLookupError:
            pass
        try:
            process.wait(timeout=10.0)
        except subprocess.TimeoutExpired:
            try:
                os.killpg(process.pid, signal.SIGKILL)
            except ProcessLookupError:
                pass
            process.wait()
        return 3


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--deadline-utc", required=True)
    parser.add_argument("command", nargs=argparse.REMAINDER)
    args = parser.parse_args(argv)
    command_args = list(args.command)
    if command_args[:1] == ["--"]:
        command_args = command_args[1:]
    return run(deadline_utc=args.deadline_utc, command=command_args)


if __name__ == "__main__":
    raise SystemExit(main())
