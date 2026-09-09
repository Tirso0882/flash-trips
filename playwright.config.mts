import { defineConfig } from "@playwright/test";

export default defineConfig({
  fullyParallel: false,
  globalSetup: "./tests/journey/global-setup.mts",
  reporter: "line",
  testDir: "./tests/journey",
  testMatch: "**/*.journey.mts",
  timeout: 30_000,
  use: {
    ignoreHTTPSErrors: true,
    trace: "retain-on-failure",
  },
  workers: 1,
});
