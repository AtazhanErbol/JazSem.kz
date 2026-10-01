import { defineConfig } from "@playwright/test";
if (process.env.CI && !process.env.DEV_SEED_PASSWORD)
  throw new Error(
    "CI requires DEV_SEED_PASSWORD and isolated seeded services; mandatory E2E cannot be skipped.",
  );
export default defineConfig({
  testDir: "./e2e",
  timeout: 60000,
  use: {
    baseURL: process.env.E2E_BASE_URL || "http://127.0.0.1:5173",
    trace: "retain-on-failure",
  },
  reporter: "list",
  workers: 1,
});
