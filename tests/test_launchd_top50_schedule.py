from __future__ import annotations

from pathlib import Path
import plistlib

ROOT = Path(__file__).resolve().parents[1]
PLIST = ROOT / "ops" / "com.atlas20.top50-readiness.plist"
WRAPPER = ROOT / "ops" / "run_top50_readiness.sh"


def test_top50_fallback_runs_once_after_the_daily_fill() -> None:
    payload = plistlib.loads(PLIST.read_bytes())

    assert payload["Label"] == "com.atlas20.top50-readiness"
    assert payload["ProgramArguments"] == [
        "/bin/zsh",
        "/Users/ww/Project/Atlas20/ops/run_top50_readiness.sh",
    ]
    assert payload["WorkingDirectory"] == "/Users/ww/Project/Atlas20"
    assert payload["StartCalendarInterval"] == [{"Hour": 9, "Minute": 45}]
    assert payload["RunAtLoad"] is False
    assert payload["ThrottleInterval"] == 300


def test_top50_wrapper_loads_only_telegram_credentials() -> None:
    text = WRAPPER.read_text(encoding="utf-8")

    assert "telegram.env" in text
    assert "bitget.env" not in text
    assert "execute_live_plan.py" not in text
    assert "/usr/bin/make top50-readiness ARGS=--notify" in text
