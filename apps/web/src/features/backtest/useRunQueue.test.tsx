import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { act, renderHook } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import * as api from "../../lib/api";
import { qk } from "../../lib/qk";
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

  it("stops polling once no run is queued or running", async () => {
    vi.mocked(api.listRunsQueue).mockResolvedValue([]);
    const { unmount } = renderHook(() => useRunQueue(), { wrapper });

    await act(async () => {
      await vi.waitFor(() => expect(api.listRunsQueue).toHaveBeenCalledTimes(1));
    });

    await act(async () => {
      await vi.advanceTimersByTimeAsync(10_000);
    });

    expect(api.listRunsQueue).toHaveBeenCalledTimes(1);
    unmount();
  });

  it("resumes polling when a submitted run lands in the idle queue cache", async () => {
    vi.mocked(api.listRunsQueue).mockResolvedValue([]);
    const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
    const { unmount } = renderHook(() => useRunQueue(), {
      wrapper: ({ children }: { children: React.ReactNode }) => (
        <QueryClientProvider client={client}>{children}</QueryClientProvider>
      ),
    });

    await act(async () => {
      await vi.waitFor(() => expect(api.listRunsQueue).toHaveBeenCalledTimes(1));
    });

    await act(async () => {
      client.setQueryData(qk.runs.queue(), [api.fallbackRunsQueue[5]]);
      await vi.advanceTimersByTimeAsync(2000);
    });

    expect(api.listRunsQueue).toHaveBeenCalledTimes(2);
    unmount();
  });
});
