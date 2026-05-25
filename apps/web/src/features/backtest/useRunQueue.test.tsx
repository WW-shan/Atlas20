import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { act, renderHook } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import * as api from "../../lib/api";
import { useRunQueue } from "./useRunQueue";

vi.mock("../../lib/api", async () => {
  const actual = await vi.importActual<typeof import("../../lib/api")>("../../lib/api");
  return {
    ...actual,
    listRunsQueue: vi.fn(),
  };
});

function wrapper({ children }: { children: React.ReactNode }) {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return <QueryClientProvider client={client}>{children}</QueryClientProvider>;
}

beforeEach(() => {
  vi.useFakeTimers();
  vi.clearAllMocks();
  vi.mocked(api.listRunsQueue).mockResolvedValue(api.fallbackRunsQueue);
});

afterEach(() => {
  vi.useRealTimers();
});

describe("useRunQueue", () => {
  it("polls the queue so running backtests leave the queued state without a refresh", async () => {
    const { unmount } = renderHook(() => useRunQueue(), { wrapper });

    await act(async () => {
      await vi.waitFor(() => expect(api.listRunsQueue).toHaveBeenCalledTimes(1));
    });

    await act(async () => {
      await vi.advanceTimersByTimeAsync(2000);
    });

    await act(async () => {
      await vi.waitFor(() => expect(api.listRunsQueue).toHaveBeenCalledTimes(2));
      unmount();
    });
  });
});
