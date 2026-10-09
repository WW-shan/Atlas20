from __future__ import annotations

import json
from pathlib import Path

import pytest


def test_format_signal_message_labels_utc_close_and_t_plus_one_execution() -> None:
    from scripts.send_telegram_signal import format_signal_message

    message = format_signal_message(_payload())

    assert "信号日期（UTC日线）: 2026-10-08" in message
    assert "数据收盘: 2026-10-08 23:59 UTC / 北京时间 2026-10-09 08:00" in message
    assert "执行日期: 2026-10-09（T+1）" in message


def test_format_signal_message_reports_target_current_and_rebalance() -> None:
    from scripts.send_telegram_signal import format_signal_message

    payload = {
        "as_of": "2026-10-08",
        "latest_target_date": "2026-10-08",
        "trade_required": True,
        "btc_gate_open": True,
        "gross_exposure": 0.62,
        "targets": {"near": 0.62},
        "current_weights": {"near": 0.46},
        "trial_id": "PR2026-10-H5",
        "cost_bps": 20.0,
    }

    message = format_signal_message(payload)

    assert "Atlas20 H5 每日信号" in message
    assert "信号日期（UTC日线）: 2026-10-08" in message
    assert "Trade required: YES" in message
    assert "目标持仓（调仓后）:" in message
    assert "  NEAR 62.00%" in message
    assert "  CASH 38.00%" in message
    assert "模型当前持仓:" not in message
    assert "今日操作（按总资金 1000.00 USDT）:" in message
    assert "  BUY NEAR 160.00 USDT (+16.00pp)" in message
    assert "信号仅供参考，请手动执行。" in message



def _payload(**overrides: object) -> dict[str, object]:
    payload: dict[str, object] = {
        "as_of": "2026-10-08",
        "latest_target_date": "2026-10-08",
        "trade_required": True,
        "btc_gate_open": True,
        "gross_exposure": 0.62,
        "targets": {"near": 0.62},
        "current_weights": {"near": 0.46},
        "trial_id": "PR2026-10-H5",
        "cost_bps": 20.0,
    }
    payload.update(overrides)
    return payload


def _write_signal(path: Path, payload: dict[str, object] | None = None) -> None:
    path.write_text(json.dumps(payload or _payload()), encoding="utf-8")


def test_format_signal_message_reports_usdt_operations_and_holdings() -> None:
    from scripts.send_telegram_signal import format_signal_message

    message = format_signal_message(_payload(), capital=1000.0)

    assert "今日操作（按总资金 1000.00 USDT）:" in message
    assert "  BUY NEAR 160.00 USDT (+16.00pp)" in message
    assert "  NEAR 62.00% / 620.00 USDT" in message
    assert "  CASH 38.00% / 380.00 USDT" in message
    assert "模型当前持仓:" not in message


def test_format_signal_message_reports_sell_amount() -> None:
    from scripts.send_telegram_signal import format_signal_message

    message = format_signal_message(
        _payload(targets={"near": 0.20}, current_weights={"near": 0.60}),
        capital=1000.0,
    )

    assert "  SELL NEAR 400.00 USDT (-40.00pp)" in message


def test_format_signal_message_says_no_rebalance_when_weights_match() -> None:
    from scripts.send_telegram_signal import format_signal_message

    message = format_signal_message(
        _payload(targets={"near": 0.62}, current_weights={"near": 0.62})
    )

    assert "  今日无需调仓" in message
    assert "BUY NEAR" not in message
    assert "SELL NEAR" not in message


def test_format_signal_message_omits_unchanged_coin_from_operations() -> None:
    from scripts.send_telegram_signal import format_signal_message

    message = format_signal_message(
        _payload(targets={"near": 0.62}, current_weights={"near": 0.62})
    )

    assert "今日无需调仓" in message
    assert "HOLD NEAR" not in message


def test_format_signal_message_does_not_rebalance_on_non_trade_days() -> None:
    from scripts.send_telegram_signal import format_signal_message

    message = format_signal_message(
        _payload(
            trade_required=False,
            targets={"near": 0.62},
            current_weights={"near": 0.46},
        )
    )

    assert "  今日无需调仓" in message
    assert "BUY NEAR" not in message
    assert "SELL NEAR" not in message


def test_format_signal_message_rejects_gross_above_one() -> None:
    from scripts.send_telegram_signal import format_signal_message

    with pytest.raises(ValueError, match="exceed 100%"):
        format_signal_message(
            _payload(targets={"near": 1.01}, current_weights={})
        )


def test_format_signal_message_rejects_non_finite_weight() -> None:
    from scripts.send_telegram_signal import format_signal_message

    with pytest.raises(ValueError, match="finite"):
        format_signal_message(
            _payload(targets={"near": float("nan")}, current_weights={})
        )


def test_main_skips_already_sent_same_as_of(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    import scripts.send_telegram_signal as sender

    signal_path = tmp_path / "latest_signal.json"
    state_path = tmp_path / "state.json"
    _write_signal(signal_path)
    state_path.write_text(
        json.dumps(
            {"sent_keys": {"12345": "PR2026-10-H5|2026-10-08"}}
        ),
        encoding="utf-8",
    )
    calls: list[str] = []

    def fake_send(message: str, **kwargs: object) -> None:
        calls.append(str(kwargs["chat_id"]))

    monkeypatch.setattr(sender, "send_telegram_message", fake_send)
    monkeypatch.setenv("ATLAS20_TELEGRAM_CHAT_ID", "12345")

    sender.main(["--signal-file", str(signal_path), "--state-file", str(state_path)])

    assert calls == []


def test_main_dry_run_does_not_require_credentials_or_write_state(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    import scripts.send_telegram_signal as sender

    signal_path = tmp_path / "latest_signal.json"
    state_path = tmp_path / "state.json"
    _write_signal(signal_path)
    monkeypatch.delenv("ATLAS20_TELEGRAM_BOT_TOKEN", raising=False)
    monkeypatch.delenv("ATLAS20_TELEGRAM_CHAT_ID", raising=False)

    sender.main(
        [
            "--signal-file",
            str(signal_path),
            "--state-file",
            str(state_path),
            "--dry-run",
        ]
    )

    assert "Atlas20 H5 每日信号" in capsys.readouterr().out
    assert not state_path.exists()


def test_main_sends_to_each_chat_id(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    import scripts.send_telegram_signal as sender

    signal_path = tmp_path / "latest_signal.json"
    state_path = tmp_path / "state.json"
    _write_signal(signal_path)
    calls: list[str] = []

    def fake_send(message: str, **kwargs: object) -> None:
        calls.append(str(kwargs["chat_id"]))

    monkeypatch.setattr(sender, "send_telegram_message", fake_send)
    monkeypatch.setenv("ATLAS20_TELEGRAM_BOT_TOKEN", "test-token")
    monkeypatch.setenv("ATLAS20_TELEGRAM_CHAT_ID", "12345, 67890")

    sender.main(["--signal-file", str(signal_path), "--state-file", str(state_path)])

    assert calls == ["12345", "67890"]
    state = json.loads(state_path.read_text(encoding="utf-8"))
    assert state["sent_keys"] == {
        "12345": "PR2026-10-H5|2026-10-08",
        "67890": "PR2026-10-H5|2026-10-08",
    }


def test_main_resends_only_missing_chat_id(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    import scripts.send_telegram_signal as sender

    signal_path = tmp_path / "latest_signal.json"
    state_path = tmp_path / "state.json"
    _write_signal(signal_path)
    state_path.write_text(
        json.dumps({"sent_keys": {"12345": "PR2026-10-H5|2026-10-08"}}),
        encoding="utf-8",
    )
    calls: list[str] = []

    def fake_send(message: str, **kwargs: object) -> None:
        calls.append(str(kwargs["chat_id"]))

    monkeypatch.setattr(sender, "send_telegram_message", fake_send)
    monkeypatch.setenv("ATLAS20_TELEGRAM_BOT_TOKEN", "test-token")
    monkeypatch.setenv("ATLAS20_TELEGRAM_CHAT_ID", "12345,67890")

    sender.main(["--signal-file", str(signal_path), "--state-file", str(state_path)])

    assert calls == ["67890"]


def test_main_force_sends_again_and_updates_state(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import scripts.send_telegram_signal as sender

    signal_path = tmp_path / "latest_signal.json"
    state_path = tmp_path / "state.json"
    _write_signal(signal_path)
    state_path.write_text(
        json.dumps({"last_sent_key": "PR2026-10-H5|2026-10-08"}),
        encoding="utf-8",
    )
    calls: list[tuple[str, dict[str, object]]] = []

    def fake_send(message: str, **kwargs: object) -> None:
        calls.append((message, kwargs))

    monkeypatch.setattr(sender, "send_telegram_message", fake_send)
    monkeypatch.setenv("ATLAS20_TELEGRAM_BOT_TOKEN", "test-token")
    monkeypatch.setenv("ATLAS20_TELEGRAM_CHAT_ID", "12345")

    sender.main(
        [
            "--signal-file",
            str(signal_path),
            "--state-file",
            str(state_path),
            "--force",
        ]
    )

    assert len(calls) == 1
    state = json.loads(state_path.read_text(encoding="utf-8"))
    assert state["sent_keys"]["12345"] == "PR2026-10-H5|2026-10-08"


def test_main_requires_telegram_credentials(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import scripts.send_telegram_signal as sender

    signal_path = tmp_path / "latest_signal.json"
    state_path = tmp_path / "state.json"
    _write_signal(signal_path)
    monkeypatch.delenv("ATLAS20_TELEGRAM_BOT_TOKEN", raising=False)
    monkeypatch.setenv("ATLAS20_TELEGRAM_CHAT_ID", "12345")

    with pytest.raises(SystemExit, match="ATLAS20_TELEGRAM_BOT_TOKEN"):
        sender.main(["--signal-file", str(signal_path), "--state-file", str(state_path)])


def test_main_does_not_write_state_when_send_fails(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import scripts.send_telegram_signal as sender

    signal_path = tmp_path / "latest_signal.json"
    state_path = tmp_path / "state.json"
    _write_signal(signal_path)

    def fake_send(message: str, **kwargs: object) -> None:
        raise RuntimeError("telegram down")

    monkeypatch.setattr(sender, "send_telegram_message", fake_send)
    monkeypatch.setenv("ATLAS20_TELEGRAM_BOT_TOKEN", "test-token")
    monkeypatch.setenv("ATLAS20_TELEGRAM_CHAT_ID", "12345")

    with pytest.raises(RuntimeError, match="telegram down"):
        sender.main(["--signal-file", str(signal_path), "--state-file", str(state_path)])

    assert not state_path.exists()


class _Response:
    def __init__(self, status_code: int, body: dict[str, object]) -> None:
        self.status_code = status_code
        self._body = body

    @property
    def ok(self) -> bool:
        return 200 <= self.status_code < 300

    def json(self) -> dict[str, object]:
        return self._body


def test_send_telegram_message_posts_expected_payload(monkeypatch: pytest.MonkeyPatch) -> None:
    import scripts.send_telegram_signal as sender

    calls: list[dict[str, object]] = []

    def fake_post(url: str, **kwargs: object) -> _Response:
        calls.append({"url": url, **kwargs})
        return _Response(200, {"ok": True, "result": {"message_id": 1}})

    monkeypatch.setattr(sender.requests, "post", fake_post)

    sender.send_telegram_message(
        "hello",
        token="secret-token",
        chat_id="12345",
        api_base="https://telegram.example",
    )

    assert calls == [
        {
            "url": "https://telegram.example/botsecret-token/sendMessage",
            "json": {
                "chat_id": "12345",
                "text": "hello",
                "disable_web_page_preview": True,
            },
            "timeout": 10,
        }
    ]


def test_send_telegram_message_retries_server_errors(monkeypatch: pytest.MonkeyPatch) -> None:
    import scripts.send_telegram_signal as sender

    responses = [
        _Response(500, {"ok": False, "description": "temporary"}),
        _Response(200, {"ok": True, "result": {"message_id": 1}}),
    ]
    sleeps: list[float] = []

    def fake_post(url: str, **kwargs: object) -> _Response:
        return responses.pop(0)

    monkeypatch.setattr(sender.requests, "post", fake_post)
    monkeypatch.setattr(sender.time, "sleep", sleeps.append)

    sender.send_telegram_message("hello", token="secret-token", chat_id="12345")

    assert len(sleeps) == 1


def test_send_telegram_message_redacts_token_on_failure(monkeypatch: pytest.MonkeyPatch) -> None:
    import scripts.send_telegram_signal as sender

    def fake_post(url: str, **kwargs: object) -> _Response:
        return _Response(401, {"ok": False, "description": "Unauthorized"})

    monkeypatch.setattr(sender.requests, "post", fake_post)

    with pytest.raises(RuntimeError) as exc_info:
        sender.send_telegram_message(
            "hello",
            token="super-secret-token",
            chat_id="12345",
        )

    assert "super-secret-token" not in str(exc_info.value)
    assert "HTTP 401" in str(exc_info.value)


def test_systemd_timer_runs_daily_in_utc() -> None:
    root = Path(__file__).resolve().parents[1]
    timer = (root / "ops" / "systemd" / "atlas20-telegram-signal.timer").read_text(
        encoding="utf-8"
    )
    service = (root / "ops" / "systemd" / "atlas20-telegram-signal.service").read_text(
        encoding="utf-8"
    )

    assert "OnCalendar=*-*-* 03:00:00 UTC" in timer
    assert "OnCalendar=*-*-* 07:00:00 UTC" in timer
    assert "Persistent=true" in timer
    assert "Unit=atlas20-telegram-signal.service" in timer
    assert "scripts/run_phase_momentum_live_signal.py" in service
    assert "scripts/send_telegram_signal.py" in service
    assert "launchd" not in timer.lower()
    assert "launchd" not in service.lower()
