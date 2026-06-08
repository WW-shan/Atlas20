import { afterEach, describe, expect, it, vi } from "vitest";

import {
  defaultBacktestConfig,
  defaultHistoryFilter,
  compareMetricMeta,
  fallbackOverview,
  fallbackRunsQueue,
  fallbackRunsList,
  fallbackRunDetail,
  fallbackCompare,
  fallbackOptions,
  fallbackUniverseTimeline,
  fallbackDataSources,
  fallbackDataAlerts,
  fallbackFeaturedDigest,
  fallbackReports,
} from "./api";
import { qk } from "./qk";

describe("Default config constants", () => {
  it("defaultBacktestConfig has all required fields", () => {
    expect(defaultBacktestConfig.preset).toBe("base");
    expect(defaultBacktestConfig.universe.topN).toBe(20);
    expect(defaultBacktestConfig.allocation.slots).toBe(10);
    expect(defaultBacktestConfig.costs.feeBps).toBe(10);
  });

  it("defaultHistoryFilter uses serializable string[] chips", () => {
    expect(Array.isArray(defaultHistoryFilter.chips)).toBe(true);
    expect(defaultHistoryFilter.page).toBe(1);
    expect(defaultHistoryFilter.pageSize).toBe(14);
  });

  it("compareMetricMeta covers all 8 keys with correct direction", () => {
    const keys = Object.keys(compareMetricMeta);
    expect(keys).toHaveLength(8);
    expect(compareMetricMeta.max_dd.direction).toBe("lower-is-better");
    expect(compareMetricMeta.cagr.direction).toBe("higher-is-better");
    expect(compareMetricMeta.avg_turnover.direction).toBe("lower-is-better");
  });
});

describe("Fallback data shapes", () => {
  it("fallbackOverview has Phase 5 additions (aum, regime, hero_kpi, equity_overlay)", () => {
    expect(fallbackOverview.aum.current).toBeGreaterThan(0);
    expect(fallbackOverview.regime.label).toBe("RISK-ON");
    expect(fallbackOverview.hero_kpi.ytdReturn).toBeGreaterThan(0);
    expect(fallbackOverview.equity_overlay.series.length).toBeGreaterThan(0);
    expect(fallbackOverview.rebalance.swaps.length).toBe(4);
    expect(fallbackOverview.strategies.total).toBe(12);
  });

  it("fallbackRunsQueue has mixed statuses (running/completed/failed/queued)", () => {
    const statuses = new Set(fallbackRunsQueue.map((r) => r.status));
    expect(statuses.has("running")).toBe(true);
    expect(statuses.has("completed")).toBe(true);
    expect(statuses.has("failed")).toBe(true);
    expect(statuses.has("queued")).toBe(true);
  });

  it("fallbackRunsList has at least 14 rows (page4 default pageSize)", () => {
    expect(fallbackRunsList.length).toBeGreaterThanOrEqual(14);
    // Must contain the canonical champion run btk_0142
    expect(fallbackRunsList.some((r) => r.run_id === "btk_0142")).toBe(true);
  });

  it("fallbackRunDetail has equity_overlay + 6 KPI fields", () => {
    expect(fallbackRunDetail.equity_overlay.series.length).toBeGreaterThan(0);
    expect(fallbackRunDetail.kpi.cagr).toBeGreaterThan(0);
    expect(fallbackRunDetail.kpi.sortino).toBeGreaterThan(0);
  });

  it("fallbackCompare metrics cover all 8 keys", () => {
    expect(Object.keys(fallbackCompare.metrics)).toHaveLength(8);
    expect(fallbackCompare.overlap.symbols).toHaveLength(3);
    expect(fallbackCompare.overlap.matrix).toHaveLength(3);
  });

  it("fallbackOptions exposes addable compare strategies", () => {
    expect(fallbackOptions.strategies?.length).toBeGreaterThan(0);
    expect(fallbackOptions.strategies?.map((option) => option.strategy)).toContain("BTC_BH__always_on");
    expect(fallbackOptions.strategies?.every((option) => option.display_name.length > 0)).toBe(true);
  });

  it("fallbackUniverseTimeline has 32 tokens", () => {
    expect(fallbackUniverseTimeline.tokens.length).toBe(32);
    expect(fallbackUniverseTimeline.rotations.length).toBeGreaterThanOrEqual(3);
  });

  it("fallbackDataSources has 9 sources with 6/2/1 status distribution", () => {
    expect(fallbackDataSources.length).toBe(9);
    const counts = fallbackDataSources.reduce((acc, s) => {
      acc[s.status] = (acc[s.status] ?? 0) + 1;
      return acc;
    }, {} as Record<string, number>);
    expect(counts.healthy).toBe(6);
    expect(counts.degraded).toBe(2);
    expect(counts.error).toBe(1);
  });

  it("fallbackDataAlerts has 6 alerts with 3/2/1 severity (rose/cyan/emerald)", () => {
    expect(fallbackDataAlerts.length).toBe(6);
    const counts = fallbackDataAlerts.reduce((acc, a) => {
      acc[a.severity] = (acc[a.severity] ?? 0) + 1;
      return acc;
    }, {} as Record<string, number>);
    expect(counts.rose).toBe(3);
    expect(counts.cyan).toBe(2);
    expect(counts.emerald).toBe(1);
    // No InfoCircle anywhere — must be "info"
    expect(fallbackDataAlerts.every((a) => (a.icon as string) !== "InfoCircle")).toBe(true);
  });

  it("fallbackFeaturedDigest has 4 formats", () => {
    expect(fallbackFeaturedDigest.formats).toHaveLength(4);
    expect(fallbackFeaturedDigest.defaultFormat).toBe("markdown");
  });

  it("fallbackReports has 6 entries, 5 ready + 1 generating, 1 highlight", () => {
    expect(fallbackReports.length).toBe(6);
    const ready = fallbackReports.filter((r) => r.status === "ready").length;
    const gen = fallbackReports.filter((r) => r.status === "generating").length;
    const highlight = fallbackReports.filter((r) => r.highlight).length;
    expect(ready).toBe(5);
    expect(gen).toBe(1);
    expect(highlight).toBe(1);
  });
});

describe("qk registry", () => {
  it("produces stable keys for runs.list regardless of chip order", () => {
    const f1 = { ...defaultHistoryFilter, chips: ["a", "b", "c"] };
    const f2 = { ...defaultHistoryFilter, chips: ["c", "a", "b"] };
    expect(JSON.stringify(qk.runs.list(f1))).toBe(JSON.stringify(qk.runs.list(f2)));
  });

  it("produces stable keys for compare regardless of id order", () => {
    expect(JSON.stringify(qk.compare(["a", "b"], "YTD"))).toBe(
      JSON.stringify(qk.compare(["b", "a"], "YTD")),
    );
  });

  it("produces distinct keys for different namespaces", () => {
    expect(qk.overview()[0]).toBe("overview");
    expect(qk.runs.queue()[0]).toBe("runs");
    expect(qk.universe.timeline()[0]).toBe("universe");
    expect(qk.reports.featured()[0]).toBe("reports");
  });
});

describe("requestJson API key header", () => {
  afterEach(() => {
    vi.restoreAllMocks();
    vi.unstubAllEnvs();
    vi.resetModules();
  });

  it("injects X-API-Key when VITE_ATLAS20_API_KEY is set", async () => {
    vi.resetModules();
    vi.stubEnv("VITE_ATLAS20_API_KEY", "test-key");
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(new Response(JSON.stringify(fallbackRunsQueue[0]))));
    const api = await import("./api");

    await api.runBacktest(api.defaultBacktestConfig);

    const init = vi.mocked(fetch).mock.calls[0][1] as RequestInit;
    expect(init.headers).toMatchObject({
      "Content-Type": "application/json",
      "X-API-Key": "test-key",
    });
  });

  it("omits X-API-Key when VITE_ATLAS20_API_KEY is empty", async () => {
    vi.resetModules();
    vi.stubEnv("VITE_ATLAS20_API_KEY", "   ");
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(new Response(JSON.stringify(fallbackRunsQueue[0]))));
    const api = await import("./api");

    await api.runBacktest(api.defaultBacktestConfig);

    const init = vi.mocked(fetch).mock.calls[0][1] as RequestInit;
    expect(init.headers).toMatchObject({ "Content-Type": "application/json" });
    expect(init.headers).not.toHaveProperty("X-API-Key");
  });

  it("injects Authorization bearer when VITE_ATLAS20_BEARER_TOKEN is set", async () => {
    vi.resetModules();
    vi.stubEnv("VITE_ATLAS20_BEARER_TOKEN", "jwt-token");
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(new Response(JSON.stringify(fallbackRunsQueue[0]))));
    const api = await import("./api");

    await api.runBacktest(api.defaultBacktestConfig);

    const init = vi.mocked(fetch).mock.calls[0][1] as RequestInit;
    expect(init.headers).toMatchObject({
      "Content-Type": "application/json",
      Authorization: "Bearer jwt-token",
    });
  });

  it("uses runtime bearer token set by OAuth integrations", async () => {
    vi.resetModules();
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(new Response(JSON.stringify(fallbackRunsQueue[0]))));
    const api = await import("./api");
    api.setApiBearerToken("Bearer runtime-token");

    await api.runBacktest(api.defaultBacktestConfig);

    const init = vi.mocked(fetch).mock.calls[0][1] as RequestInit;
    expect(init.headers).toMatchObject({
      "Content-Type": "application/json",
      Authorization: "Bearer runtime-token",
    });
  });

  it("fetches report downloads with X-API-Key and parses attachment filename", async () => {
    vi.resetModules();
    vi.stubEnv("VITE_ATLAS20_API_KEY", "download-key");
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(
        new Response("# Digest\n", {
          headers: { "Content-Disposition": 'attachment; filename="digest.md"' },
        }),
      ),
    );
    const api = await import("./api");
    const fetchReportDownload = (
      api as unknown as {
        fetchReportDownload: (id: string, fmt?: string) => Promise<{ blob: Blob; filename: string }>;
      }
    ).fetchReportDownload;

    const result = await fetchReportDownload("btk_0142", "markdown");

    const [url, init] = vi.mocked(fetch).mock.calls[0] as [string, RequestInit];
    expect(url).toBe("/api/reports/btk_0142/download?format=markdown");
    expect(init.headers).toMatchObject({ "X-API-Key": "download-key" });
    expect(result.filename).toBe("digest.md");
    expect(result.blob).toBeInstanceOf(Blob);
    expect(result.blob.size).toBe("# Digest\n".length);
  });

  it("throws ApiError with backend envelope details for JSON requests", async () => {
    vi.resetModules();
    const details = [{ loc: ["body", "formats"], msg: "List should have at least 1 item" }];
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(
        new Response(
          JSON.stringify({
            error: {
              code: "validation_error",
              message: "formats must not be empty",
              details,
              request_id: "req-frontend-422",
            },
          }),
          { status: 422, headers: { "Content-Type": "application/json" } },
        ),
      ),
    );
    const api = await import("./api");

    await expect(api.generateReport({ type: "run", formats: [] })).rejects.toMatchObject({
      name: "ApiError",
      message: "formats must not be empty",
      status: 422,
      code: "validation_error",
      details,
      requestId: "req-frontend-422",
    });
  });

  it("keeps status fallback messages for non-JSON download errors", async () => {
    vi.resetModules();
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(new Response("missing", { status: 404 })));
    const api = await import("./api");

    await expect(api.fetchReportDownload("missing-run", "pdf")).rejects.toMatchObject({
      name: "ApiError",
      message: "Atlas20 API download failed: 404",
      status: 404,
    });
  });
});
