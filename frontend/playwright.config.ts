import {defineConfig, devices} from "@playwright/test";

export default defineConfig({
  testDir: "./tests",
  use: {
    baseURL: "http://127.0.0.1:4173",
    ...devices["Desktop Chrome"],
    launchOptions: {executablePath: process.env.FIS_CHROMIUM_PATH},
  },
  webServer: {
    command: "python ../tests/run_demo_server.py",
    url: "http://127.0.0.1:4173/api/health",
    reuseExistingServer: false,
  },
});
