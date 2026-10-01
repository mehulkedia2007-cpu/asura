import assert from "node:assert/strict";
import { mkdirSync, readFileSync, writeFileSync } from "node:fs";
import { createRequire } from "node:module";
import { chromium } from "@playwright/test";

const origin = process.env.WEB_URL ?? "http://127.0.0.1:3016";
const output = process.env.MOTION_REPORT_DIR ?? "../../.cache/motion";
const axe = readFileSync(
  createRequire(import.meta.url).resolve("axe-core/axe.min.js"),
  "utf8",
);
mkdirSync(output, { recursive: true });
const browser = await chromium.launch();
const checks = [];
const errors = [];
try {
  for (const locale of ["en", "te", "hi"]) {
    const messages = JSON.parse(
      readFileSync(`messages/${locale}.json`, "utf8"),
    );
    const page = await browser.newPage({
      viewport: { width: 1440, height: 1000 },
    });
    page.on("pageerror", (error) => errors.push(error.message));
    // Trace actual Web Audio nodes without replacing audio behavior.
    await page.addInitScript(() => {
      window.__tones = [];
      const oscillator = AudioContext.prototype.createOscillator;
      AudioContext.prototype.createOscillator = function (...args) {
        const node = oscillator.apply(this, args);
        const start = node.start.bind(node);
        node.start = (...values) => {
          window.__tones.push({
            frequency: node.frequency.value,
            state: this.state,
          });
          return start(...values);
        };
        return node;
      };
    });
    await page.goto(`${origin}/${locale}`);
    await page.locator(".feature-track").waitFor();
    const brand = await page
      .locator(".workspace-brand .brand-mark")
      .boundingBox();
    assert(brand.width >= 30, "Desktop direction mark keeps its width");
    assert.equal(
      await page
        .locator(".workspace-brand .brand-lockup")
        .evaluate((el) => getComputedStyle(el).fontSize),
      "24px",
    );
    assert.equal(await page.locator(".feature-set a").count(), 8);
    for (const route of [
      "path",
      "leads",
      "schemes",
      "questions",
      "prep",
      "interview",
      "voice",
      "evidence",
    ]) {
      assert.equal(
        await page
          .locator(`.feature-set a[href="/${locale}/${route}"]`)
          .count(),
        1,
      );
    }
    await page.mouse.move(800, 150);
    await page.locator(".cursor-orbit").waitFor();
    await page
      .getByRole("button", { name: messages.experience.pause, exact: true })
      .click();
    assert.equal(
      await page
        .locator(".feature-track")
        .evaluate((el) => getComputedStyle(el).animationPlayState),
      "paused",
    );
    await page
      .getByRole("button", { name: messages.experience.play, exact: true })
      .click();

    await page.locator(".journey-start").click();
    assert.equal(
      await page.locator("dialog").evaluate((el) => el.matches(":modal")),
      true,
    );
    assert.equal(
      await page
        .locator("dialog")
        .evaluate((el) => el.contains(document.activeElement)),
      true,
    );
    for (const width of [390, 768, 1440]) {
      await page.setViewportSize({ width, height: 1000 });
      assert.equal(
        await page.evaluate(
          () => document.documentElement.scrollWidth > innerWidth,
        ),
        false,
      );
      const box = await page.locator("dialog").boundingBox();
      assert(box.x >= 0 && box.x + box.width <= width);
    }
    await page.addScriptTag({ content: axe });
    for (const dark of [false, true]) {
      await page.evaluate((isDark) => {
        document.documentElement.dataset.theme = isDark ? "dark" : "light";
      }, dark);
      const audit = await page.evaluate(() =>
        window.axe.run(document, {
          runOnly: { type: "tag", values: ["wcag2a", "wcag2aa", "wcag21aa"] },
        }),
      );
      assert.deepEqual(
        audit.violations.map((v) => ({
          id: v.id,
          nodes: v.nodes.map((n) => n.target),
        })),
        [],
      );
    }
    await page.locator(".journey-stage-picker button").nth(1).click();
    assert.equal(
      await page.locator(".journey-stage-links a").first().getAttribute("href"),
      `/${locale}/path`,
    );
    await page.locator(".journey-stage-picker button").nth(2).click();
    assert.equal(
      await page.locator(".journey-stage-links a").first().getAttribute("href"),
      `/${locale}/leads`,
    );
    await page.keyboard.press("Escape");
    assert.equal(await page.locator("dialog").evaluate((el) => el.open), false);
    assert.equal(
      await page
        .locator(".journey-start")
        .evaluate((el) => el === document.activeElement),
      true,
    );
    await page.setViewportSize({ width: 1440, height: 1000 });

    await page.locator(".home-actions a").first().click();
    await page.waitForURL(`**/${locale}/path`);
    await page.waitForFunction(() => window.__tones.length > 0);
    assert.equal(await page.evaluate(() => window.__tones[0].state), "running");
    await page.locator(".sound-toggle").click();
    const beforeMute = await page.evaluate(() => window.__tones.length);
    await page.locator('.workspace-nav-link[href$="/prep"]').click();
    await page.waitForURL(`**/${locale}/prep`);
    assert.equal(await page.evaluate(() => window.__tones.length), beforeMute);
    await page.reload();
    await page.waitForFunction(
      () =>
        document
          .querySelector(".sound-toggle")
          ?.getAttribute("aria-pressed") === "false",
    );
    assert.equal(
      await page.locator(".sound-toggle").getAttribute("aria-pressed"),
      "false",
    );
    await page.locator(".sound-toggle").click();
    await page.locator(".voice-trigger").click();
    await page.waitForFunction(
      () => document.documentElement.dataset.motionPaused === "true",
    );
    assert.equal(await page.locator(".cursor-orbit").count(), 0);
    const beforeVoice = await page.evaluate(() => window.__tones.length);
    await page.locator('.workspace-nav-link[href$="/questions"]').click();
    await page.waitForURL(`**/${locale}/questions`);
    assert.equal(await page.evaluate(() => window.__tones.length), beforeVoice);

    await page.goto(`${origin}/${locale}`);
    await page.emulateMedia({ reducedMotion: "reduce" });
    await page.waitForFunction(() => !document.querySelector(".cursor-orbit"));
    assert.equal(
      await page
        .locator(".feature-track")
        .evaluate((el) => getComputedStyle(el).animationName),
      "none",
    );
    await page.locator(".feature-set a").first().focus();
    assert.equal(await page.locator(".feature-copy").isVisible(), false);
    await page.locator(".journey-start").click();
    await page.locator(".journey-stage-picker button").nth(1).click();
    await page.locator(".journey-stage-links a").first().click();
    await page.waitForURL(`**/${locale}/path`);
    assert.equal(await page.locator("dialog[open]").count(), 0);
    checks.push({
      locale,
      featureLinks: 8,
      dialogWidths: [390, 768, 1440],
      dialogAccessibility: ["light", "dark"],
      navigationAudio:
        "real Web Audio oscillator started; mute persisted; voice suppressed tones",
      reducedMotion: "static icons, no cursor, working journey links",
      escapeFocus: "passed",
    });
    await page.close();
  }
  const touch = await browser.newPage({
    viewport: { width: 390, height: 844 },
    isMobile: true,
    hasTouch: true,
  });
  await touch.goto(`${origin}/en`);
  const mobileBrand = await touch
    .locator(".mobile-brand .brand-mark")
    .boundingBox();
  assert(mobileBrand.width >= 18, "Mobile direction mark keeps its width");
  assert.equal(await touch.locator(".cursor-orbit").count(), 0);
  assert.equal(
    await touch.evaluate(
      () => document.documentElement.scrollWidth > innerWidth,
    ),
    false,
  );
  await touch.close();
  assert.deepEqual(errors, []);
  writeFileSync(
    `${output}/report.json`,
    JSON.stringify({ origin, checks, touch: "passed", errors }, null, 2),
  );
  console.log(
    `Motion checks passed in all three languages; report: ${output}/report.json`,
  );
} finally {
  await browser.close();
}
