import assert from "node:assert/strict";
import { mkdirSync, readFileSync, writeFileSync } from "node:fs";
import { createRequire } from "node:module";
import { chromium } from "@playwright/test";

const origin = process.env.WEB_URL ?? "http://127.0.0.1:3015";
const axeFile =
  process.env.AXE_PATH ??
  createRequire(import.meta.url).resolve("axe-core/axe.min.js");
const output = "../../.cache/redesign";
mkdirSync(output, { recursive: true });
const browser = await chromium.launch();
const checks = [];
const errors = [];
async function accessible(page, label) {
  await page.addScriptTag({ content: readFileSync(axeFile, "utf8") });
  const audit = await page.evaluate(async () =>
    window.axe.run(document, {
      runOnly: { type: "tag", values: ["wcag2a", "wcag2aa", "wcag21aa"] },
    }),
  );
  checks.push({
    label,
    violations: audit.violations.map((v) => ({
      id: v.id,
      impact: v.impact,
      nodes: v.nodes.map((n) => ({
        target: n.target,
        summary: n.failureSummary,
      })),
    })),
  });
}
try {
  for (const locale of ["en", "te", "hi"]) {
    const messages = JSON.parse(
      readFileSync(`messages/${locale}.json`, "utf8"),
    );
    const page = await browser.newPage({
      viewport: { width: 390, height: 844 },
    });
    page.on("pageerror", (error) => errors.push(`${locale}: ${error.message}`));
    for (const route of [
      "",
      "path",
      "leads",
      "schemes",
      "questions",
      "prep",
      "interview",
      "voice",
      "evidence",
    ]) {
      await page.goto(`${origin}/${locale}/${route}`);
      await page.locator("h1").waitFor();
      await page.waitForTimeout(400);
      if (
        !route &&
        (await page.evaluate(
          () => document.documentElement.dataset.theme === "dark",
        ))
      ) {
        await page.locator(".theme-toggle").click();
      }
      assert.equal(
        await page.locator("h1").count(),
        1,
        `${locale}/${route}: single page title`,
      );
      for (const width of [390, 768, 1024, 1440]) {
        await page.setViewportSize({ width, height: 1000 });
        assert(
          !(await page.evaluate(
            () => document.documentElement.scrollWidth > innerWidth,
          )),
          `${locale}/${route}: overflow at ${width}`,
        );
      }
      await accessible(page, `${locale}/${route || "home"}/light`);
      await page.locator(".theme-toggle").click();
      await accessible(page, `${locale}/${route || "home"}/dark`);
      await page.locator(".theme-toggle").click();
    }
    await page.setViewportSize({ width: 390, height: 844 });
    await page.goto(`${origin}/${locale}/path`);
    await page.locator(".skill-map").waitFor();
    await page.locator(".map-node-list button").first().click();
    await page.locator(".map-detail").waitFor();
    assert(
      (await page.locator(".map-detail .source-stamp").innerText()).length > 0,
    );
    await page
      .getByRole("button", { name: messages.path.simulate, exact: true })
      .click();
    await page
      .getByRole("heading", { name: messages.path.after, exact: true })
      .waitFor();
    assert.equal(await page.locator(".path-card:visible").count(), 1);
    await page
      .locator(".comparison-switch")
      .getByRole("button", { name: messages.path.before, exact: true })
      .click();
    assert(
      await page
        .getByRole("heading", { name: messages.path.before, exact: true })
        .isVisible(),
    );
    await page.locator("#navigation-toggle").click();
    assert.equal(
      await page.locator("#navigation-toggle").getAttribute("aria-expanded"),
      "true",
    );
    await page.keyboard.press("Escape");
    assert.equal(
      await page.locator("#navigation-toggle").getAttribute("aria-expanded"),
      "false",
    );
    assert.equal(
      await page.evaluate(() => document.activeElement?.id),
      "navigation-toggle",
    );
    await page
      .getByRole("button", { name: messages.voice.open, exact: true })
      .click();
    await page.getByLabel(messages.voice.textLabel, { exact: true }).waitFor();
    assert(
      await page
        .getByLabel(messages.voice.textLabel, { exact: true })
        .evaluate((input) => document.activeElement === input),
    );
    await accessible(page, `${locale}/voice-popover`);
    await page.keyboard.press("Escape");
    assert(
      !(await page
        .getByLabel(messages.voice.textLabel, { exact: true })
        .isVisible()),
    );
    await page.locator(".theme-toggle").click();
    await page.reload();
    await page.waitForFunction(
      () => document.documentElement.dataset.theme === "dark",
    );
    await page.locator(".theme-toggle").click();
    // Only the failure condition is simulated; recovery uses the real local API.
    await page.route("**/api/engine/ready**", (route) =>
      route.fulfill({
        status: 503,
        contentType: "application/json",
        body: JSON.stringify({ detail: "Engine unavailable" }),
      }),
    );
    await page.goto(`${origin}/${locale}`);
    await page
      .getByText(messages.workspace.offlineNotice, { exact: true })
      .waitFor();
    await page.unroute("**/api/engine/ready**");
    await page.locator(".connection-banner button").click();
    await page.waitForFunction(
      () => !document.querySelector(".connection-banner"),
    );
    await page.close();
  }
  writeFileSync(
    `${output}/accessibility.json`,
    JSON.stringify({ checks, errors }, null, 2),
  );
  assert.equal(errors.length, 0, errors.join("\n"));
  const violations = checks.filter((check) => check.violations.length);
  assert.equal(violations.length, 0, JSON.stringify(violations, null, 2));
  console.log(
    `Passed: ${checks.length} accessibility states, 108 responsive route checks, all three locales; map, comparison, menus, voice focus, themes and offline recovery.`,
  );
} finally {
  await browser.close();
}
