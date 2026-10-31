from __future__ import annotations

from datetime import datetime, timezone
import json
from pathlib import Path

from scripts.monitor_live_track import _execution_freshness


def test_execution_freshness_rejects_a_partial_last_run(tmp_path: Path) -> None:
    state_file = tmp_path / "state.json"
    state_file.write_text(
        json.dumps(
            {
                "last_key": "SPEC|2026-10-30|2026-10-31",
                "last_status": "partial",
                "last_run_at": "2026-10-31T03:06:16+00:00",
            }
        ),
        encoding="utf-8",
    )

    fresh, detail = _execution_freshness(
        state_file,
        datetime(2026, 10, 31, 5, 0, tzinfo=timezone.utc),
    )

    assert fresh is False
    assert "partial" in detail
