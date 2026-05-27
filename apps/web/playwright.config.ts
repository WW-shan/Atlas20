import { defineConfig } from "@playwright/test";
import { dirname, resolve } from "node:path";
import { fileURLToPath } from "node:url";

const configDir = dirname(fileURLToPath(import.meta.url));
const repoRoot = resolve(configDir, "../..");

export default defineConfig({
  testDir: "./e2e",
  timeout: 60_000,
  expect: {
    timeout: 10_000,
  },
  fullyParallel: false,
  reporter: [["list"]],
  use: {
    baseURL: "http://127.0.0.1:5173",
    colorScheme: "dark",
    viewport: { width: 1440, height: 1200 },
    trace: "retain-on-failure",
    screenshot: "only-on-failure",
    video: "retain-on-failure",
  },
  outputDir: resolve(repoRoot, "output/playwright"),
  webServer: [
    {
      command: "python -m uvicorn atlas20.api.app:create_app --factory --host 127.0.0.1 --port 8000",
      cwd: repoRoot,
      env: {
        PYTHONPATH: resolve(repoRoot, "src"),
      },
      url: "http://127.0.0.1:8000/healthz",
      reuseExistingServer: true,
      timeout: 120_000,
    },
    {
      command: "npm run dev",
      cwd: configDir,
      url: "http://127.0.0.1:5173",
      reuseExistingServer: true,
      timeout: 120_000,
    },
  ],
});
