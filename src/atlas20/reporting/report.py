"""CSV export and markdown report generation."""

from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import time

import pandas as pd

from atlas20.backtest.engine import BacktestResult
from atlas20.config import ResearchConfig


SAFE_STRATEGY_NAME = re.compile(r"^[A-Za-z0-9_]+$")
# Windows reserved device basenames — block to ensure cross-platform safety.
WINDOWS_RESERVED_NAMES = frozenset(
    {"CON", "PRN", "AUX", "NUL"}
    | {f"COM{i}" for i in range(1, 10)}
    | {f"LPT{i}" for i in range(1, 10)}
)
SELECTION_HISTORY_COLUMNS = (
    "rebalance_date",
    "strategy",
    "coin_id",
    "coin_rank",
    "coin_score",
    "coin_weight",
)


def dataframe_to_markdown(
    df: pd.DataFrame,
    percent_columns: set[str] | None = None,
    number_columns: set[str] | None = None,
) -> str:
    """Render a compact markdown table without external dependencies."""
    formatted = df.copy()
    percent_columns = percent_columns or set()
    number_columns = number_columns or set()

    for column in formatted.columns:
        if not pd.api.types.is_numeric_dtype(formatted[column]):
            continue
        if column in percent_columns:
            formatted[column] = formatted[column].map(lambda x: f"{x:.2%}" if pd.notna(x) else "")
        elif column in number_columns:
            formatted[column] = formatted[column].map(lambda x: f"{x:,.2f}" if pd.notna(x) else "")
        else:
            formatted[column] = formatted[column].map(lambda x: f"{x:,.4f}" if pd.notna(x) else "")
    header = "| " + " | ".join([str(df.index.name or "index"), *map(str, formatted.columns)]) + " |"
    sep = "| " + " | ".join(["---"] * (len(formatted.columns) + 1)) + " |"
    rows = []
    for idx, row in formatted.iterrows():
        rows.append("| " + " | ".join([str(idx), *map(str, row.tolist())]) + " |")
    return "\n".join([header, sep, *rows])


def _safe_strategy_name(strategy_name: str) -> str:
    if not SAFE_STRATEGY_NAME.match(strategy_name):
        raise ValueError(f"Strategy name must be filesystem-safe: {strategy_name}")
    if strategy_name.upper() in WINDOWS_RESERVED_NAMES:
        raise ValueError(f"Strategy name conflicts with Windows reserved device name: {strategy_name}")
    return strategy_name


def _validate_strategy_names(results: dict[str, BacktestResult]) -> None:
    if not results:
        raise ValueError("export_result_tables requires at least one BacktestResult")
    seen_lower: dict[str, str] = {}
    for strategy_name in results:
        _safe_strategy_name(strategy_name)
        lower = strategy_name.lower()
        if lower in seen_lower and seen_lower[lower] != strategy_name:
            raise ValueError(
                f"Strategy name collision on case-insensitive filesystem: "
                f"{seen_lower[lower]!r} vs {strategy_name!r}"
            )
        seen_lower[lower] = strategy_name


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _utc_iso_from_timestamp(timestamp: float) -> str:
    return datetime.fromtimestamp(timestamp, timezone.utc).isoformat().replace("+00:00", "Z")


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _code_commit() -> str:
    try:
        completed = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=Path.cwd(),
            capture_output=True,
            check=True,
            text=True,
            timeout=5,
        )
        commit = completed.stdout.strip()
        if commit:
            return commit
    except (OSError, subprocess.SubprocessError):
        pass
    return os.environ.get("ATLAS20_CODE_COMMIT", "unknown")


def _pipeline_version() -> str:
    try:
        import atlas20

        return str(getattr(atlas20, "__version__", "0.1.0"))
    except ImportError:
        return "0.1.0"


def _config_metadata() -> tuple[str, str]:
    config_path_text = os.environ.get("ATLAS20_CONFIG_PATH", "config/base.yaml")
    config_path = Path(config_path_text)
    resolved_path = config_path if config_path.is_absolute() else Path.cwd() / config_path
    try:
        config_sha256 = _sha256_file(resolved_path)
    except FileNotFoundError:
        config_sha256 = "unknown"
    return config_path.as_posix(), config_sha256


def _data_snapshot() -> dict[str, str]:
    raw_dir = Path(os.environ.get("ATLAS20_DATA_RAW_DIR", "data/raw"))
    raw_dir = raw_dir if raw_dir.is_absolute() else Path.cwd() / raw_dir
    if not raw_dir.exists():
        return {}

    snapshot: dict[str, str] = {}
    for provider_dir in sorted(path for path in raw_dir.iterdir() if path.is_dir()):
        newest_file: Path | None = None
        newest_mtime = -1.0
        for path in provider_dir.rglob("*"):
            if not path.is_file():
                continue
            mtime = path.stat().st_mtime
            if mtime > newest_mtime:
                newest_file = path
                newest_mtime = mtime
        if newest_file is not None:
            snapshot[provider_dir.name] = _utc_iso_from_timestamp(newest_mtime)
    return snapshot


def _artifact_kind(path: Path) -> str:
    if path.parts and path.parts[0] == "weights":
        return "weights"
    mapping = {
        "strategy_summary.csv": "summary",
        "yearly_returns.csv": "yearly_returns",
        "regime_performance.csv": "regime_performance",
        "daily_returns.csv": "daily_returns",
        "equity_curves.csv": "equity_curves",
        "drawdowns.csv": "drawdowns",
        "turnover_summary.csv": "turnover",
        "selection_history.csv": "selection_history",
    }
    return mapping.get(path.name, path.suffix.lstrip(".") or "file")


def _artifact_rows(report_dir: Path) -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    for path in sorted(report_dir.rglob("*")):
        if not path.is_file() or path.name == "manifest.json":
            continue
        relative_path = path.relative_to(report_dir)
        rows.append(
            {
                "kind": _artifact_kind(relative_path),
                "path": relative_path.as_posix(),
                "size": path.stat().st_size,
                "sha256": _sha256_file(path),
            }
        )
    return rows


def _write_manifest(report_dir: Path) -> None:
    config_path, config_sha256 = _config_metadata()
    manifest = {
        "config_path": config_path,
        "config_sha256": config_sha256,
        "code_commit": _code_commit(),
        "pipeline_version": _pipeline_version(),
        "data_snapshot": _data_snapshot(),
        "generated_at": _utc_now_iso(),
        "artifacts": _artifact_rows(report_dir),
    }
    (report_dir / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")


def _build_selection_history(results: dict[str, BacktestResult]) -> pd.DataFrame:
    rows: list[dict[str, object]] = []
    for strategy_name, result in results.items():
        _safe_strategy_name(strategy_name)
        if result.rebalance_targets.empty:
            continue

        targets = result.rebalance_targets
        if not targets.index.is_unique:
            # Duplicate rebalance dates indicate engine inconsistency; collapse
            # deterministically by taking the last entry for each date.
            targets = targets[~targets.index.duplicated(keep="last")]

        for rebalance_date, raw_target_row in targets.sort_index().iterrows():
            target_row = pd.to_numeric(raw_target_row, errors="coerce").fillna(0.0)
            selected = target_row[target_row > 0]
            if selected.empty:
                continue

            # Use rebalance_targets weights directly. result.weights may reflect
            # the previous portfolio on the same date (targets apply on next
            # trading day), and may also miss the freshly-selected coins.
            selection = selected.sort_values(ascending=False, kind="stable")
            # Stable sort already breaks ties by original index order; for full
            # determinism resort by (weight desc, coin_id asc).
            selection_df = selection.rename("coin_weight").reset_index().rename(
                columns={"index": "coin_id"}
            )
            selection_df["coin_id"] = selection_df["coin_id"].astype(str)
            selection_df = selection_df.sort_values(
                ["coin_weight", "coin_id"], ascending=[False, True], kind="stable"
            ).reset_index(drop=True)

            for rank, row in enumerate(selection_df.itertuples(index=False), start=1):
                rows.append(
                    {
                        "rebalance_date": rebalance_date,
                        "strategy": strategy_name,
                        "coin_id": row.coin_id,
                        "coin_rank": rank,
                        "coin_score": pd.NA,
                        "coin_weight": float(row.coin_weight),
                    }
                )

    history = pd.DataFrame(rows, columns=SELECTION_HISTORY_COLUMNS)
    if history.empty:
        return history
    return history.sort_values(["rebalance_date", "strategy", "coin_rank"]).reset_index(drop=True)


def _write_result_tables(
    results: dict[str, BacktestResult],
    summary: pd.DataFrame,
    yearly_returns: pd.DataFrame,
    regime_performance: pd.DataFrame,
    report_dir: Path,
) -> None:
    summary.to_csv(report_dir / "strategy_summary.csv")
    yearly_returns.to_csv(report_dir / "yearly_returns.csv")
    regime_performance.to_csv(report_dir / "regime_performance.csv", index=False)

    pd.DataFrame({name: result.daily_returns for name, result in results.items()}).to_csv(report_dir / "daily_returns.csv")
    pd.DataFrame({name: result.equity_curve for name, result in results.items()}).to_csv(report_dir / "equity_curves.csv")
    pd.DataFrame({name: result.drawdown for name, result in results.items()}).to_csv(report_dir / "drawdowns.csv")
    turnover = pd.DataFrame(
        {
            "annualized_turnover": summary["annualized_turnover"],
            "avg_turnover_per_rebalance": summary["avg_turnover_per_rebalance"],
            "average_holdings": summary["average_holdings"],
        }
    )
    turnover.to_csv(report_dir / "turnover_summary.csv")

    weights_dir = report_dir / "weights"
    weights_dir.mkdir(parents=True, exist_ok=True)
    for strategy_name, result in results.items():
        safe_strategy_name = _safe_strategy_name(strategy_name)
        result.weights.to_csv(weights_dir / f"{safe_strategy_name}.csv")

    _build_selection_history(results).to_csv(report_dir / "selection_history.csv", index=False)


def _temporary_report_dir(report_dir: Path) -> Path:
    return report_dir.with_name(f"{report_dir.name}.tmp_{os.getpid()}_{time.time_ns()}")


def _remove_path(path: Path) -> None:
    if path.is_symlink() or path.is_file():
        path.unlink()
    elif path.exists():
        shutil.rmtree(path)


def _publish_report_dir(tmp_dir: Path, report_dir: Path) -> None:
    backup_dir: Path | None = None
    report_dir.parent.mkdir(parents=True, exist_ok=True)

    if report_dir.exists() or report_dir.is_symlink():
        backup_dir = report_dir.with_name(f"{report_dir.name}.bak_{os.getpid()}_{time.time_ns()}")
        _remove_path(backup_dir)
        shutil.move(str(report_dir), str(backup_dir))

    try:
        shutil.move(str(tmp_dir), str(report_dir))
    except Exception:
        if report_dir.exists() or report_dir.is_symlink():
            _remove_path(report_dir)
        if backup_dir is not None and backup_dir.exists():
            shutil.move(str(backup_dir), str(report_dir))
        raise
    else:
        if backup_dir is not None:
            _remove_path(backup_dir)


def _report_root(report_dir: Path) -> Path:
    for path in (report_dir, *report_dir.parents):
        if path.name == "reports":
            return path
    raise ValueError(
        f"report_dir must be located under a 'reports/' ancestor; got {report_dir!s}. "
        f"Atomic latest.txt publication requires a known reports root."
    )


def _write_latest_pointer(report_dir: Path) -> None:
    report_root = _report_root(report_dir)
    relative_report_dir = report_dir.relative_to(report_root)
    pointer_path = report_root / "latest.txt"
    tmp_pointer_path = pointer_path.with_name(f"{pointer_path.name}.tmp_{os.getpid()}_{time.time_ns()}")
    tmp_pointer_path.write_text(relative_report_dir.as_posix() + "\n", encoding="utf-8")
    tmp_pointer_path.replace(pointer_path)


def export_result_tables(
    results: dict[str, BacktestResult],
    summary: pd.DataFrame,
    yearly_returns: pd.DataFrame,
    regime_performance: pd.DataFrame,
    report_dir: Path,
) -> None:
    """Export major result tables, weights, selection history, and manifest.

    Single-writer assumption: this function is not safe to call concurrently
    with itself targeting the same ``report_dir`` — concurrent invocations may
    race during the publish step. Readers should go through
    ``reports/latest.txt`` rather than poking ``report_dir`` directly.

    Raises:
        ValueError: ``results`` is empty, contains a filesystem-unsafe
            strategy name, or ``report_dir`` is not under a ``reports/``
            ancestor (required for atomic ``latest.txt`` publication).
    """
    report_dir = Path(report_dir)
    _validate_strategy_names(results)
    _report_root(report_dir)  # eagerly validate the reports/ ancestor
    tmp_dir = _temporary_report_dir(report_dir)
    try:
        tmp_dir.mkdir(parents=True, exist_ok=False)
        _write_result_tables(results, summary, yearly_returns, regime_performance, tmp_dir)
        _write_manifest(tmp_dir)
        _publish_report_dir(tmp_dir, report_dir)
        _write_latest_pointer(report_dir)
    except Exception:
        if tmp_dir.exists():
            _remove_path(tmp_dir)
        raise



def _pick_best(summary: pd.DataFrame, prefix: str) -> tuple[str, pd.Series]:
    subset = summary[summary.index.to_series().str.startswith(prefix)]
    if subset.empty:
        return "N/A", pd.Series(dtype=float)
    best_name = subset.sort_values(["sharpe", "cagr"], ascending=False).index[0]
    return best_name, subset.loc[best_name]



def build_markdown_report(
    config: ResearchConfig,
    summary: pd.DataFrame,
    yearly_returns: pd.DataFrame,
    regime_performance: pd.DataFrame,
    output_path: Path,
) -> str:
    """Create the final markdown research report."""
    btc = summary.loc["BTC_BH__always_on"]
    eq = summary.loc["TOP20_EQ__always_on"]
    best_mom_name, best_mom = _pick_best(summary, "TOP20_MOM_")
    best_sector_name, best_sector = _pick_best(summary, "TOP20_SECTOR_")
    bull_subset = summary[summary.index.to_series().str.endswith("__bull_only")]
    always_subset = summary[summary.index.to_series().str.endswith("__always_on")]
    avg_bull_sharpe = bull_subset["sharpe"].mean() if not bull_subset.empty else 0.0
    avg_always_sharpe = always_subset["sharpe"].mean() if not always_subset.empty else 0.0

    def verdict(condition: bool) -> str:
        return "Yes" if condition else "No"

    top_summary = summary.head(12).copy()
    yearly_head = yearly_returns.tail(5).copy()
    regime_head = regime_performance.pivot(index="strategy", columns="regime", values="annualized_return").sort_index().head(12)

    summary_percent_cols = {"cagr", "annualized_volatility", "max_drawdown"}
    summary_number_cols = {"sharpe", "sortino", "calmar", "annualized_turnover", "average_holdings"}
    yearly_percent_cols = set(yearly_head.columns)
    regime_percent_cols = set(regime_head.columns)

    text = f"""# {config.project_name} Research Report

## Scope

- Universe: top-{config.universe.universe_size} non-stablecoin crypto assets by point-in-time market-cap proxy.
- Portfolio construction: equal weight, momentum rotation, and sector rotation.
- Rebalancing tested: monthly and biweekly.
- Regime overlays tested: always-on and bull-only.
- Frictions: {config.frictions.fee_bps:.1f} bps fee + {config.frictions.slippage_bps:.1f} bps slippage.

## Executive summary

- Best momentum variant: **{best_mom_name}**
- Best sector variant: **{best_sector_name}**
- BTC benchmark CAGR: **{btc['cagr']:.2%}**
- Equal-weight benchmark CAGR: **{eq['cagr']:.2%}**

## Answers to the required questions

1. **Does top-20 momentum rotation outperform BTC buy-and-hold?**
   - Verdict: **{verdict(not best_mom.empty and best_mom['cagr'] > btc['cagr'])}** on CAGR.
   - Best momentum CAGR / Sharpe: **{best_mom.get('cagr', 0.0):.2%} / {best_mom.get('sharpe', 0.0):.2f}**
   - BTC CAGR / Sharpe: **{btc['cagr']:.2%} / {btc['sharpe']:.2f}**

2. **Does sector rotation outperform simple top-20 equal weight?**
   - Verdict: **{verdict(not best_sector.empty and best_sector['sharpe'] > eq['sharpe'])}** on Sharpe.
   - Best sector CAGR / Sharpe: **{best_sector.get('cagr', 0.0):.2%} / {best_sector.get('sharpe', 0.0):.2f}**
   - Equal-weight CAGR / Sharpe: **{eq['cagr']:.2%} / {eq['sharpe']:.2f}**

3. **Does the bull-market filter improve risk-adjusted returns?**
   - Verdict: **{verdict(avg_bull_sharpe > avg_always_sharpe)}** on average Sharpe across tested variants.
   - Average bull-only Sharpe: **{avg_bull_sharpe:.2f}**
   - Average always-on Sharpe: **{avg_always_sharpe:.2f}**

4. **Is the extra complexity of sector rotation justified?**
   - Verdict: **{verdict(not best_sector.empty and best_sector['sharpe'] > eq['sharpe'] and best_sector['max_drawdown'] >= eq['max_drawdown'])}**
   - Interpretation: sector rotation is only justified if it improves Sharpe meaningfully without materially worsening implementation risk.

5. **What are the main practical risks and data limitations?**
   - Historical market-cap rankings use direct CoinGecko daily market caps for the recent window and a price-scaled proxy anchor before that because free long-history point-in-time market-cap series are limited.
   - Sector labels come from a current metadata snapshot plus manual overrides, so they are not perfectly point-in-time.
   - Candidate coverage is reduced-survivorship rather than perfect-survivorship-free; the project uses current large caps plus a curated legacy list.
   - CryptoCompare symbol-level history can still be imperfect for rebrands, ticker collisions, or synthetic duplicates, although the pipeline now validates 365-day overlap against CoinGecko and exports `data/processed/data_quality.csv`.

## Strategy comparison table

{dataframe_to_markdown(top_summary[["cagr", "annualized_volatility", "sharpe", "sortino", "max_drawdown", "calmar", "annualized_turnover", "average_holdings"]], percent_columns=summary_percent_cols, number_columns=summary_number_cols)}

## Recent yearly return table

{dataframe_to_markdown(yearly_head, percent_columns=yearly_percent_cols)}

## Performance by regime snapshot

{dataframe_to_markdown(regime_head.fillna(0.0), percent_columns=regime_percent_cols)}

## Interpretation notes

- Market cap is used strictly for **universe selection**, not weighting.
- Rotation strategies use **equal-weight allocations** after signal selection.
- A strong result for momentum generally indicates relative-strength persistence inside large and liquid crypto assets.
- A weak result for sector rotation usually indicates that its extra selection layer does not compensate for turnover and classification noise.

## Next recommended improvements

1. Replace proxy market caps with a paid or archived point-in-time market-cap dataset.
2. Add exchange-level liquidity filters and price-source cross checks.
3. Add daily regime-trigger exits as an overlay rather than rebalance-date-only gating.
4. Add transaction-cost sensitivity sweeps and bootstrap significance tests.
5. Expand sector mapping with time-aware overrides for major token rebrands and protocol migrations.
"""
    output_path.write_text(text, encoding="utf-8")
    return text
