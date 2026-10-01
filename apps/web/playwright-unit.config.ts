import { defineConfig } from "@playwright/test";

// Unit regressions use plain assertions without a page fixture or browser.
export default defineConfig({
  testDir: "./tests/unit",
  fullyParallel: true,
  reporter: "list",
});
