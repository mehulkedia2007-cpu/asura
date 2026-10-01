import assert from "node:assert/strict";
import { mkdirSync, readFileSync, writeFileSync } from "node:fs";
import { chromium } from "@playwright/test";

const origin = process.env.WEB_URL ?? "http://127.0.0.1:3015";
const output = "../../.cache/redesign";
mkdirSync(output, { recursive: true });
const browser = await chromium.launch();
const page = await browser.newPage({ viewport: { width: 390, height: 844 } });
const errors = [];
page.on("pageerror", (error) => errors.push(error.message));
const t = JSON.parse(readFileSync("messages/en.json", "utf8"));
const report = {};
try {
  await page.addInitScript(() =>
    localStorage.setItem("daari-held", JSON.stringify({ sql_querying: 4 })),
  );
  await page.goto(`${origin}/en/leads`);
  await page.getByLabel(t.live.query, { exact: true }).fill("python");
  const leadsResponse = page.waitForResponse(
    (response) =>
      response.url().endsWith("/leads/search") &&
      response.request().method() === "POST",
    { timeout: 70000 },
  );
  await page.getByRole("button", { name: t.live.search, exact: true }).click();
  const leads = await (await leadsResponse).json();
  await page.locator(".result-card").first().waitFor();
  assert(
    leads.leads.length > 0,
    "Live sources must produce stamped cards in this verification",
  );
  assert.equal(
    await page.locator(".source-footer").count(),
    leads.leads.length,
  );
  assert(
    leads.leads.every(
      (lead) =>
        lead.source_url.startsWith("https://") &&
        lead.fetched_at &&
        lead.match &&
        lead.scam,
    ),
  );
  await page.locator(".match-panel summary").first().click();
  assert(
    (await page.locator(".match-panel dl").first().innerText()).length > 0,
  );
  await page.screenshot({ path: `${output}/leads-mobile.png`, fullPage: true });
  report.leads = {
    returned: leads.leads.length,
    sourceStamps: true,
    matchBreakdown: true,
    sourceErrors: leads.errors,
    radius: leads.radius_km,
  };
  await page.goto(`${origin}/en/schemes`);
  await page.getByLabel(t.live.query, { exact: true }).fill("skill training");
  const schemesResponse = page.waitForResponse(
    (response) =>
      response.url().endsWith("/schemes/search") &&
      response.request().method() === "POST",
    { timeout: 70000 },
  );
  await page.getByRole("button", { name: t.live.search, exact: true }).click();
  const schemes = await (await schemesResponse).json();
  await page.locator(".result-card").first().waitFor();
  assert(schemes.schemes.length > 0);
  assert(
    schemes.schemes.every(
      (scheme) =>
        ["true", "unknown"].includes(scheme.eligibility.status) &&
        scheme.url &&
        scheme.fetched_at,
    ),
  );
  assert.equal(
    await page.locator(".eligibility-badge.unknown").count(),
    schemes.schemes.filter((scheme) => scheme.eligibility.status === "unknown")
      .length,
  );
  assert.equal(
    await page.locator(".source-footer").count(),
    schemes.schemes.length,
  );
  let eligibilityRecheck = false;
  if (schemes.next_question) {
    const target = schemes.schemes.find(
      (scheme) => scheme.id === schemes.next_question.scheme_id,
    );
    assert.equal(target.rules_complete, true);
    const rule = [...target.rules.all, ...target.rules.any].find(
      (item) => item.field === schemes.next_question.field,
    );
    assert(rule, "A follow-up question must have a source-backed predicate");
    const answer =
      rule.op === "in"
        ? rule.value[0]
        : rule.op === "ne"
          ? "synthetic alternative"
          : rule.value;
    await page.locator("#scheme-slot").fill(String(answer));
    const recheckResponse = page.waitForResponse(
      (response) =>
        response.url().endsWith("/schemes/search") &&
        response.request().method() === "POST",
      { timeout: 70000 },
    );
    await page
      .getByRole("button", { name: t.live.checkAgain, exact: true })
      .click();
    const rechecked = await (await recheckResponse).json();
    assert(
      rechecked.schemes.some(
        (scheme) =>
          scheme.id === schemes.next_question.scheme_id &&
          scheme.eligibility.status === "true",
      ),
    );
    eligibilityRecheck = true;
  } else {
    // Incomplete source evidence cannot be repaired with a personal fact.
    // A live catalog need not contain a complete single-slot predicate.
    assert(
      schemes.schemes.every(
        (scheme) =>
          !scheme.rules_complete ||
          scheme.eligibility.missing_fields.length !== 1,
      ),
    );
    assert.equal(await page.locator("#scheme-slot").count(), 0);
  }
  await page.screenshot({
    path: `${output}/schemes-mobile.png`,
    fullPage: true,
  });
  report.schemes = {
    returned: schemes.schemes.length,
    eligibilityUnknown: true,
    eligibilityRecheck,
    followUpQuestion: schemes.next_question?.field ?? null,
    indexed: schemes.coverage.indexed,
    stale: schemes.stale,
    sourceErrors: schemes.source_errors,
  };
  await page.goto(`${origin}/en/path`);
  await page.locator(".skill-map").waitFor();
  await page.getByRole("button", { name: t.path.assess, exact: true }).click();
  await page.getByTestId("assessment-question-text").waitFor();
  let answered = 0;
  while (await page.getByTestId("assessment-question-text").isVisible()) {
    assert(answered < 6, "CAT must terminate within six questions");
    await page
      .getByLabel(t.path.answer, { exact: true })
      .fill("SELECT * FROM reports;");
    const answerResponse = page.waitForResponse((response) =>
      response.url().endsWith("/assess/answer"),
    );
    await page
      .getByRole("button", { name: t.path.submit, exact: true })
      .click();
    const answer = await (await answerResponse).json();
    answered++;
    if (answer.done) {
      await page
        .getByRole("heading", { name: t.path.after, exact: true })
        .waitFor();
      break;
    }
    await page.waitForFunction(
      (count) =>
        document
          .querySelector(".assessment-progress")
          ?.querySelectorAll(".complete").length === count,
      answered,
    );
  }
  assert(answered > 0 && answered <= 6);
  assert(
    Number(
      JSON.parse(await page.evaluate(() => localStorage.getItem("daari-held")))
        .sql_querying,
    ) >= 1,
  );
  report.assessment = {
    answered,
    persistedProfile: true,
    recalculatedRoadmap: true,
  };
  assert.equal(errors.length, 0, errors.join("\n"));
  writeFileSync(
    `${output}/live-journeys.json`,
    JSON.stringify({ report, errors }, null, 2),
  );
  console.log(JSON.stringify(report, null, 2));
} finally {
  await browser.close();
}
