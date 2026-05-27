// ============================================================
// Atlas20 API — typed schema, fetch helpers, and fallback mocks
// SPEC §7 (data types), §8 (function registry), §9 (qk registry)
// ============================================================

import type { ChartRange, RunStatusEnum, ReportSortKey } from "../components/ui/types";

const API_KEY = (import.meta.env.VITE_ATLAS20_API_KEY as string | undefined)?.trim();
const ENV_BEARER_TOKEN = normalizeBearerToken(import.meta.env.VITE_ATLAS20_BEARER_TOKEN as string | undefined);
let runtimeBearerToken: string | undefined;

function normalizeBearerToken(token: string | undefined): string | undefined {
  const trimmed = token?.trim();
  if (!trimmed) return undefined;
  return /^Bearer\s+/i.test(trimmed) ? trimmed.replace(/^Bearer\s+/i, "Bearer ") : `Bearer ${trimmed}`;
}

export function setApiBearerToken(token: string | null | undefined): void {
  runtimeBearerToken = normalizeBearerToken(token ?? undefined);
}

function withAuthHeaders(headers: Record<string, string>): Record<string, string> {
  if (API_KEY) headers["X-API-Key"] = API_KEY;
  const bearerToken = runtimeBearerToken ?? ENV_BEARER_TOKEN;
  if (bearerToken) headers.Authorization = bearerToken;
  return headers;
}

// ============================================================
// §7.1 — Existing types (preserved & extended)
// ============================================================

export type ChampionSummary = {
  strategy: string;
  display_name: string;
  window_start: string;
  window_end: string;
  min_history_days?: number | null;
  min_daily_dollar_volume?: number | null;
  leader_pool?: string | null;
  rebalance_frequency?: string | null;
  regime_mode?: string | null;
  risk_off_asset?: string | null;
  initial_asset?: string | null;
  btc_stop_lookback_days?: number | null;
  btc_stop_confirm_days?: number | null;
  weight_momentum_rank?: number | null;
  weight_ret_21_rank?: number | null;
  weight_ret_42_rank?: number | null;
  weight_near_high_rank?: number | null;
  multiple: number;
  total_return?: number | null;
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
  annualized_turnover?: number | null;
  monthly_win_rate?: number | null;
};

export type SeriesPoint = {
  date: string;
  value: number;
};

export type SelectionHistoryRow = {
  rebalance_date: string;
  coin_id: string;
  coin_rank: number;
  coin_score?: number | null;
  coin_weight: number;
};

export type OverviewPayload = {
  champion: ChampionSummary;
  top_strategies: StrategySummary[];
  equity_curve: SeriesPoint[];
  daily_returns: SeriesPoint[];
  selection_history: SelectionHistoryRow[];

  // Phase 5 additions
  aum: { current: number; deltaPct: number; sparkline: number[] };
  strategies: { total: number; breakdown: { family: string; count: number }[] };
  regime: { label: "RISK-ON" | "NEUTRAL" | "RISK-OFF"; score: number; model: string };
  rebalance: {
    ts: string;
    swaps: { out: string; in: string; deltaPct: number }[];
  };
  equity_overlay: {
    series: { ts: string; atlas: number; btc: number }[];
    range: ChartRange;
    atlas_label: string;
    btc_label: string;
  };
  hero_kpi: { ytdReturn: number; sharpe: number; maxDd: number; winRate: number };
  last_sync_seconds: number;
  data_source: "real" | "fallback";
};

// Pre-redesign RunStatus (kept for backward compat with runBacktest signature)
export type RunStatus = {
  run_id: string;
  status: "completed" | "failed";
  name: string;
  summary: Record<string, string | number | null>;
  error?: string | null;
};

// ============================================================
// §7.2 — Runs (page2 + page4 shared)
// ============================================================

export type StrategyFamily = "ATLAS" | "Momentum" | "MeanRev" | "Carry" | "Other";

export type RunRow = {
  run_id: string;
  strategy: string;
  selected_strategy?: string | null;
  strategy_family?: StrategyFamily | null;
  universe: string;
  window: { start: string; end: string };
  status: RunStatusEnum;
  return_pct?: number | null;
  sharpe?: number | null;
  max_dd?: number | null;
  duration_s?: number | null;
  eta_s?: number | null;
  spark?: number[] | null;
  created_at: string;
  favorited?: boolean | null;
};

export type RunRowSummary = Pick<RunRow, "run_id" | "strategy" | "status" | "duration_s" | "eta_s" | "favorited"> & {
  params_summary: string;
};

export type RunDetailSeriesPoint = { ts: string; atlas: number; btc: number };

export type RunTurnoverRow = {
  strategy: string;
  annualized_turnover?: number | null;
  avg_turnover_per_rebalance?: number | null;
  average_holdings?: number | null;
};

export type RunTradeRow = {
  rebalance_date: string;
  strategy?: string | null;
  coin_id: string;
  coin_rank?: number | null;
  coin_score?: number | null;
  coin_weight?: number | null;
};

export type RunDetailPayload = RunRow & {
  selected_strategy?: string | null;
  equity_overlay: { series: RunDetailSeriesPoint[] };
  kpi: {
    cagr: number;
    sharpe: number;
    sortino: number;
    max_dd: number;
    calmar: number;
    win_rate: number;
  };
  drawdown_series?: RunDetailSeriesPoint[];
  return_series?: RunDetailSeriesPoint[];
  turnover_rows?: RunTurnoverRow[];
  trade_rows?: RunTradeRow[];
};

// ============================================================
// §7.2 — Backtest config (page2)
// ============================================================

export type BacktestConfig = {
  preset: string;
  universe: { topN: number; excludeStable: boolean; excludeWrapped: boolean };
  window: { start: string; end: string; rebalance: "Weekly" | "Biweekly" | "Monthly" };
  allocation: { positionPct: number; slots: number };
  costs: { feeBps: number; slippageBps: number };
};

export type OptionsPayload = {
  presets: { slug: string; display_name: string }[];
  strategies?: { strategy: string; display_name: string }[];
  universes: { topN: number; label: string }[];
  rebalances: { value: "Weekly" | "Biweekly" | "Monthly"; label: string }[];
  feeBpsRange: number[];
  slippageBpsRange: number[];
  sectors: string[];
};

export const fallbackOptions: OptionsPayload = {
  presets: [
    { slug: "base", display_name: "Base Config" },
    { slug: "five_year_2020_2024", display_name: "Five Year 2020 2024" },
    { slug: "five_year_exact_2021_04_22_2026_04_22", display_name: "Five Year Exact 2021 04 22 2026 04 22" },
    { slug: "bear_bottom_to_current_2022_11_21_2026_04_22", display_name: "Bear Bottom To Current 2022 11 21 2026 04 22" },
  ],
  strategies: [],
  universes: [
    { topN: 5, label: "Top 5" },
    { topN: 10, label: "Top 10" },
    { topN: 20, label: "Top 20" },
  ],
  rebalances: [
    { value: "Weekly", label: "Weekly" },
    { value: "Biweekly", label: "Biweekly" },
    { value: "Monthly", label: "Monthly" },
  ],
  feeBpsRange: [0.0, 10.0, 50.0],
  slippageBpsRange: [0.0, 5.0, 25.0],
  sectors: ["DeFi", "Layer1", "Layer2", "Meme", "Oracle", "Payments"],
};

export const defaultBacktestConfig: BacktestConfig = {
  // "base" is a real preset slug present in config/base.yaml — the engine
  // resolves it directly without falling back to the legacy "ATLAS Adaptive
  // v3" placeholder. Using a real default means a fresh visitor who clicks
  // RUN BACKTEST without changing anything still submits a valid request.
  preset: "base",
  universe: { topN: 20, excludeStable: true, excludeWrapped: true },
  window: { start: "2024-01-01", end: "2026-05-18", rebalance: "Weekly" },
  allocation: { positionPct: 5.0, slots: 10 },
  costs: { feeBps: 10, slippageBps: 5 },
};

// ============================================================
// §7.2 — History filter (page4)
// ============================================================

export type HistoryFilter = {
  q: string;
  chips: string[];
  dateRange: "7d" | "30d" | "90d" | "ytd" | "all";
  page: number;
  pageSize: number;
};

export const defaultHistoryFilter: HistoryFilter = {
  q: "",
  chips: [],
  dateRange: "30d",
  page: 1,
  pageSize: 14,
};

// ============================================================
// §7.2 — Compare (page3)
// ============================================================

export type CompareMetricKey =
  | "cagr"
  | "sharpe"
  | "sortino"
  | "max_dd"
  | "calmar"
  | "win_rate"
  | "avg_turnover"
  | "trades_per_year";

export const compareMetricMeta: Record<
  CompareMetricKey,
  { label: string; direction: "higher-is-better" | "lower-is-better"; format: "percent" | "signed-percent" | "ratio" | "count" }
> = {
  cagr:            { label: "CAGR",         direction: "higher-is-better", format: "signed-percent" },
  sharpe:          { label: "Sharpe",       direction: "higher-is-better", format: "ratio" },
  sortino:         { label: "Sortino",      direction: "higher-is-better", format: "ratio" },
  max_dd:          { label: "Max DD",       direction: "lower-is-better",  format: "percent" },
  calmar:          { label: "Calmar",       direction: "higher-is-better", format: "ratio" },
  win_rate:        { label: "Win Rate",     direction: "higher-is-better", format: "percent" },
  avg_turnover:    { label: "Avg Turnover", direction: "lower-is-better",  format: "percent" },
  trades_per_year: { label: "Trades / yr",  direction: "lower-is-better",  format: "count" },
};

export type CompareSelectionItem = {
  id: string;
  label: string;
  tone: "gold" | "violet" | "cyan" | "emerald";
};

export type ComparePayload = {
  strategies?: { strategy: string; display_name: string }[];
  equity: { ts: string; values: Record<string, number> }[];
  metrics: Record<CompareMetricKey, Record<string, number>>;
  overlap: {
    symbols: string[];
    matrix: number[][];
    sharedHoldings: { symbol: string; count: number; total: number }[];
  };
  data_source: "real" | "fallback";
};

// ============================================================
// §7.2 — Universe (page5)
// ============================================================

export type UniverseTimelinePayload = {
  tokens: string[];
  segments: { token: string; start: string; end: string }[];
  rotations: { ts: string; label: string }[];
  range: { start: string; end: string };
  data_source: "real" | "fallback";
};

export type DataSourceStatus = "healthy" | "degraded" | "error";

export type DataSource = {
  id: string;
  name: string;
  status: DataSourceStatus;
  last_sync_seconds: number;
};

export type DataAlertSeverity = "rose" | "cyan" | "emerald";

export type DataAlert = {
  id: string;
  severity: DataAlertSeverity;
  title: string;
  meta: string;
  ts: string;
  icon: "alert-triangle" | "info" | "check-circle";
  source?: string;
};

// ============================================================
// §7.2 — Reports (page6)
// ============================================================

export type ReportFormat = "markdown" | "pdf" | "png" | "csv" | "bundle";
export type ReportStatus = "ready" | "generating";
export type ReportThumbKind =
  | "equity"
  | "lines"
  | "heatmap"
  | "bars"
  | "horizontal-bars"
  | "sparkbar";

export type FeaturedDigest = {
  id: string;
  title: string;
  subtitle: string;
  formats: ReportFormat[];
  defaultFormat: ReportFormat;
  generated_at: string;
};

export type ReportEntry = {
  id: string;
  title: string;
  subtitle: string;
  thumbnail: ReportThumbKind;
  status: ReportStatus;
  highlight?: boolean | null;
  generated_at: string;
  size_bytes: number;
  report_type: "weekly" | "run" | "compare" | "universe";
};

export type GenerateReportRequest = {
  type: ReportEntry["report_type"];
  formats: ReportFormat[];
  run_id?: string;
  strategy?: string | null;
  notes?: string | null;
};

export type GeneratedReportFile = {
  id: string;
  run_id?: string | null;
  kind: ReportFormat;
  path: string;
  sha256: string;
  size_bytes: number;
  generated_at: string;
};

export type GenerateReportResponse = {
  job_id: string;
  status: "completed";
  files: GeneratedReportFile[];
  warnings: string[];
};

// ============================================================
// Fallback data (mock implementations for dev / tests)
// ============================================================

export const fallbackOverview: OverviewPayload = {
  champion: {
    strategy: "MOMENTUM_LEAD_TOP1_ALL_14D_STOP11_CONFIRM2_BTC_PARK",
    display_name: "Momentum Lead Top1 All 14D Stop11 Confirm2 Btc Park",
    window_start: "2022-11-21",
    window_end: "2026-04-21",
    min_history_days: 30,
    min_daily_dollar_volume: 1_000_000,
    rebalance_frequency: "Biweekly",
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

  // Phase 5 additions
  aum: {
    current: 847_200_000,
    deltaPct: 0.084,
    sparkline: [820, 825, 818, 830, 835, 828, 840, 844, 838, 847],
  },
  strategies: {
    total: 12,
    breakdown: [
      { family: "Trend Following", count: 5 },
      { family: "Momentum", count: 3 },
      { family: "Mean Reversion", count: 2 },
      { family: "Carry", count: 1 },
      { family: "Other", count: 1 },
    ],
  },
  regime: { label: "RISK-ON", score: 0.72, model: "v2.1" },
  rebalance: {
    ts: "2026-05-18",
    swaps: [
      { out: "TIA", in: "DOT", deltaPct: 0.042 },
      { out: "ICP", in: "SUI", deltaPct: 0.031 },
      { out: "ATOM", in: "INJ", deltaPct: -0.018 },
      { out: "FTM", in: "SEI", deltaPct: 0.024 },
    ],
  },
  equity_overlay: {
    series: [
      { ts: "Jan 2026", atlas: 0, btc: 0 },
      { ts: "Feb 2026", atlas: 180, btc: 22 },
      { ts: "Mar 2026", atlas: 420, btc: 58 },
      { ts: "Apr 2026", atlas: 780, btc: 104 },
      { ts: "May 2026", atlas: 1247, btc: 124 },
    ],
    range: "YTD",
    atlas_label: "Momentum Lead Top1 All 14D Stop11 Confirm2 Btc Park",
    btc_label: "BTC Benchmark",
  },
  hero_kpi: { ytdReturn: 12.4756, sharpe: 3.42, maxDd: -0.3204, winRate: 0.685 },
  last_sync_seconds: 18,
  data_source: "fallback",
};

export const fallbackRunsQueue: RunRowSummary[] = [
  { run_id: "btk_0148", strategy: "ATLAS Adaptive v3",   status: "running",   duration_s: 42,  eta_s: 90,  params_summary: "N=20 · Weekly · 2024→2026" },
  { run_id: "btk_0147", strategy: "Momentum Top-10",     status: "running",   duration_s: 24,  eta_s: 60,  params_summary: "N=10 · Daily · 2024→2026" },
  { run_id: "btk_0146", strategy: "Mean Reversion v2",   status: "completed", duration_s: 88,  params_summary: "N=15 · Biweekly · 2024→2026" },
  { run_id: "btk_0145", strategy: "ATLAS Adaptive v2",   status: "completed", duration_s: 102, params_summary: "N=20 · Weekly · 2023→2026" },
  { run_id: "btk_0144", strategy: "Carry Top-5",         status: "failed",    duration_s: 12,  params_summary: "N=5 · Weekly · 2024→2026" },
  { run_id: "btk_0149", strategy: "ATLAS Adaptive v3",   status: "queued",    params_summary: "N=20 · Weekly · 2024→2026" },
];

export const fallbackRunsList: RunRow[] = [
  { run_id: "btk_0148", strategy: "ATLAS Adaptive v3",   strategy_family: "ATLAS",    universe: "Top-20", window: { start: "2024-01-01", end: "2026-05-18" }, status: "running",   return_pct: 0,       sharpe: 0,    max_dd: 0,       duration_s: 42,  eta_s: 90, spark: [], created_at: "2026-05-18T14:02:00Z", favorited: true },
  { run_id: "btk_0147", strategy: "Momentum Top-10",     strategy_family: "Momentum", universe: "Top-10", window: { start: "2024-01-01", end: "2026-05-18" }, status: "running",   return_pct: 0,       sharpe: 0,    max_dd: 0,       duration_s: 24,  eta_s: 60, spark: [], created_at: "2026-05-18T13:58:00Z" },
  { run_id: "btk_0146", strategy: "Mean Reversion v2",   strategy_family: "MeanRev",  universe: "Top-15", window: { start: "2024-01-01", end: "2026-05-18" }, status: "completed", return_pct: 0.416,   sharpe: 1.94, max_dd: -0.184, duration_s: 88,  spark: [10, 12, 11, 14, 13, 16, 15], created_at: "2026-05-18T12:30:00Z" },
  { run_id: "btk_0145", strategy: "ATLAS Adaptive v2",   strategy_family: "ATLAS",    universe: "Top-20", window: { start: "2023-01-01", end: "2026-05-18" }, status: "completed", return_pct: 0.921,   sharpe: 2.81, max_dd: -0.287, duration_s: 102, spark: [10, 15, 22, 28, 34, 42, 50], created_at: "2026-05-17T18:14:00Z" },
  { run_id: "btk_0144", strategy: "Carry Top-5",         strategy_family: "Carry",    universe: "Top-5",  window: { start: "2024-01-01", end: "2026-05-18" }, status: "failed",    duration_s: 12, created_at: "2026-05-17T16:02:00Z" },
  { run_id: "btk_0143", strategy: "Mean Reversion v1",   strategy_family: "MeanRev",  universe: "Top-15", window: { start: "2024-01-01", end: "2026-05-15" }, status: "completed", return_pct: 0.224,   sharpe: 1.42, max_dd: -0.215, duration_s: 76,  spark: [10, 11, 10, 12, 11, 13, 12], created_at: "2026-05-17T11:00:00Z" },
  { run_id: "btk_0142", strategy: "ATLAS Adaptive v3",   strategy_family: "ATLAS",    universe: "Top-20", window: { start: "2024-01-01", end: "2026-05-15" }, status: "completed", return_pct: 1.584,   sharpe: 3.42, max_dd: -0.3204, duration_s: 88, spark: [10, 18, 26, 38, 50, 65, 80], created_at: "2026-05-16T22:45:00Z", favorited: true },
  { run_id: "btk_0141", strategy: "Momentum Top-10",     strategy_family: "Momentum", universe: "Top-10", window: { start: "2023-06-01", end: "2026-05-15" }, status: "completed", return_pct: 0.682,   sharpe: 2.10, max_dd: -0.243, duration_s: 64,  spark: [10, 14, 18, 24, 30, 36, 42], created_at: "2026-05-16T17:18:00Z" },
  { run_id: "btk_0140", strategy: "ATLAS Adaptive v3",   strategy_family: "ATLAS",    universe: "Top-20", window: { start: "2024-06-01", end: "2026-05-12" }, status: "completed", return_pct: 0.842,   sharpe: 2.65, max_dd: -0.198, duration_s: 80,  spark: [10, 16, 22, 28, 36, 44, 52], created_at: "2026-05-16T09:30:00Z" },
  { run_id: "btk_0139", strategy: "Mean Reversion v2",   strategy_family: "MeanRev",  universe: "Top-15", window: { start: "2024-01-01", end: "2026-05-12" }, status: "completed", return_pct: 0.184,   sharpe: 1.72, max_dd: -0.142, duration_s: 70,  spark: [10, 11, 12, 11, 13, 12, 14], created_at: "2026-05-15T20:00:00Z" },
  { run_id: "btk_0138", strategy: "Carry Top-5",         strategy_family: "Carry",    universe: "Top-5",  window: { start: "2024-01-01", end: "2026-05-10" }, status: "failed",    duration_s: 18, created_at: "2026-05-15T16:20:00Z" },
  { run_id: "btk_0137", strategy: "ATLAS Adaptive v2",   strategy_family: "ATLAS",    universe: "Top-20", window: { start: "2023-01-01", end: "2026-05-10" }, status: "completed", return_pct: 0.764,   sharpe: 2.42, max_dd: -0.262, duration_s: 92,  spark: [10, 14, 20, 26, 34, 42, 48], created_at: "2026-05-15T11:00:00Z" },
  { run_id: "btk_0136", strategy: "Momentum Top-10",     strategy_family: "Momentum", universe: "Top-10", window: { start: "2023-06-01", end: "2026-05-10" }, status: "completed", return_pct: 0.582,   sharpe: 1.95, max_dd: -0.231, duration_s: 60,  spark: [10, 13, 17, 22, 28, 33, 38], created_at: "2026-05-14T22:00:00Z" },
  { run_id: "btk_0135", strategy: "Trend Following v1",  strategy_family: "Other",    universe: "Top-20", window: { start: "2024-01-01", end: "2026-05-08" }, status: "completed", return_pct: 0.412,   sharpe: 1.65, max_dd: -0.198, duration_s: 84,  spark: [10, 13, 16, 20, 25, 30, 34], created_at: "2026-05-14T15:30:00Z" },
];

export const fallbackRunDetail: RunDetailPayload = {
  ...fallbackRunsList[6], // btk_0142, the canonical "champion" reference run
  selected_strategy: fallbackRunsList[6].strategy,
  equity_overlay: { series: fallbackOverview.equity_overlay.series },
  kpi: { cagr: 1.584, sharpe: 3.42, sortino: 5.18, max_dd: -0.3204, calmar: 4.95, win_rate: 0.685 },
  drawdown_series: [],
  return_series: [],
  turnover_rows: [],
  trade_rows: [],
};

export const fallbackCompare: ComparePayload = {
  strategies: [
    { strategy: "atlas", display_name: "ATLAS v3" },
    { strategy: "momentum", display_name: "Momentum" },
    { strategy: "meanrev", display_name: "MeanRev" },
  ],
  equity: [
    { ts: "Jan 2026", values: { atlas: 0,    momentum: 0,   meanrev: 0 } },
    { ts: "Feb 2026", values: { atlas: 180,  momentum: 110, meanrev: 32 } },
    { ts: "Mar 2026", values: { atlas: 420,  momentum: 240, meanrev: 78 } },
    { ts: "Apr 2026", values: { atlas: 780,  momentum: 430, meanrev: 142 } },
    { ts: "May 2026", values: { atlas: 1247, momentum: 682, meanrev: 214 } },
  ],
  metrics: {
    cagr:            { atlas: 1.584, momentum: 0.921, meanrev: 0.416 },
    sharpe:          { atlas: 3.42,  momentum: 2.81,  meanrev: 1.94 },
    sortino:         { atlas: 5.18,  momentum: 4.02,  meanrev: 2.71 },
    max_dd:          { atlas: -0.3204, momentum: -0.287, meanrev: -0.184 },
    calmar:          { atlas: 4.95,  momentum: 3.21,  meanrev: 2.26 },
    win_rate:        { atlas: 0.685, momentum: 0.612, meanrev: 0.548 },
    avg_turnover:    { atlas: 0.182, momentum: 0.246, meanrev: 0.083 },
    trades_per_year: { atlas: 248,   momentum: 312,   meanrev: 96 },
  },
  overlap: {
    symbols: ["ATLAS v3", "Momentum", "MeanRev"],
    matrix: [
      [1.0, 0.62, 0.18],
      [0.62, 1.0, 0.31],
      [0.18, 0.31, 1.0],
    ],
    sharedHoldings: [
      { symbol: "SOL", count: 3, total: 3 },
      { symbol: "TIA", count: 2, total: 3 },
      { symbol: "SUI", count: 2, total: 3 },
      { symbol: "INJ", count: 2, total: 3 },
      { symbol: "SEI", count: 1, total: 3 },
    ],
  },
  data_source: "fallback",
};

const universeTickers = [
  "BTC", "ETH", "SOL", "BNB", "XRP", "ADA", "DOGE", "AVAX",
  "DOT", "LINK", "MATIC", "TON", "TRX", "ATOM", "ICP", "NEAR",
  "INJ", "SUI", "TIA", "SEI", "ARB", "OP", "APT", "RNDR",
  "FIL", "STX", "FTM", "AAVE", "HBAR", "ALGO", "EGLD", "FLOW",
];

export const fallbackUniverseTimeline: UniverseTimelinePayload = {
  tokens: universeTickers,
  segments: universeTickers.slice(1, 21).flatMap((token, idx) => {
    // Each top-20 token has 1-2 active windows in last 180 days
    const baseStart = idx % 3 === 0 ? "2025-12-01" : idx % 3 === 1 ? "2026-01-15" : "2026-02-10";
    return [{ token, start: baseStart, end: "2026-05-18" }];
  }),
  rotations: [
    { ts: "2026-01-15", label: "MAJOR ROTATION" },
    { ts: "2026-03-09", label: "MAJOR ROTATION" },
    { ts: "2026-04-22", label: "MAJOR ROTATION" },
  ],
  range: { start: "2025-12-01", end: "2026-05-18" },
  data_source: "fallback",
};

export const fallbackDataSources: DataSource[] = [
  { id: "coingecko",     name: "CoinGecko · Markets",   status: "healthy",  last_sync_seconds: 12 },
  { id: "cryptocompare", name: "CryptoCompare · OHLCV", status: "healthy",  last_sync_seconds: 18 },
  { id: "binance",       name: "Binance · Spot",        status: "healthy",  last_sync_seconds: 6 },
  { id: "coinbase",      name: "Coinbase · Spot",       status: "degraded", last_sync_seconds: 840 },
  { id: "kraken",        name: "Kraken · Spot",         status: "healthy",  last_sync_seconds: 14 },
  { id: "defillama",     name: "DefiLlama · TVL",       status: "healthy",  last_sync_seconds: 120 },
  { id: "glassnode",     name: "Glassnode · On-chain",  status: "degraded", last_sync_seconds: 1800 },
  { id: "messari",       name: "Messari · Metrics",     status: "healthy",  last_sync_seconds: 240 },
  { id: "custom",        name: "Custom · CSV uploads",  status: "error",    last_sync_seconds: 8040 },
];

export const fallbackDataAlerts: DataAlert[] = [
  { id: "a1", severity: "rose",    title: "BNB · price gap detected — auto-imputed",     meta: "Gap 14m · CoinGecko · auto-fill", ts: "2026-05-18T13:42:00Z", icon: "alert-triangle" },
  { id: "a2", severity: "rose",    title: "RNDR · volume outlier (5σ) — flagged for review", meta: "Δ5.2σ · Binance · pending",      ts: "2026-05-18T12:18:00Z", icon: "alert-triangle" },
  { id: "a3", severity: "cyan",    title: "DOT · stale tick > 30s on Coinbase",          meta: "Stale 38s · Coinbase",            ts: "2026-05-18T11:40:00Z", icon: "info" },
  { id: "a4", severity: "rose",    title: "ICP · OHLCV mismatch CoinGecko vs Kraken",    meta: "Δ0.4% · 2026-05-18 04:00 UTC",    ts: "2026-05-18T05:00:00Z", icon: "alert-triangle" },
  { id: "a5", severity: "emerald", title: "ATOM · validator slashing event resolved",    meta: "Slash 0.1% · resolved",           ts: "2026-05-17T23:14:00Z", icon: "check-circle" },
  { id: "a6", severity: "cyan",    title: "Universe diff: 2 in / 2 out at 2026-05-15 00:00 UTC rebalance", meta: "+TIA +SEI / -ATOM -FTM", ts: "2026-05-15T00:00:00Z", icon: "info" },
];

export const fallbackFeaturedDigest: FeaturedDigest = {
  id: "digest_w20_2026",
  title: "Atlas20 — Week 20 / 2026",
  subtitle: "ATLAS Adaptive v3 · YTD +1,247.56% · Top-20 universe · generated 2026-05-18 14:32 UTC",
  formats: ["markdown", "pdf", "png", "csv"],
  defaultFormat: "markdown",
  generated_at: "2026-05-18T14:32:00Z",
};

export const fallbackReports: ReportEntry[] = [
  { id: "r1", title: "Atlas20 — Week 19 / 2026",                  subtitle: "digest_w19 · 2026-05-11 · 3.1 MB",       thumbnail: "equity",          status: "ready",      highlight: true,  generated_at: "2026-05-11T14:00:00Z", size_bytes: 3_250_000, report_type: "weekly" },
  { id: "r2", title: "ATLAS Adaptive v3 — Tear sheet",            subtitle: "btk_0142 · 2026-05-18 · 2.4 MB",         thumbnail: "lines",           status: "ready",                        generated_at: "2026-05-18T15:00:00Z", size_bytes: 2_500_000, report_type: "run" },
  { id: "r3", title: "Q1 2026 Performance Review",                subtitle: "q1_2026_review · 2026-04-02 · 4.6 MB",   thumbnail: "heatmap",         status: "ready",                        generated_at: "2026-04-02T10:00:00Z", size_bytes: 4_800_000, report_type: "compare" },
  { id: "r4", title: "Momentum Family Comparison",                subtitle: "cmp_momentum · 2026-05-09 · 1.8 MB",     thumbnail: "bars",            status: "ready",                        generated_at: "2026-05-09T08:30:00Z", size_bytes: 1_890_000, report_type: "compare" },
  { id: "r5", title: "Universe Composition · April 2026",         subtitle: "uni_2026-04 · 2026-05-01 · pending",     thumbnail: "horizontal-bars", status: "generating",                   generated_at: "2026-05-01T00:00:00Z", size_bytes: 0,         report_type: "universe" },
  { id: "r6", title: "MeanRev v2 — Backtest Report",              subtitle: "btk_0136 · 2026-05-07 · 2.1 MB",         thumbnail: "sparkbar",        status: "ready",                        generated_at: "2026-05-07T18:42:00Z", size_bytes: 2_180_000, report_type: "run" },
];

// ============================================================
// §8 — API function registry
// ============================================================

export function buildApiUrl(path: string, base = import.meta.env.VITE_ATLAS20_API_BASE ?? "/api") {
  const cleanBase = base.replace(/\/+$/, "");
  const cleanPath = path.replace(/^\/+/, "");
  return `${cleanBase}/${cleanPath}`;
}

type ApiErrorPayload = {
  error?: {
    code?: unknown;
    message?: unknown;
    details?: unknown;
    request_id?: unknown;
  };
};

export class ApiError extends Error {
  status: number;
  code?: string;
  details: unknown;
  requestId?: string;

  constructor(
    message: string,
    {
      status,
      code,
      details,
      requestId,
    }: {
      status: number;
      code?: string;
      details?: unknown;
      requestId?: string;
    },
  ) {
    super(message);
    this.name = "ApiError";
    this.status = status;
    this.code = code;
    this.details = details;
    this.requestId = requestId;
  }
}

async function apiErrorFromResponse(response: Response, fallbackMessage: string): Promise<ApiError> {
  const payload = await response.clone().json().catch(() => undefined) as ApiErrorPayload | undefined;
  const error = payload?.error;
  const message = typeof error?.message === "string" ? error.message : fallbackMessage;
  const code = typeof error?.code === "string" ? error.code : undefined;
  const requestId = typeof error?.request_id === "string" ? error.request_id : undefined;
  return new ApiError(message, {
    status: response.status,
    code,
    details: error?.details,
    requestId,
  });
}

async function requestJson<T>(path: string, init?: RequestInit): Promise<T> {
  const headers = withAuthHeaders({
    ...(init?.headers as Record<string, string> | undefined),
  });
  const response = await fetch(buildApiUrl(path), { ...init, headers });
  if (!response.ok) {
    throw await apiErrorFromResponse(response, `Atlas20 API request failed: ${response.status}`);
  }
  return response.json() as Promise<T>;
}

export type ReportDownload = {
  blob: Blob;
  filename: string;
};

async function requestBlob(path: string, fallbackFilename: string): Promise<ReportDownload> {
  const headers = withAuthHeaders({});
  const response = await fetch(buildApiUrl(path), { headers });
  if (!response.ok) {
    throw await apiErrorFromResponse(response, `Atlas20 API download failed: ${response.status}`);
  }
  const filename = parseAttachmentFilename(response.headers.get("Content-Disposition")) ?? fallbackFilename;
  const contentType = response.headers.get("Content-Type") ?? "";
  const blob = new Blob([await response.arrayBuffer()], { type: contentType });
  return { blob, filename };
}

function parseAttachmentFilename(header: string | null): string | undefined {
  if (!header) return undefined;
  const encoded = /filename\*=UTF-8''([^;]+)/i.exec(header);
  if (encoded?.[1]) {
    try {
      return decodeURIComponent(encoded[1].replace(/^"|"$/g, ""));
    } catch {
      return encoded[1].replace(/^"|"$/g, "");
    }
  }
  return /filename="?([^";]+)"?/i.exec(header)?.[1];
}

function triggerBrowserDownload({ blob, filename }: ReportDownload): void {
  const url = URL.createObjectURL(blob);
  const anchor = document.createElement("a");
  anchor.href = url;
  anchor.download = filename;
  anchor.rel = "noopener";
  document.body.appendChild(anchor);
  anchor.click();
  anchor.remove();
  URL.revokeObjectURL(url);
}

export function getOverview() {
  return requestJson<OverviewPayload>("/overview");
}

export function getOptions() {
  return requestJson<OptionsPayload>("/options");
}

export function runBacktest(payload: BacktestConfig) {
  return requestJson<RunRowSummary>("/backtests/run", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
}

export function listRunsQueue() {
  return requestJson<RunRowSummary[]>("/runs/queue");
}

export function listRuns(filter: HistoryFilter) {
  const params = new URLSearchParams({
    q: filter.q,
    chips: filter.chips.join(","),
    dateRange: filter.dateRange,
    page: String(filter.page),
    pageSize: String(filter.pageSize),
  });
  return requestJson<{ items: RunRow[]; total: number; page: number; pageSize: number }>(
    `/runs?${params.toString()}`,
  );
}

export function getRun(id: string) {
  return requestJson<RunRow>(`/runs/${encodeURIComponent(id)}`);
}

export function getRunDetail(id: string) {
  return requestJson<RunDetailPayload>(`/runs/${encodeURIComponent(id)}/detail`);
}

export function toggleFavorite(id: string) {
  return requestJson<{ run_id: string; favorited: boolean }>(
    `/runs/${encodeURIComponent(id)}/favorite`,
    { method: "POST" },
  );
}

export function getCompare(ids: string[], range: ChartRange) {
  const params = new URLSearchParams({ ids: ids.join(","), range });
  return requestJson<ComparePayload>(`/compare?${params.toString()}`);
}

export function getUniverseTimeline() {
  return requestJson<UniverseTimelinePayload>("/universe/timeline");
}

export function getDataSources() {
  return requestJson<DataSource[]>("/universe/sources");
}

export function getDataAlerts() {
  return requestJson<DataAlert[]>("/universe/alerts");
}

export function refreshUniverse() {
  return requestJson<{ run_id: string; status: string }>("/universe/refresh", { method: "POST" });
}

export function getFeaturedDigest() {
  return requestJson<FeaturedDigest>("/reports/digest/featured");
}

export function listReports(sort: ReportSortKey) {
  return requestJson<ReportEntry[]>(`/reports?sort=${encodeURIComponent(sort)}`);
}

export function downloadDigestUrl(format: ReportFormat): string {
  return buildApiUrl(`/reports/digest/download?format=${encodeURIComponent(format)}`);
}

export function downloadReportUrl(id: string, fmt?: ReportFormat): string {
  const q = fmt ? `?format=${encodeURIComponent(fmt)}` : "";
  return buildApiUrl(`/reports/${encodeURIComponent(id)}/download${q}`);
}

export function fetchDigestDownload(format: ReportFormat): Promise<ReportDownload> {
  return requestBlob(
    `/reports/digest/download?format=${encodeURIComponent(format)}`,
    `atlas20-digest.${format}`,
  );
}

export function fetchReportDownload(id: string, fmt?: ReportFormat): Promise<ReportDownload> {
  const q = fmt ? `?format=${encodeURIComponent(fmt)}` : "";
  return requestBlob(
    `/reports/${encodeURIComponent(id)}/download${q}`,
    `atlas20-${id}${fmt ? `.${fmt}` : ""}`,
  );
}

export async function downloadDigest(format: ReportFormat): Promise<void> {
  triggerBrowserDownload(await fetchDigestDownload(format));
}

export async function downloadReport(id: string, fmt?: ReportFormat): Promise<void> {
  triggerBrowserDownload(await fetchReportDownload(id, fmt));
}

export function generateReport(payload: GenerateReportRequest) {
  return requestJson<GenerateReportResponse>("/reports/generate", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
}
