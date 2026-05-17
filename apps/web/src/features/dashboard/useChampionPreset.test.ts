import { describe, expect, it } from "vitest";

import { buildApiUrl } from "../../lib/api";
import { championToFormState } from "./useChampionPreset";

describe("championToFormState", () => {
  it("parses fallback strategy settings from the champion name", () => {
    const state = championToFormState({
      strategy: "MOMENTUM_LEAD_TOP1_ALL_14D_STOP11_CONFIRM2_BTC_PARK",
      window_start: "2022-11-21",
      window_end: "2026-04-21",
      multiple: 236.999833,
      cagr: 3.949231,
      sharpe: 2.293786,
      max_drawdown: -0.507875,
      annualized_turnover: 37.801204,
      monthly_win_rate: 0.619048,
      ending_equity: 23699983.3,
    });

    expect(state.strategy.frequency).toBe("14D");
    expect(state.risk.stop_lookback_days).toBe(11);
    expect(state.risk.confirm_days).toBe(2);
  });

  it("prefers explicit API fields when richer champion settings are present", () => {
    const state = championToFormState({
      strategy: "MOMENTUM_LEAD_TOP3_ALL_28D_STOP99_CONFIRM9_BTC_PARK",
      window_start: "2022-11-21",
      window_end: "2026-04-21",
      rebalance_frequency: "7D",
      regime_mode: "risk_managed",
      risk_off_asset: "BTC",
      btc_stop_lookback_days: 11,
      btc_stop_confirm_days: 2,
      multiple: 236.999833,
      cagr: 3.949231,
      sharpe: 2.293786,
      max_drawdown: -0.507875,
      annualized_turnover: 37.801204,
      monthly_win_rate: 0.619048,
      ending_equity: 23699983.3,
    });

    expect(state.strategy.frequency).toBe("7D");
    expect(state.risk.mode).toBe("risk_managed");
    expect(state.risk.stop_lookback_days).toBe(11);
    expect(state.risk.confirm_days).toBe(2);
    expect(state.risk.risk_off_asset).toBe("bitcoin");
  });
});

describe("buildApiUrl", () => {
  it("uses a relative /api base by default and allows an override", () => {
    expect(buildApiUrl("/overview")).toBe("/api/overview");
    expect(buildApiUrl("/overview", "http://127.0.0.1:8000/custom-api/")).toBe(
      "http://127.0.0.1:8000/custom-api/overview",
    );
  });
});
