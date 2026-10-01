import assert from "node:assert/strict";
import { mkdirSync, writeFileSync } from "node:fs";
import { chromium } from "@playwright/test";

const origin = process.env.WEB_URL ?? "http://127.0.0.1:3016";
const output = process.env.BACKGROUND_REPORT_DIR ?? "../../.cache/background";
mkdirSync(output, { recursive: true });
const browser = await chromium.launch();
const checks = [];
try {
  for (const locale of ["en", "te", "hi"]) {
    const page = await browser.newPage({
      viewport: { width: 1440, height: 1000 },
    });
    const errors = [];
    page.on("pageerror", (error) => errors.push(error.message));
    await page.goto(`${origin}/${locale}`);
    await page.waitForFunction(
      () =>
        document.querySelector(".fluid-canvas")?.dataset.state === "running",
    );
    assert.equal(
      await page.evaluate(() => document.documentElement.dataset.theme),
      "dark",
    );
    const canvas = page.locator(".fluid-canvas");
    const first = await canvas.getAttribute("data-frame");
    await page.waitForFunction(
      (previous) =>
        Number(document.querySelector(".fluid-canvas").dataset.frame) >
        Number(previous) + 2,
      first,
    );
    const pixelsBefore = await canvas.screenshot();
    await page.mouse.move(1200, 450);
    await page.waitForFunction(
      () =>
        Number(document.querySelector(".fluid-canvas").dataset.pointerX) > 0.1,
    );
    const pixelsAfter = await canvas.screenshot();
    assert.notDeepEqual(
      pixelsBefore,
      pixelsAfter,
      "The rendered fluid actually changes",
    );
    await page.locator(".feature-ribbon-heading button").click();
    await page.waitForFunction(
      () => document.querySelector(".fluid-canvas").dataset.state === "paused",
    );
    const pausedFrame = await canvas.getAttribute("data-frame");
    await page.waitForTimeout(150);
    assert.equal(await canvas.getAttribute("data-frame"), pausedFrame);
    await page.locator(".feature-ribbon-heading button").click();
    await page.waitForFunction(
      () => document.querySelector(".fluid-canvas").dataset.state === "running",
    );
    await page.locator(".voice-trigger").click();
    await page.waitForFunction(
      () => document.querySelector(".fluid-canvas").dataset.state === "paused",
    );
    await page.keyboard.press("Escape");
    await page.waitForFunction(
      () => document.querySelector(".fluid-canvas").dataset.state === "running",
    );
    await page.emulateMedia({ reducedMotion: "reduce" });
    await page.waitForFunction(
      () => document.querySelector(".fluid-canvas").dataset.state === "paused",
    );
    const stillFrame = await canvas.getAttribute("data-frame");
    await page.waitForTimeout(150);
    assert.equal(await canvas.getAttribute("data-frame"), stillFrame);
    await page.emulateMedia({ reducedMotion: "no-preference" });
    await page.waitForFunction(
      () => document.querySelector(".fluid-canvas").dataset.state === "running",
    );
    await page.goto(`${origin}/${locale}/path`);
    await page.waitForFunction(
      () => document.querySelector(".fluid-canvas").dataset.state === "paused",
    );
    assert.deepEqual(errors, []);
    checks.push({
      locale,
      defaultDark: true,
      renderedPixelChange: true,
      cursorWarp: true,
      pause: true,
      voicePause: true,
      reducedMotion: true,
      graphFrameBudget: true,
    });
    await page.close();
  }
  const fallback = await browser.newPage();
  await fallback.addInitScript(() => {
    const getContext = HTMLCanvasElement.prototype.getContext;
    HTMLCanvasElement.prototype.getContext = function (name, ...args) {
      if (name === "webgl") return null;
      return getContext.call(this, name, ...args);
    };
  });
  await fallback.goto(`${origin}/en`);
  await fallback.waitForFunction(
    () => document.querySelector(".fluid-canvas").dataset.state === "fallback",
  );
  assert(await fallback.locator(".fluid-fallback").isVisible());
  assert(await fallback.locator(".home-actions a").first().isVisible());
  await fallback.close();
  writeFileSync(
    `${output}/report.json`,
    JSON.stringify(
      {
        origin,
        checks,
        noWebGL: "visible static contours and working feature links",
      },
      null,
      2,
    ),
  );
  console.log(
    "Fluid background: rendered motion and cursor response, pause, reduced motion, voice/graph suspension, and no-WebGL fallback passed.",
  );
} finally {
  await browser.close();
}
