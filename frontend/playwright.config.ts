import { defineConfig } from "@playwright/test";
export default defineConfig({
  testDir: "../tests/e2e",
  timeout: 60000,
  expect: { timeout: 12000 },
  fullyParallel: false,
  workers: 1,
  reporter: [
    ["list"],
    ["html", { outputFolder: "../data/playwright-report", open: "never" }],
    ["junit", { outputFile: "../data/playwright-results.xml" }],
  ],
  use: {
    baseURL: process.env.E2E_BASE_URL || "http://127.0.0.1:8000",
    headless: true,
    viewport: { width: 1440, height: 1000 },
    screenshot: "only-on-failure",
    trace: "off",
  },
  outputDir: "../data/playwright-artifacts",
});
