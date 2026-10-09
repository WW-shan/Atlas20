from __future__ import annotations

import pandas as pd
import pytest


def _book() -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "signal_date": "2026-10-08 00:00:00+00:00",
                "execution_hint": "2026-10-09 03:00:00+00:00",
                "asset": "near",
                "target_weight": 0.7768,
                "target_notional_per_1k": 776.78,
                "change_weight": 0.1447,
                "change_notional_per_1k": 144.67,
                "action": "BUY",
            },
            {
                "signal_date": "2026-10-08 00:00:00+00:00",
                "execution_hint": "2026-10-09 03:00:00+00:00",
                "asset": "zcash",
                "target_weight": 0.2138,
                "target_notional_per_1k": 213.77,
                "change_weight": 0.0,
                "change_notional_per_1k": 0.0,
                "action": "HOLD",
            },
        ]
    )


def test_format_derivatives_message_labels_utc_close_and_execution() -> None:
    from scripts.send_derivatives_signal import format_derivatives_message

    message = format_derivatives_message(
        _book(),
        signal_date=pd.Timestamp("2026-10-08", tz="UTC"),
        execution_hint=pd.Timestamp("2026-10-09 03:00", tz="UTC"),
    )

    assert "Atlas20 合约信号 · PR2026-10-D-L125-V2" in message
    assert "信号日线（UTC）: 2026-10-08" in message
    assert "数据收盘: 2026-10-09 00:00 UTC / 北京时间 2026-10-09 08:00" in message
    assert "建议执行: 北京时间 2026-10-09 11:00（UTC 2026-10-09 03:00，T+1 +3h）" in message
    assert "名义上限 1.25x" in message


def test_format_derivatives_message_show_trades_notional_and_margin() -> None:
    from scripts.send_derivatives_signal import format_derivatives_message

    message = format_derivatives_message(
        _book(),
        signal_date=pd.Timestamp("2026-10-08", tz="UTC"),
        execution_hint=pd.Timestamp("2026-10-09 03:00", tz="UTC"),
    )

    assert "今日调仓（按权益 1000.00 USDT）:" in message
    assert "  BUY NEAR 名义 +144.70 USDT（+14.47pp 权重）" in message
    assert "SELL" not in message
    assert "  NEAR 名义 776.80 USDT（77.68%）· 参考隔离保证金 388.40 USDT" in message
    assert "  ZCASH 名义 213.80 USDT（21.38%）· 参考隔离保证金 106.90 USDT" in message
    assert "合计名义 990.60 USDT（99.06% 权益，上限 125%）" in message
    assert "占用隔离保证金 495.30 USDT（49.53%） · 剩余可用 504.70 USDT" in message


def test_format_derivatives_message_flags_stale_execution() -> None:
    from scripts.send_derivatives_signal import format_derivatives_message

    message = format_derivatives_message(
        _book(),
        signal_date=pd.Timestamp("2026-10-08", tz="UTC"),
        execution_hint=pd.Timestamp("2026-10-09 03:00", tz="UTC"),
        now=pd.Timestamp("2026-10-09 15:38", tz="UTC"),
    )

    assert "该执行时点已过去" in message
    assert "请勿追单" in message


def test_format_derivatives_message_reports_no_trade_when_book_is_unchanged() -> None:
    from scripts.send_derivatives_signal import format_derivatives_message

    book = _book()
    book["change_weight"] = 0.0
    book["change_notional_per_1k"] = 0.0

    message = format_derivatives_message(
        book,
        signal_date=pd.Timestamp("2026-10-08", tz="UTC"),
        execution_hint=pd.Timestamp("2026-10-09 03:00", tz="UTC"),
    )

    assert "  今日无需调仓" in message


def test_load_latest_targets_picks_last_signal_date(tmp_path) -> None:
    from scripts.send_derivatives_signal import load_latest_targets

    path = tmp_path / "oos_targets.csv"
    frame = pd.concat([_book(), _book().assign(signal_date="2026-10-09 00:00:00+00:00")])
    frame.to_csv(path, index=False)

    signal_date, execution_hint, book = load_latest_targets(path)

    assert signal_date == pd.Timestamp("2026-10-09", tz="UTC")
    assert execution_hint == pd.Timestamp("2026-10-09 03:00", tz="UTC")
    assert len(book) == 2


def test_load_latest_targets_rejects_missing_columns(tmp_path) -> None:
    from scripts.send_derivatives_signal import load_latest_targets

    path = tmp_path / "oos_targets.csv"
    pd.DataFrame({"signal_date": ["2026-10-08"]}).to_csv(path, index=False)

    with pytest.raises(SystemExit):
        load_latest_targets(path)
