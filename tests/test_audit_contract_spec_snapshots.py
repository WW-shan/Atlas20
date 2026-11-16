from __future__ import annotations

import json
from pathlib import Path

import pytest

from scripts.audit_contract_spec_snapshots import _compare, _load_snapshot


def _row(symbol: str, **overrides: object) -> dict[str, object]:
    row: dict[str, object] = {
        "symbol": symbol,
        "sizeMultiplier": "0.001",
        "minTradeUSDT": "5",
        "minTradeNum": "0.001",
        "fundInterval": "8",
        "pricePlace": "1",
        "priceEndStep": "1",
        "maxLever": "100",
    }
    row.update(overrides)
    return row


def _write_snapshot(path: Path, payload: object) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")
    return path


def test_snapshot_loader_accepts_list_and_symbol_keyed_dict(tmp_path: Path) -> None:
    listed = _write_snapshot(tmp_path / "list" / "contracts.json", [_row("BTCUSDT")])
    keyed = _write_snapshot(
        tmp_path / "dict" / "contracts.json", {"BTCUSDT": _row("BTCUSDT")}
    )

    list_snapshot = _load_snapshot(listed, "list")
    dict_snapshot = _load_snapshot(keyed, "dict")

    assert list_snapshot.rows["BTCUSDT"]["sizeMultiplier"] == "0.001"
    assert dict_snapshot.rows["BTCUSDT"]["minTradeUSDT"] == "5"


def test_snapshot_loader_accepts_a_captured_contracts_wrapper(tmp_path: Path) -> None:
    path = _write_snapshot(
        tmp_path / "captured.json",
        {
            "captured_at": "2026-11-16T13:00:00+00:00",
            "request_time": "2026-11-16T13:00:01+00:00",
            "contracts": [_row("BTCUSDT")],
        },
    )

    snapshot = _load_snapshot(path, "captured")

    assert snapshot.rows["BTCUSDT"]["fundInterval"] == "8"


@pytest.mark.parametrize(
    "field", ["sizeMultiplier", "minTradeUSDT", "minTradeNum", "fundInterval"]
)
def test_track_contract_spec_change_fails_the_audit(
    tmp_path: Path, field: str
) -> None:
    before = _load_snapshot(
        _write_snapshot(tmp_path / "before.json", [_row("BTCUSDT")]), "before"
    )
    after = _load_snapshot(
        _write_snapshot(
            tmp_path / "after.json",
            [_row("BTCUSDT", **{field: "changed"})],
        ),
        "after",
    )

    result = _compare(snapshots=[before, after], track_symbols=["BTCUSDT"])

    assert result["passed"] is False
    assert [(item["symbol"], item["field"]) for item in result["changes"]] == [
        ("BTCUSDT", field)
    ]


def test_contract_change_outside_the_track_does_not_fail_the_audit(
    tmp_path: Path,
) -> None:
    before = _load_snapshot(
        _write_snapshot(
            tmp_path / "before.json", [_row("BTCUSDT"), _row("SOPHUSDT")]
        ),
        "before",
    )
    after = _load_snapshot(
        _write_snapshot(
            tmp_path / "after.json",
            [
                _row("BTCUSDT"),
                _row("SOPHUSDT", fundInterval="1"),
            ],
        ),
        "after",
    )

    result = _compare(snapshots=[before, after], track_symbols=["BTCUSDT"])

    assert result["passed"] is True
    assert result["changes"] == []


def test_missing_track_symbol_in_a_snapshot_fails_the_audit(tmp_path: Path) -> None:
    before = _load_snapshot(
        _write_snapshot(tmp_path / "before.json", [_row("BTCUSDT")]), "before"
    )
    after = _load_snapshot(
        _write_snapshot(tmp_path / "after.json", [_row("ETHUSDT")]), "after"
    )

    result = _compare(snapshots=[before, after], track_symbols=["BTCUSDT"])

    assert result["passed"] is False
    assert result["missing_snapshot_symbols"] == [
        {"symbol": "BTCUSDT", "snapshots": ["before"]}
    ]


def test_identical_track_specs_pass_and_snapshot_bytes_are_identified(
    tmp_path: Path,
) -> None:
    before = _load_snapshot(
        _write_snapshot(tmp_path / "before.json", [_row("BTCUSDT")]), "before"
    )
    after = _load_snapshot(
        _write_snapshot(tmp_path / "after.json", [_row("BTCUSDT")]), "after"
    )

    result = _compare(snapshots=[before, after], track_symbols=["BTCUSDT"])

    assert result["passed"] is True
    assert all(item["sha256"] for item in result["snapshots"])


def test_max_lever_change_is_non_material_when_all_values_support_the_track(
    tmp_path: Path,
) -> None:
    before = _load_snapshot(
        _write_snapshot(
            tmp_path / "before.json", [_row("SANDUSDT", maxLever="10")]
        ),
        "before",
    )
    after = _load_snapshot(
        _write_snapshot(
            tmp_path / "after.json", [_row("SANDUSDT", maxLever="20")]
        ),
        "after",
    )

    result = _compare(
        snapshots=[before, after],
        track_symbols=["SANDUSDT"],
        required_leverage=4.0,
    )

    assert result["passed"] is True
    assert result["material_changes"] == []
    assert result["changes"] == [
        {
            "symbol": "SANDUSDT",
            "field": "maxLever",
            "values": {"before": "10", "after": "20"},
            "material": False,
            "reason": "all observed values support required 4x leverage",
        }
    ]


def test_max_lever_change_below_required_leverage_is_material(tmp_path: Path) -> None:
    before = _load_snapshot(
        _write_snapshot(
            tmp_path / "before.json", [_row("SANDUSDT", maxLever="10")]
        ),
        "before",
    )
    after = _load_snapshot(
        _write_snapshot(
            tmp_path / "after.json", [_row("SANDUSDT", maxLever="2")]
        ),
        "after",
    )

    result = _compare(
        snapshots=[before, after],
        track_symbols=["SANDUSDT"],
        required_leverage=4.0,
    )

    assert result["passed"] is False
    assert [(item["symbol"], item["field"]) for item in result["material_changes"]] == [
        ("SANDUSDT", "maxLever")
    ]


def test_max_lever_change_allows_repeated_unchanged_observations(tmp_path: Path) -> None:
    snapshots = [
        _load_snapshot(
            _write_snapshot(
                tmp_path / f"snapshot_{index}.json",
                [_row("SANDUSDT", maxLever=value)],
            ),
            f"snapshot_{index}",
        )
        for index, value in enumerate(("10", "20", "20"))
    ]

    result = _compare(
        snapshots=snapshots,
        track_symbols=["SANDUSDT"],
        required_leverage=4.0,
    )

    assert result["passed"] is True
    assert result["material_changes"] == []


def test_default_snapshots_include_the_pre_refresh_october_capture() -> None:
    import scripts.audit_contract_spec_snapshots as module

    assert Path("data/raw/bitget_derivatives/contracts.json") in (
        module.DEFAULT_SNAPSHOT_PATHS
    )


def test_default_snapshot_paths_include_every_recorded_change_point(
    tmp_path: Path, monkeypatch
) -> None:
    import scripts.audit_contract_spec_snapshots as module

    first = _write_snapshot(tmp_path / "a" / "contracts.json", [_row("BTCUSDT")])
    second = _write_snapshot(tmp_path / "b" / "contracts.json", [_row("BTCUSDT")])
    archive_a = _write_snapshot(
        tmp_path / "raw" / "contract_snapshots" / "contracts_a.json",
        {"contracts": [_row("BTCUSDT")]},
    )
    archive_b = _write_snapshot(
        tmp_path / "raw" / "contract_snapshots" / "contracts_b.json",
        {"contracts": [_row("BTCUSDT", sizeMultiplier="0.01")]},
    )
    import os

    os.utime(archive_a, (1_800_000_000, 1_800_000_000))
    os.utime(archive_b, (1_800_000_001, 1_800_000_001))
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(module, "DEFAULT_SNAPSHOT_PATHS", (first, second))
    monkeypatch.setattr(
        module,
        "DEFAULT_CURRENT_SNAPSHOT_GLOB",
        "raw/contract_snapshots/contracts_*.json",
    )

    paths = module._default_snapshot_paths()

    assert paths == [
        first,
        second,
        Path("raw/contract_snapshots/contracts_a.json"),
        Path("raw/contract_snapshots/contracts_b.json"),
    ]
