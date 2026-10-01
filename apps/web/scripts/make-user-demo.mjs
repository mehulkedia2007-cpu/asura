import assert from "node:assert/strict";
import { execFileSync, spawnSync } from "node:child_process";
import {
  mkdirSync,
  mkdtempSync,
  readFileSync,
  rmSync,
  writeFileSync,
} from "node:fs";
import { tmpdir } from "node:os";
import { join, resolve } from "node:path";
import { chromium } from "@playwright/test";

const origin = process.env.WEB_URL ?? "http://localhost:3000";
const repoRoot = resolve("../..");
const output = join(repoRoot, "docs", "DAARI-user-demo.mp4");
const temp = mkdtempSync(join(tmpdir(), "daari-user-demo-"));
const frameDir = join(temp, "frames");
const audioDir = join(temp, "audio");
const segmentDir = join(temp, "segments");
for (const dir of [frameDir, audioDir, segmentDir]) mkdirSync(dir);

const scenes = [];
const browser = await chromium.launch();
const context = await browser.newContext({
  viewport: { width: 1440, height: 900 },
  colorScheme: "light",
});
const page = await context.newPage();
page.setDefaultTimeout(20_000);

function say(text, path) {
  const result = spawnSync(
    "/usr/bin/say",
    ["-v", "Aman", "-r", "170", "-o", path, "--data-format=LEI16@44100", text],
    { encoding: "utf8" },
  );
  if (result.status !== 0) {
    throw new Error(result.stderr || "macOS speech synthesis failed");
  }
}

function audioDuration(path) {
  return Number(
    execFileSync(
      "/opt/homebrew/bin/ffprobe",
      [
        "-v",
        "error",
        "-show_entries",
        "format=duration",
        "-of",
        "default=noprint_wrappers=1:nokey=1",
        path,
      ],
      { encoding: "utf8" },
    ).trim(),
  );
}

function escapeHtml(value) {
  return value
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#39;");
}

async function capture(title, narration) {
  const index = scenes.length + 1;
  const raw = await page.screenshot({ type: "png" });
  const frame = join(frameDir, `${String(index).padStart(2, "0")}.png`);
  const voice = join(audioDir, `${String(index).padStart(2, "0")}.wav`);
  const slide = await context.newPage();
  await slide.setViewportSize({ width: 1280, height: 720 });
  await slide.setContent(`<!doctype html>
    <html><head><meta charset="utf-8"><style>
      *{box-sizing:border-box}html,body{margin:0;width:1280px;height:720px;overflow:hidden;background:#171816;color:#f7f3eb;font-family:Arial,Helvetica,sans-serif}
      .screen{position:absolute;inset:0;width:1280px;height:720px;object-fit:cover}
      .shade{position:absolute;inset:0;background:linear-gradient(180deg,rgba(20,21,19,.72) 0,transparent 20%,transparent 55%,rgba(20,21,19,.25) 66%,rgba(20,21,19,.98) 100%)}
      .brand{position:absolute;top:20px;left:38px;font-size:18px;font-weight:700;letter-spacing:.18em}
      .badge{position:absolute;top:22px;right:38px;padding:8px 12px;border:1px solid rgba(247,243,235,.55);border-radius:3px;font-size:12px;letter-spacing:.12em;text-transform:uppercase}
      .copy{position:absolute;left:56px;right:56px;bottom:28px}
      .step{color:#f18965;font-family:monospace;font-size:15px;letter-spacing:.16em;text-transform:uppercase}
      h1{font-family:Georgia,serif;font-weight:400;font-size:42px;line-height:1.05;margin:10px 0 9px}
      p{font-size:19px;line-height:1.35;max-width:1120px;margin:0;color:#f2eee6}
    </style></head><body>
      <img class="screen" src="data:image/png;base64,${raw.toString("base64")}" />
      <div class="shade"></div><div class="brand">DAARI</div>
      <div class="badge">User walkthrough · Sample journey</div>
      <div class="copy"><div class="step">${String(index).padStart(2, "0")} / 14 · DAARI</div>
      <h1>${escapeHtml(title)}</h1><p>${escapeHtml(narration)}</p></div>
    </body></html>`);
  await slide.screenshot({ path: frame, type: "png" });
  await slide.close();
  say(narration, voice);
  scenes.push({ frame, voice, duration: audioDuration(voice) });
}

async function waitForLiveResults() {
  const busy = page.getByRole("status");
  await busy.waitFor({ timeout: 10_000 });
  await busy.waitFor({ state: "detached", timeout: 90_000 });
  await page.waitForFunction(() => {
    const main = document.querySelector("main");
    return Boolean(
      main?.querySelector("article") ||
        main?.innerText.includes("No source-backed results are available") ||
        main?.querySelector('[role="alert"]'),
    );
  });
}

async function clickButton(name) {
  await page.getByRole("button", { name, exact: true }).click();
}

try {
  const messages = JSON.parse(readFileSync("messages/en.json", "utf8"));
  await page.goto(`${origin}/en`);
  await page.getByRole("heading", { name: "DAARI", exact: true }).waitFor();
  await capture(
    "Start with your goal",
    "Welcome to DAARI. Use My path to plan skills, job leads and government schemes to explore opportunities, Interview intelligence to see reported questions, and Placement prep to build a study plan. The same features are available in English, Telugu and Hindi.",
  );

  await page.goto(`${origin}/en/path`);
  await page
    .getByRole("button", { name: messages.path.simulate, exact: true })
    .waitFor();
  await page
    .getByLabel(messages.path.skill, { exact: true })
    .selectOption("sql_querying");
  await capture(
    "Choose a role and skill",
    "On My path, choose Student or Rural learner, select a goal role, then choose a skill and your current level. The roadmap lists prerequisites, required skills, estimated hours and the overall study time.",
  );
  await clickButton(messages.path.simulate);
  await page
    .getByRole("heading", { name: messages.path.after, exact: true })
    .waitFor();
  await page
    .getByRole("heading", { name: messages.path.after, exact: true })
    .scrollIntoViewIfNeeded();
  await capture(
    "Compare the skill update",
    "Select Simulate skill update to compare your current roadmap with the plan after learning SQL. DAARI explains what changed, updates your saved skill level, and shows how the path moves toward your goal.",
  );
  await clickButton(messages.path.shock);
  await page
    .getByRole("heading", { name: messages.path.after, exact: true })
    .waitFor();
  await capture(
    "Explore market demand",
    "Market shock lets you explore how more job listings for a skill could change the roadmap. It is a scenario tool, so use it to understand trade-offs rather than as a promise of a job.",
  );
  await clickButton(messages.path.assess);
  const answer = page.getByRole("textbox", {
    name: messages.path.answer,
    exact: true,
  });
  await answer.waitFor();
  await answer.fill("SELECT employee_id FROM employees;");
  await clickButton(messages.path.submit);
  await page.getByRole("status").last().waitFor();
  await capture(
    "Check a skill with a short assessment",
    "Choose Assess this skill to answer a short adaptive question. Submit your response to see the expected answer, explanation, estimated level and uncertainty. The questions help estimate a level; you can still edit your own skills.",
  );

  await page.goto(`${origin}/en/leads`);
  await page
    .getByLabel(messages.live.query, { exact: true })
    .fill("Data Analyst");
  await page
    .getByLabel(messages.live.place, { exact: true })
    .fill("Guntur, Andhra Pradesh");
  await clickButton(messages.live.search);
  await waitForLiveResults();
  await capture(
    "Search nearby job leads",
    "In Live job leads, enter a role or keyword and a town or district. Review each result's source, location, match details and risk signals. If sources have no current results, try another term or open the source directly.",
  );

  await page.goto(`${origin}/en/schemes`);
  await page.getByLabel(messages.live.query, { exact: true }).fill("student");
  await clickButton(messages.live.search);
  await waitForLiveResults();
  await capture(
    "Check government schemes",
    "Search Government schemes by a need such as student support. Add profile facts when you have them to check source-backed rules. Eligibility stays unknown when the available sources do not support a decision, and every record links back to its source.",
  );

  await page.goto(`${origin}/en/questions`);
  await page.waitForFunction(
    () => document.querySelector("select")?.options.length > 0,
  );
  await clickButton(messages.p5.search);
  await page.getByText(messages.p5.available, { exact: true }).waitFor();
  await capture(
    "Review interview reports",
    "Interview intelligence lets you search company and role reports, filter by topic or round, and inspect source dates. Candidate reports describe past experiences; they do not predict what you will be asked.",
  );
  await page.getByLabel(messages.p5.role, { exact: true }).fill("Data Analyst");
  await clickButton(messages.p5.search);
  await page.getByText(messages.p5.none, { exact: true }).waitFor();
  await capture(
    "Use practice when reports are missing",
    "Coverage depends on the company and role. When DAARI has no report for a search, that is shown clearly; you can still practise with the skill question bank instead of treating missing reports as evidence.",
  );

  await page.goto(`${origin}/en/prep`);
  await page
    .getByLabel(messages.p5.notice, { exact: true })
    .fill(
      "Company: Example Analytics\nRole: Data Analyst\nInterview date: 2026-11-30\nCTC: 7 LPA\nEligibility: BTech\nRounds: Coding, Technical, HR\nMode: Online",
    );
  await clickButton(messages.p5.extract);
  await page.getByLabel(messages.p5.confirm, { exact: true }).waitFor();
  await page.getByLabel(messages.p5.confirm, { exact: true }).check();
  await clickButton(messages.p5.build);
  await page.getByText(messages.p5.shortfall, { exact: true }).waitFor();
  await capture(
    "Turn a notice into a prep plan",
    "Paste a placement notice. Check every extracted field against the original, correct anything uncertain, and confirm before building the plan. DAARI orders practice by prerequisite and interview date, then shows whether the available study hours are enough.",
  );

  await page.goto(`${origin}/en/interview`);
  await clickButton(messages.p5.start);
  await page.getByLabel(messages.p5.answer, { exact: true }).waitFor();
  for (let index = 0; index < 5; index++) {
    await page
      .getByLabel(messages.p5.answer, { exact: true })
      .fill(
        "I used SQL to check the data, explained the result, and worked with my team on the next step.",
      );
    await clickButton(messages.p5.submit);
    await page.waitForFunction(
      (count) => document.querySelectorAll("mark").length === count,
      index + 1,
    );
  }
  await page.getByText(messages.p5.complete, { exact: true }).waitFor();
  await capture(
    "Practise and review your answers",
    "Start a five-question practice session, answer in your own words, and review feedback tied to your transcript. Your attempt history survives a reload for up to 24 hours. Delete a practice session when you are finished.",
  );
  await clickButton(messages.p5.delete);
  await page
    .getByRole("button", { name: messages.p5.start, exact: true })
    .waitFor();

  await page.goto(`${origin}/en/voice`);
  const voiceInput = page.getByRole("textbox", {
    name: messages.voice.textLabel,
    exact: true,
  });
  await voiceInput.fill("Show me a roadmap to become a data analyst.");
  await clickButton(messages.voice.send);
  await page
    .getByText(messages.voice.answer, { exact: true })
    .waitFor({ timeout: 100_000 });
  await capture(
    "Ask DAARI by voice or text",
    "Ask DAARI a question by speaking or typing. The voice assistant can look up your path, nearby jobs and government schemes, then show evidence links for supported answers. If your microphone is unavailable, typing remains available.",
  );

  await page.goto(`${origin}/en/evidence`);
  await page.getByRole("heading", { level: 1 }).waitFor();
  await page.waitForFunction(
    () => !document.body.innerText.includes("Assembling the evidence board…"),
    { timeout: 30_000 },
  );
  await capture(
    "Understand the evidence and limits",
    "The Evidence board shows regression results, source coverage, grounding checks, voice measurements and limitations. Read its scope before relying on any metric: test fixtures and cached rehearsals are not field validation.",
  );

  await page.goto(`${origin}/te`);
  await page.locator("main h1").waitFor();
  await capture(
    "Continue in your language",
    "Use the language control to switch between English, Telugu and Hindi. DAARI keeps you on the same feature when the language changes, so you can continue your path, search or practice in the language you prefer.",
  );

  await browser.close();
  for (const [index, scene] of scenes.entries()) {
    const segment = join(
      segmentDir,
      `${String(index + 1).padStart(2, "0")}.mp4`,
    );
    const fadeOut = Math.max(0.1, scene.duration - 0.3).toFixed(3);
    execFileSync(
      "/opt/homebrew/bin/ffmpeg",
      [
        "-y",
        "-loop",
        "1",
        "-framerate",
        "30",
        "-i",
        scene.frame,
        "-i",
        scene.voice,
        "-vf",
        `scale=1280:720,format=yuv420p,fade=t=in:st=0:d=0.25,fade=t=out:st=${fadeOut}:d=0.25`,
        "-af",
        "aresample=48000,afade=t=in:st=0:d=0.12",
        "-c:v",
        "libx264",
        "-preset",
        "veryfast",
        "-crf",
        "22",
        "-c:a",
        "aac",
        "-b:a",
        "128k",
        "-t",
        scene.duration.toFixed(3),
        "-shortest",
        segment,
      ],
      { stdio: "ignore" },
    );
  }
  const list = join(temp, "segments.txt");
  writeFileSync(
    list,
    scenes
      .map(
        (_scene, index) =>
          `file '${join(segmentDir, `${String(index + 1).padStart(2, "0")}.mp4`)}'`,
      )
      .join("\n"),
  );
  mkdirSync(join(repoRoot, "docs"), { recursive: true });
  execFileSync(
    "/opt/homebrew/bin/ffmpeg",
    [
      "-y",
      "-f",
      "concat",
      "-safe",
      "0",
      "-i",
      list,
      "-c",
      "copy",
      "-movflags",
      "+faststart",
      output,
    ],
    { stdio: "ignore" },
  );
  const seconds = audioDuration(output);
  assert(scenes.length === 14, `Expected 14 chapters, got ${scenes.length}`);
  console.log(
    JSON.stringify({
      output,
      chapters: scenes.length,
      duration_seconds: Math.round(seconds),
    }),
  );
} finally {
  if (!browser.isConnected()) {
    rmSync(temp, { recursive: true, force: true });
  } else {
    await browser.close();
    rmSync(temp, { recursive: true, force: true });
  }
}
