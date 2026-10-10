import assert from "node:assert/strict";
import { mkdirSync, readFileSync, writeFileSync } from "node:fs";
import { chromium } from "@playwright/test";

const origin = process.env.WEB_URL ?? "http://127.0.0.1:3017";
const browser = await chromium.launch();
const report = { origin, locales: [], realGovernment: null };
const output = "../../.cache/ap-search";
mkdirSync(output, { recursive: true });
try {
  for (const locale of ["en", "te", "hi"]) {
    const t = JSON.parse(readFileSync(`messages/${locale}.json`, "utf8")).live;
    const page = await browser.newPage();
    const errors = [];
    page.on("pageerror", (error) => errors.push(error.message));
    const bodies = [];
    await page.route("**/api/engine/leads/search", async (route) => {
      const body = route.request().postDataJSON();
      bodies.push(body);
      if (body.query === "slow")
        await new Promise((resolve) => setTimeout(resolve, 500));
      await route
        .fulfill({
          json: {
            leads: [],
            region: "Andhra Pradesh",
            include_remote: body.include_remote,
            job_type: body.job_type,
            radius_km: body.job_type === "government" ? null : 100,
            errors: {},
          },
        })
        .catch(() => {});
    });
    await page.goto(`${origin}/${locale}/leads`);
    const remote = page.getByLabel(t.includeRemote, { exact: true });
    assert.equal(await remote.isChecked(), false);
    await page.getByLabel(t.query, { exact: true }).fill("python");
    await page.getByRole("button", { name: t.search, exact: true }).click();
    await page.getByText(t.noData, { exact: true }).waitFor();
    assert.equal(bodies.at(-1).include_remote, false);
    await page.getByLabel(t.query, { exact: true }).fill("slow");
    assert.equal(await page.getByText(t.noData, { exact: true }).count(), 0);
    await page.getByRole("button", { name: t.search, exact: true }).click();
    await page.getByLabel(t.query, { exact: true }).fill("new query");
    await page.waitForTimeout(700);
    assert.equal(
      await page.getByText(t.noData, { exact: true }).count(),
      0,
      "Aborted old query must not restore results",
    );
    await remote.check();
    await page.getByRole("button", { name: t.search, exact: true }).click();
    await page.getByText(t.noData, { exact: true }).waitFor();
    assert.equal(bodies.at(-1).include_remote, true);
    await page
      .getByLabel(t.jobType, { exact: true })
      .selectOption("government");
    await page.getByLabel(t.query, { exact: true }).fill("");
    assert.equal(await remote.count(), 0);
    await page.getByRole("button", { name: t.search, exact: true }).click();
    await page.getByText(t.noData, { exact: true }).waitFor();
    assert.equal(bodies.at(-1).job_type, "government");
    assert.equal(bodies.at(-1).query, "recruitment");
    assert.equal(bodies.at(-1).include_remote, false);
    assert.deepEqual(errors, []);
    report.locales.push({
      locale,
      remoteOptIn: true,
      staleQueryCleared: true,
      cancelledResponseIgnored: true,
      governmentBrowse: true,
    });
    await page.close();
  }
  const page = await browser.newPage();
  const t = JSON.parse(readFileSync("messages/en.json", "utf8")).live;
  await page.goto(`${origin}/en/leads`);
  await page.getByLabel(t.jobType, { exact: true }).selectOption("government");
  const response = page.waitForResponse(
    (r) => r.url().endsWith("/leads/search") && r.request().method() === "POST",
    { timeout: 90000 },
  );
  await page.getByRole("button", { name: t.search, exact: true }).click();
  const res = await response;
  assert.equal(res.status(), 200);
  const data = await res.json();
  assert.equal(data.job_type, "government");
  assert(
    data.leads.every(
      (lead) =>
        lead.government &&
        lead.source_url.startsWith("https://") &&
        lead.distance_km === null &&
        lead.application_status === "verify_on_source",
    ),
  );
  if (data.leads.length) await page.locator(".result-card").first().waitFor();
  else await page.getByText(t.noData, { exact: true }).waitFor();
  report.realGovernment = {
    count: data.leads.length,
    sourceErrors: data.errors,
    officialSourceLinks: true,
    noInventedDistance: true,
  };
  await page.screenshot({ path: `${output}/government.png`, fullPage: true });
  writeFileSync(`${output}/report.json`, JSON.stringify(report, null, 2));
  console.log(JSON.stringify(report, null, 2));
} finally {
  await browser.close();
}
