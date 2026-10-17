import { defineConfig, devices } from "@playwright/test";
import path from "node:path";

/**
 * E2E runs against the production topology: FastAPI serving the static export on one
 * origin, with the clearly labelled mock agent (no network, no model cost).
 * Build first: `npm run build`.
 */
const PORT = Number(process.env.E2E_PORT ?? 8010);
const apiDir = path.resolve(__dirname, "../../services/api");

export default defineConfig({
  testDir: "e2e",
  timeout: 60_000,
  fullyParallel: false,
  reporter: [["list"]],
  use: { baseURL: `http://localhost:${PORT}`, trace: "retain-on-failure" },
  projects: [
    { name: "desktop", use: { ...devices["Desktop Chrome"], viewport: { width: 1440, height: 900 } } },
    { name: "mobile", use: { ...devices["Pixel 7"], viewport: { width: 390, height: 844 } } },
  ],
  webServer: {
    command: `uv run uvicorn app.main:app --port ${PORT}`,
    cwd: apiDir,
    url: `http://localhost:${PORT}/api/health`,
    reuseExistingServer: false,
    timeout: 120_000,
    env: {
      AI_MODE: "mock",
      STATIC_DIR: path.resolve(__dirname, "out"),
      CORS_ORIGINS: "",
      RECOVER_RATE_PER_MINUTE: "120",
    },
  },
});
