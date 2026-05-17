import type { ChampionSummary } from "../../lib/api";

export type DashboardFormState = {
  window: {
    start_date: string;
    end_date: string;
  };
  strategy: {
    family: "momentum_lead";
    top_n: number;
    frequency: string;
  };
  universe: {
    min_history_days: number;
    min_daily_dollar_volume: number;
    exclude_btc: boolean;
  };
  risk: {
    mode: string;
    stop_lookback_days: number;
    confirm_days: number;
    risk_off_asset: "bitcoin" | "ethereum" | "cash";
  };
  weights: {
    momentum_rank: number;
    ret_21_rank: number;
    ret_42_rank: number;
    near_high_rank: number;
  };
};

function parseNumber(pattern: RegExp, value: string, fallback: number) {
  const match = value.match(pattern);
  return match ? Number(match[1]) : fallback;
}

function parseFrequency(strategy: string) {
  const match = strategy.match(/_(\d+D)_/);
  return match?.[1] ?? "14D";
}

function normalizeRiskOffAsset(value: string | undefined): "bitcoin" | "ethereum" | "cash" {
  const normalized = value?.toLowerCase();
  if (normalized === "btc" || normalized === "bitcoin") return "bitcoin";
  if (normalized === "eth" || normalized === "ethereum") return "ethereum";
  return "cash";
}

function parseRiskMode(strategy: string) {
  if (strategy.includes("_ALL_")) return "always_on";
  if (strategy.includes("_BULL_")) return "bull_only";
  return "always_on";
}

export function championToFormState(champion: ChampionSummary): DashboardFormState {
  return {
    window: {
      start_date: champion.window_start,
      end_date: champion.window_end,
    },
    strategy: {
      family: "momentum_lead",
      top_n: parseNumber(/TOP(\d+)/, champion.strategy, 1),
      frequency: champion.rebalance_frequency ?? parseFrequency(champion.strategy),
    },
    universe: {
      min_history_days: champion.min_history_days ?? 30,
      min_daily_dollar_volume: champion.min_daily_dollar_volume ?? 1_000_000,
      exclude_btc: champion.strategy.includes("_EXBTC_"),
    },
    risk: {
      mode: champion.regime_mode ?? parseRiskMode(champion.strategy),
      stop_lookback_days: champion.btc_stop_lookback_days ?? parseNumber(/STOP(\d+)/, champion.strategy, 11),
      confirm_days: champion.btc_stop_confirm_days ?? parseNumber(/CONFIRM(\d+)/, champion.strategy, 2),
      risk_off_asset: normalizeRiskOffAsset(champion.risk_off_asset ?? (champion.strategy.includes("BTC_PARK") ? "BTC" : "cash")),
    },
    weights: {
      momentum_rank: champion.weight_momentum_rank ?? 0.607681,
      ret_21_rank: champion.weight_ret_21_rank ?? 0.268948,
      ret_42_rank: champion.weight_ret_42_rank ?? 0.017319,
      near_high_rank: champion.weight_near_high_rank ?? 0.106052,
    },
  };
}
