export type ChampionSummary = {
  strategy: string;
  window_start: string;
  window_end: string;
  min_history_days?: number;
  min_daily_dollar_volume?: number;
  leader_pool?: string;
  rebalance_frequency?: string;
  regime_mode?: string;
  risk_off_asset?: string;
  initial_asset?: string;
  btc_stop_lookback_days?: number;
  btc_stop_confirm_days?: number;
  weight_momentum_rank?: number;
  weight_ret_21_rank?: number;
  weight_ret_42_rank?: number;
  weight_near_high_rank?: number;
  multiple: number;
  total_return?: number;
  cagr: number;
  sharpe: number;
  max_drawdown: number;
  annualized_turnover: number;
  monthly_win_rate: number;
  ending_equity: number;
};

export type StrategySummary = {
  strategy: string;
  multiple: number;
  cagr: number;
  sharpe: number;
  max_drawdown: number;
  annualized_turnover?: number;
  monthly_win_rate?: number;
};

export type SeriesPoint = {
  date: string;
  value: number;
};

export type SelectionHistoryRow = {
  rebalance_date: string;
  coin_id: string;
  coin_rank: number;
  coin_score?: number;
  coin_weight: number;
};

export type OverviewPayload = {
  champion: ChampionSummary;
  top_strategies: StrategySummary[];
  equity_curve: SeriesPoint[];
  daily_returns: SeriesPoint[];
  selection_history: SelectionHistoryRow[];
};

export type RunStatus = {
  run_id: string;
  status: "completed" | "failed";
  name: string;
  summary: Record<string, string | number | null>;
  error?: string | null;
};

export const fallbackOverview: OverviewPayload = {
  champion: {
    strategy: "MOMENTUM_LEAD_TOP1_ALL_14D_STOP11_CONFIRM2_BTC_PARK",
    window_start: "2022-11-21",
    window_end: "2026-04-21",
    min_history_days: 30,
    min_daily_dollar_volume: 1_000_000,
    rebalance_frequency: "14D",
    regime_mode: "always_on",
    risk_off_asset: "BTC",
    btc_stop_lookback_days: 11,
    btc_stop_confirm_days: 2,
    weight_momentum_rank: 0.607681,
    weight_ret_21_rank: 0.268948,
    weight_ret_42_rank: 0.017319,
    weight_near_high_rank: 0.106052,
    multiple: 236.999833,
    total_return: 235.999833,
    cagr: 3.949231,
    sharpe: 2.293786,
    max_drawdown: -0.507875,
    annualized_turnover: 37.801204,
    monthly_win_rate: 0.619048,
    ending_equity: 23_699_983.3,
  },
  top_strategies: [
    { strategy: "MOMENTUM_LEAD_TOP1_ALL_14D_STOP11_CONFIRM2_BTC_PARK", multiple: 236.999833, cagr: 3.949231, sharpe: 2.293786, max_drawdown: -0.507875 },
    { strategy: "BTC_BH__always_on", multiple: 4.404973, cagr: 0.542882, sharpe: 1.155328, max_drawdown: -0.496258 },
    { strategy: "TOP20_MOM_top8_biweekly__bull_only", multiple: 3.141124, cagr: 0.397595, sharpe: 0.920237, max_drawdown: -0.477837 },
  ],
  equity_curve: [
    { date: "2022-11-21", value: 100_000 },
    { date: "2023-06-01", value: 420_000 },
    { date: "2024-01-01", value: 1_950_000 },
    { date: "2024-08-01", value: 5_600_000 },
    { date: "2025-03-01", value: 12_100_000 },
    { date: "2026-04-21", value: 23_699_983 },
  ],
  daily_returns: [
    { date: "2022-11-21", value: 0 },
    { date: "2023-06-01", value: 0.012 },
    { date: "2024-01-01", value: -0.021 },
    { date: "2024-08-01", value: 0.018 },
    { date: "2025-03-01", value: 0.009 },
    { date: "2026-04-21", value: 0.004 },
  ],
  selection_history: [
    { rebalance_date: "2025-12-01", coin_id: "bitcoin", coin_rank: 1, coin_score: 0.92, coin_weight: 1 },
    { rebalance_date: "2026-01-12", coin_id: "solana", coin_rank: 1, coin_score: 0.89, coin_weight: 1 },
    { rebalance_date: "2026-03-09", coin_id: "hyperliquid", coin_rank: 1, coin_score: 0.94, coin_weight: 1 },
  ],
};

export function buildApiUrl(path: string, base = import.meta.env.VITE_ATLAS20_API_BASE ?? "/api") {
  const cleanBase = base.replace(/\/+$/, "");
  const cleanPath = path.replace(/^\/+/, "");
  return `${cleanBase}/${cleanPath}`;
}

async function requestJson<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(buildApiUrl(path), init);
  if (!response.ok) {
    throw new Error(`Atlas20 API request failed: ${response.status}`);
  }
  return response.json() as Promise<T>;
}

export function getOverview() {
  return requestJson<OverviewPayload>("/overview");
}

export function getOptions() {
  return requestJson<Record<string, unknown>>("/options");
}

export function runBacktest(payload: unknown) {
  return requestJson<RunStatus>("/backtests/run", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
}
