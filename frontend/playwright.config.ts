import { defineConfig } from "@playwright/test";
export default defineConfig({
  testDir: "./e2e",
  timeout: 60000,
  workers: 1,
  use: {
    baseURL: `http://127.0.0.1:${process.env.STUDIO_TEST_PORT || "8000"}`,
    browserName: "chromium",
    launchOptions: {
      executablePath:
        process.env.CHROMIUM_PATH ||
        (process.env.STUDIO_TEST_BROWSER === "bundled"
          ? undefined
          : process.platform === "linux"
            ? "/usr/bin/chromium"
            : undefined),
      args: ["--no-sandbox"],
    },
    viewport: { width: 1440, height: 1000 },
  },
  reporter: "list",
  webServer: process.env.CI
    ? {
        command: "python ../scripts/test-server.py",
        url: `http://127.0.0.1:${process.env.STUDIO_TEST_PORT || "8000"}/api/health`,
        reuseExistingServer: false,
        timeout: 30000,
      }
    : undefined,
});
