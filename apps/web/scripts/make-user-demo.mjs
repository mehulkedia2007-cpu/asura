// Actual browser actions and server responses. RECORD=0 runs the same checks without narration.
import assert from "node:assert/strict";
import { execFileSync } from "node:child_process";
import { mkdirSync, mkdtempSync, readFileSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { join, resolve } from "node:path";
import { chromium } from "@playwright/test";

const origin = process.env.WEB_URL ?? "http://127.0.0.1:3017";
const record = process.env.RECORD !== "0";
const dir = mkdtempSync(join(tmpdir(), "daari-demo-"));
const docs = resolve("../../docs");
const proofDir = resolve("../../.cache/user-demo");
mkdirSync(proofDir, { recursive: true });
const t = JSON.parse(readFileSync("messages/en.json", "utf8"));
const chapters = [];
const proof = {
  origin,
  checked_at: new Date().toISOString(),
  sample_notice: true,
};
const browser = await chromium.launch();
const context = await browser.newContext({
  viewport: { width: 1280, height: 800 },
  colorScheme: "light",
  ...(record
    ? { recordVideo: { dir, size: { width: 1280, height: 800 } } }
    : {}),
});
const page = await context.newPage();
const started = Date.now();
page.setDefaultTimeout(30000);
const errors = [];
page.on("pageerror", (e) => errors.push(e.message));
const button = (name) => page.getByRole("button", { name, exact: true });
async function go(route) {
  await page.goto(`${origin}/en${route}`);
  await page.locator("main h1").waitFor();
}
async function click(endpoint, name) {
  const pending = page.waitForResponse(
    (r) => r.url().endsWith(endpoint) && r.request().method() === "POST",
    { timeout: 120000 },
  );
  await button(name).click();
  const response = await pending;
  assert(response.ok(), `${endpoint}: ${response.status()}`);
  return response.json();
}
function duration(file) {
  return Number(
    execFileSync(
      "/opt/homebrew/bin/ffprobe",
      [
        "-v",
        "error",
        "-show_entries",
        "format=duration",
        "-of",
        "csv=p=0",
        file,
      ],
      { encoding: "utf8" },
    ).trim(),
  );
}
async function scene(title, narration, action) {
  const voice = join(dir, `${chapters.length}.wav`);
  if (record)
    execFileSync("/usr/bin/say", [
      "-v",
      "Aman",
      "-r",
      "155",
      "-o",
      voice,
      "--data-format=LEI16@44100",
      narration,
    ]);
  const start = (Date.now() - started) / 1000;
  await action();
  await page.screenshot({ path: join(proofDir, `${chapters.length + 1}.png`) });
  if (record)
    await page.waitForTimeout(
      Math.max(
        2500,
        duration(voice) * 1000 - (Date.now() - started - start * 1000) + 1500,
      ),
    );
  chapters.push({
    title,
    narration,
    voice,
    start,
    end: (Date.now() - started) / 1000,
  });
  console.log(`PASS: ${title}`);
}
try {
  await scene(
    "Start here",
    "Welcome to DAARI. This recording uses the working website. My learning path helps you plan skills. Job opportunities helps you find work. Government support helps you explore schemes. Get interview ready has three steps: read past questions, make a preparation plan, and practise your answers. Each page has simple instructions.",
    async () => {
      await go("");
    },
  );
  await scene(
    "Choose from 20 learning paths",
    "Choose the job you want from twenty starter career paths, including office assistant, customer support and data analyst. Select a skill you already know and save it. The learning steps and estimated hours update. These starting plans are not a complete qualification or a promise of employment.",
    async () => {
      await go("/path");
      const select = page.getByLabel(t.path.goal, { exact: true });
      await page.waitForFunction(() =>
        [...document.querySelectorAll("select")].some(
          (s) => s.options.length === 20,
        ),
      );
      proof.roles = await select.locator("option").count();
      assert.equal(proof.roles, 20);
      await select.selectOption("office_assistant");
      await page.locator(".skill-map").waitFor();
      await select.selectOption("data_analyst");
      await page
        .getByLabel(t.path.skill, { exact: true })
        .selectOption("sql_querying");
      await click("/simulate-skill-update", t.path.simulate);
      await page
        .getByRole("heading", { name: t.path.after, exact: true })
        .scrollIntoViewIfNeeded();
    },
  );
  await scene(
    "Search real job sources",
    "Choose Sales and shop work, enter Vijayawada in Andhra Pradesh, and press Search. Results show the employer, location, source and date. Open the original advertisement before applying. If no jobs match your search, try another town or role, or choose remote work. A result is not a guarantee that the vacancy is still open.",
    async () => {
      await go("/leads");
      await page
        .getByLabel(t.live.chooseJob, { exact: true })
        .selectOption("sales");
      await page
        .getByLabel(t.live.place, { exact: true })
        .fill("Vijayawada, Andhra Pradesh");
      const data = await click("/leads/search", t.live.search);
      assert.equal(data.region, "Andhra Pradesh");
      assert.equal(data.include_remote, false);
      assert(
        data.leads.every(
          (x) => !x.remote && x.source_url && x.distance_km <= 100,
        ),
      );
      proof.jobs = {
        count: data.leads.length,
        errors: data.errors,
        query: "sales",
        place: "Vijayawada, Andhra Pradesh",
      };
      if (data.leads.length)
        await page.locator(".result-card").first().scrollIntoViewIfNeeded();
      else await page.getByText(t.live.noData, { exact: true }).waitFor();
    },
  );
  await scene(
    "Choose a government scheme",
    "Choose a need such as training, or a named scheme from the official-source library. Here we select FutureSkills Prime and search. These are Andhra Pradesh or national schemes. Saved details may be older. Open the source to check the current rules and application process. DAARI does not claim you qualify when the rules are incomplete.",
    async () => {
      await go("/schemes");
      const select = page.getByLabel(t.live.chooseScheme, { exact: true });
      await select
        .locator('option[value="scheme:fspip"]')
        .waitFor({ state: "attached" });
      await select.selectOption("scheme:fspip");
      const data = await click("/schemes/search", t.live.search);
      assert.equal(data.schemes.length, 1);
      assert.equal(data.schemes[0].id, "fspip");
      assert(data.schemes[0].url);
      proof.scheme = {
        id: data.schemes[0].id,
        url: data.schemes[0].url,
        eligibility: data.schemes[0].eligibility.status,
        stale: data.stale,
      };
      await page.locator(".result-card").first().scrollIntoViewIfNeeded();
    },
  );
  await scene(
    "Use the question library",
    "Choose a company and its job title, then search reports. Read questions shared by past candidates and check the source and date. These reports do not predict your interview. If your company or role has no reports, use Interview practice to work on skills instead.",
    async () => {
      await go("/questions");
      await page.waitForFunction(
        () => document.querySelector("select")?.options.length > 0,
      );
      const data = await click("/questions/search", t.p5.search);
      proof.question_library = { count: data.questions.length };
      assert(data.questions.length > 0);
      await page.locator(".result-card").first().scrollIntoViewIfNeeded();
    },
  );
  await scene(
    "Paste a placement notice: practice example",
    "Open Preparation plan and paste your college placement notice. I am using the sample button so you can repeat these steps. Example Analytics is a fictional practice company, not a real opening. Read notice extracts the company, job title and interview date. The original text stays visible so you can compare the details.",
    async () => {
      await go("/prep");
      await button(t.p5.sampleNotice).click();
      const notice = page.getByLabel(t.p5.notice, { exact: true });
      const sample = await notice.inputValue();
      assert(sample.includes("practice only"));
      await notice.fill("");
      await notice.fill(sample);
      const data = await click("/prep/notice", t.p5.extract);
      assert.equal(
        data.fields.company.value,
        "Example Analytics (practice only)",
      );
      assert.equal(data.fields.role.value, "Data Analyst");
      proof.notice = {
        company: data.fields.company.value,
        role: data.fields.role.value,
        interview_date: data.fields.interview_date.value,
      };
      assert.equal(await notice.inputValue(), sample);
      await page
        .getByRole("heading", { name: t.p5.review, exact: true })
        .scrollIntoViewIfNeeded();
    },
  );
  await scene(
    "Check details and build your study plan",
    "Check every extracted field and correct mistakes. Choose your career goal and daily study hours. Tick the confirmation box after checking the notice, then build the plan. The schedule uses your saved skills and interview date. The warning here shows there is more to learn than your available time allows. Start with the first skills in the plan.",
    async () => {
      await page.getByLabel(t.p5.hours, { exact: true }).fill("2");
      await page.getByLabel(t.p5.confirm, { exact: true }).check();
      const data = await click("/prep/pack", t.p5.build);
      assert(data.plan.days.length > 0);
      assert(data.plan.required_hours > 0);
      proof.plan = {
        days: data.plan.days.length,
        required_hours: data.plan.required_hours,
        capacity_hours: data.plan.capacity_hours,
        feasible: data.plan.feasible,
      };
      await page
        .getByRole("heading", { name: t.p5.schedule, exact: true })
        .scrollIntoViewIfNeeded();
    },
  );
  await scene(
    "Practise an interview answer",
    "Open Start interview practice from your plan. Your company and job title carry over. Start five questions, then type an answer, or record one and check the transcript. I am sending a practice answer. Feedback quotes your own words and suggests improvements. The counts are practice aids, not a hiring score.",
    async () => {
      await page.getByRole("link", { name: t.p5.mock, exact: true }).click();
      await page.waitForFunction(
        () =>
          document.querySelector('input[list="company-job-titles"]')?.value ===
          "Data Analyst",
      );
      assert.equal(
        await page.getByLabel(t.p5.role, { exact: true }).inputValue(),
        "Data Analyst",
      );
      assert.equal(
        await page.getByLabel(t.p5.company, { exact: true }).inputValue(),
        "Example Analytics (practice only)",
      );
      const session = await click("/interview/start", t.p5.start);
      assert.equal(session.questions.length, 5);
      await page
        .getByLabel(t.p5.answer, { exact: true })
        .fill(
          "In my college project, our sales report had duplicate records. My task was to clean the data. I used SQL to find duplicate rows and checked totals with my team. As a result, we delivered an accurate report on time. Next time I would add checks before importing the data.",
        );
      const result = await click("/interview/answer", t.p5.submit);
      assert.equal(result.attempts.length, 1);
      assert(result.attempts[0].feedback.length > 0);
      proof.practice = {
        questions: session.questions.length,
        answers: 1,
        feedback_points: result.attempts[0].feedback.length,
      };
      await page.locator(".practice-attempt").first().scrollIntoViewIfNeeded();
    },
  );
  await scene(
    "Finish and review practice",
    "Continue through the remaining questions. Each answer gets feedback and appears in your attempt history. Practise in your own words; these demonstration answers are only examples. You can delete the session when finished. The interface tells you that attempts expire after twenty-four hours.",
    async () => {
      for (let i = 1; i < 5; i++) {
        await page
          .getByLabel(t.p5.answer, { exact: true })
          .fill(
            "In a college project, I needed to check a report. I compared the records, explained the problem to my team and tested the change. We completed the task on time. I would document the checks more clearly next time.",
          );
        const data = await click("/interview/answer", t.p5.submit);
        assert.equal(data.attempts.length, i + 1);
      }
      proof.practice.answers = 5;
      await page
        .getByRole("heading", { name: t.p5.complete, exact: true })
        .scrollIntoViewIfNeeded();
    },
  );
  await scene(
    "What does public evidence mean?",
    "Sources and checks is the page previously called Evidence in public. It explains where information comes from, what was tested and what still needs improvement. Public means anyone can see these checks. Your placement notice and private answers are not published here. A passing test does not guarantee every live answer is correct. You do not need this page to use the other tools.",
    async () => {
      await click("/interview/delete", t.p5.delete);
      const pending = page.waitForResponse((r) =>
        r.url().includes("/engine/evidence"),
      );
      await go("/evidence");
      const response = await pending;
      assert(response.ok());
      proof.evidence = { status: response.status() };
      await page.getByText(t.help.evidence3, { exact: true }).waitFor();
    },
  );
  assert.deepEqual(errors, []);
  proof.chapters = chapters.length;
  proof.browser_errors = errors;
  const video = record ? page.video() : null;
  await context.close();
  await browser.close();
  writeFileSync(join(proofDir, "proof.json"), JSON.stringify(proof, null, 2));
  if (record) {
    const args = ["-y", "-i", await video.path()];
    for (const c of chapters) args.push("-i", c.voice);
    const filters = chapters.map(
      (c, i) => `[${i + 1}:a]adelay=${Math.round(c.start * 1000)}:all=1[a${i}]`,
    );
    filters.push(
      `${chapters.map((_, i) => `[a${i}]`).join("")}amix=inputs=${chapters.length}:normalize=0[a]`,
    );
    const output = join(docs, "DAARI-user-demo.mp4");
    execFileSync(
      "/opt/homebrew/bin/ffmpeg",
      [
        ...args,
        "-filter_complex",
        filters.join(";"),
        "-map",
        "0:v",
        "-map",
        "[a]",
        "-c:v",
        "libx264",
        "-preset",
        "fast",
        "-crf",
        "25",
        "-pix_fmt",
        "yuv420p",
        "-c:a",
        "aac",
        "-b:a",
        "96k",
        "-movflags",
        "+faststart",
        output,
      ],
      { stdio: "ignore" },
    );
    writeFileSync(
      join(docs, "DAARI-user-demo.md"),
      `# DAARI: how to use it\n\nRecorded against ${origin} on ${proof.checked_at}. Actual browser actions and API results; no mocked responses. The placement notice and answers are practice examples.\n\n${chapters.map((c) => `## ${Math.floor(c.start / 60)}:${String(Math.floor(c.start % 60)).padStart(2, "0")} — ${c.title}\n\n${c.narration}`).join("\n\n")}\n\n## Observed results\n\n\`\`\`json\n${JSON.stringify(proof, null, 2)}\n\`\`\`\n`,
    );
    console.log(JSON.stringify({ output, duration: duration(output), proof }));
  } else console.log(JSON.stringify(proof));
} finally {
  await browser.close();
}
