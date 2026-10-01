import assert from "node:assert/strict";
import { mkdirSync, readFileSync, writeFileSync } from "node:fs";
import { chromium } from "@playwright/test";

const origin = process.env.WEB_URL ?? "http://127.0.0.1:3015";
const output = "../../.cache/p5";
mkdirSync(output, { recursive: true });
const browser = await chromium.launch({
  args: [
    "--use-fake-device-for-media-stream",
    "--use-fake-ui-for-media-stream",
  ],
  ...(process.env.CHROME_EXECUTABLE
    ? { executablePath: process.env.CHROME_EXECUTABLE }
    : {}),
});
const errors = [];
const checks = [];
try {
  for (const locale of ["en", "te", "hi"]) {
    const t = JSON.parse(readFileSync(`messages/${locale}.json`, "utf8")).p5;
    const page = await browser.newPage({
      viewport: { width: 390, height: 844 },
    });
    page.on("pageerror", (error) => errors.push(String(error)));
    await page.addInitScript(() => {
      // Generate a MediaStream locally; OS microphone acquisition is outside this regression.
      Object.defineProperty(navigator.mediaDevices, "getUserMedia", {
        configurable: true,
        value: async () => {
          const context = new AudioContext();
          const oscillator = context.createOscillator();
          const destination = context.createMediaStreamDestination();
          oscillator.connect(destination);
          oscillator.start();
          await context.resume();
          return destination.stream;
        },
      });
      Object.defineProperty(window, "SpeechRecognition", { value: undefined });
      Object.defineProperty(window, "webkitSpeechRecognition", {
        value: undefined,
      });
    });
    await page.goto(`${origin}/${locale}/questions`);
    await page.waitForFunction(
      () => document.querySelector("select")?.options.length > 0,
    );
    await page.getByRole("button", { name: t.search, exact: true }).click();
    await page.getByText(t.available, { exact: true }).waitFor();
    assert((await page.locator("article").count()) >= 5);
    await page.screenshot({
      path: `${output}/${locale}-questions.png`,
      fullPage: true,
    });
    await page.getByLabel(t.role, { exact: true }).fill("Data Analyst");
    await page.getByRole("button", { name: t.search, exact: true }).click();
    await page.getByText(t.none, { exact: true }).waitFor();
    await page.goto(`${origin}/${locale}/prep`);
    await page
      .getByLabel(t.notice, { exact: true })
      .fill(
        `Company: TCS\nRole: Prime\nInterview date: ${new Date(Date.now() + 7 * 86400000).toISOString().slice(0, 10)}\nCTC: 7 LPA\nEligibility: BTech\nRounds: Coding, Technical, HR\nMode: Online\nContact: Ravi Kumar 9876543210`,
      );
    await page.getByRole("button", { name: t.extract, exact: true }).click();
    await page.getByLabel(t.confirm, { exact: true }).waitFor();
    assert(
      await page
        .getByRole("button", { name: t.build, exact: true })
        .isDisabled(),
    );
    assert(!(await page.locator("main").innerText()).includes("9876543210"));
    await page.getByLabel(t.confirm, { exact: true }).check();
    await page.getByRole("button", { name: t.build, exact: true }).click();
    await page.getByText(t.shortfall, { exact: true }).waitFor();
    await page.screenshot({
      path: `${output}/${locale}-prep.png`,
      fullPage: true,
    });
    await page.getByRole("link", { name: t.mock, exact: true }).click();
    await page.getByRole("button", { name: t.start, exact: true }).click();
    await page.getByLabel(t.answer, { exact: true }).waitFor();
    for (let i = 0; i < 5; i++) {
      await page
        .getByLabel(t.answer, { exact: true })
        .fill(
          "In a project our task was clear. I built reports and reduced errors by 20%.",
        );
      await page.getByRole("button", { name: t.submit, exact: true }).click();
      await page.waitForFunction(
        (n) => document.querySelectorAll("mark").length === n,
        i + 1,
      );
    }
    await page.getByText(t.complete, { exact: true }).waitFor();
    await page.screenshot({
      path: `${output}/${locale}-interview.png`,
      fullPage: true,
    });
    assert(
      !(await page.evaluate(
        () => document.documentElement.scrollWidth > innerWidth,
      )),
      `${locale} horizontal overflow`,
    );
    await page.reload();
    await page.getByText(t.complete, { exact: true }).waitFor();
    await page.getByRole("button", { name: t.delete, exact: true }).click();
    await page.getByRole("button", { name: t.start, exact: true }).waitFor();
    await page.getByRole("button", { name: t.start, exact: true }).click();
    await page.getByLabel(t.answer, { exact: true }).waitFor();
    let audioReceived = false;
    await page.route("**/api/engine/interview/transcribe", async (route) => {
      const body = route.request().postDataJSON();
      audioReceived = body.audio.length > 100;
      await route.fulfill({
        json: {
          transcript: "A recorded practice answer.",
          provider: "fixture",
          confirmation_required: true,
        },
      });
    });
    await page.getByRole("button", { name: t.record, exact: true }).click();
    await page.getByRole("button", { name: t.stop, exact: true }).waitFor();
    await new Promise((resolve) => setTimeout(resolve, 600));
    await page.getByRole("button", { name: t.stop, exact: true }).click();
    await page.waitForFunction(
      () =>
        document.querySelector("textarea")?.value ===
        "A recorded practice answer.",
    );
    assert(audioReceived);
    assert.equal(
      await page.locator("mark").count(),
      0,
      "Transcription must not auto-submit an answer",
    );
    await page.getByRole("button", { name: t.submit, exact: true }).click();
    await page.waitForFunction(
      () => document.querySelectorAll("mark").length === 1,
    );
    await page.evaluate(() => {
      Object.defineProperty(navigator.mediaDevices, "getUserMedia", {
        configurable: true,
        value: () => new Promise(() => {}),
      });
    });
    await page.getByRole("button", { name: t.record, exact: true }).click();
    await page.getByRole("button", { name: t.cancelMic, exact: true }).click();
    await page.getByRole("button", { name: t.record, exact: true }).waitFor();
    await page.getByRole("button", { name: t.delete, exact: true }).click();
    await page.getByRole("button", { name: t.start, exact: true }).waitFor();
    checks.push({
      locale,
      questions: 5,
      completed_answers: 5,
      reload_history: true,
      deletion: true,
      mobile_overflow: false,
      recorded_audio: true,
      asr: "stubbed",
      audio_source: "web_audio_generated_stream",
      pending_microphone_cancel: true,
      transcript_confirmation: true,
    });
    await page.close();
  }
  assert.deepEqual(errors, []);
  writeFileSync(
    `${output}/browser-report.json`,
    JSON.stringify({ checks, errors }, null, 2),
  );
  console.log(JSON.stringify({ checks, errors }, null, 2));
} finally {
  await browser.close();
}
