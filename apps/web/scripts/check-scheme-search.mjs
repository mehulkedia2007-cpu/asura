import assert from "node:assert/strict";
import { mkdirSync, readFileSync, writeFileSync } from "node:fs";
import { chromium } from "@playwright/test";

const schemeName =
  process.env.SCHEME_NAME ??
  "National Fellowship for Students with Disabilities";
const origin = process.env.WEB_URL ?? "http://127.0.0.1:3020";
const output = "../../.cache/scheme-search";
mkdirSync(output, { recursive: true });
const t = JSON.parse(readFileSync("messages/en.json", "utf8")).live;
const browser = await chromium.launch();
const page = await browser.newPage({ viewport: { width: 1280, height: 800 } });
const errors = [];
const report = { origin, checked_at: new Date().toISOString(), searches: [] };
page.on("pageerror", (error) => errors.push(error.message));
try {
  await page.addInitScript(() =>
    localStorage.setItem("daari-seen-schemes", "broken JSON"),
  );
  const optionsResponse = page.waitForResponse((r) =>
    r.url().endsWith("/schemes/options"),
  );
  await page.goto(`${origin}/en/schemes`);
  const options = await (await optionsResponse).json();
  const selected = options.schemes.find(
    (r) => r.name_en.toLowerCase() === schemeName.toLowerCase(),
  );
  assert(
    selected,
    `The selected real scheme must exist in the source index: ${schemeName}`,
  );
  async function search(query, refresh = false) {
    if (query !== null)
      await page.getByLabel(t.query, { exact: true }).fill(query);
    const pending = page.waitForResponse(
      (r) =>
        r.url().endsWith("/schemes/search") && r.request().method() === "POST",
    );
    const start = performance.now();
    await page
      .getByRole("button", {
        name: refresh ? t.refresh : t.search,
        exact: true,
      })
      .click();
    const response = await pending;
    const data = await response.json();
    assert(response.ok(), `HTTP ${response.status()}`);
    await page.waitForFunction(
      () => !document.querySelector('button[type="submit"]')?.disabled,
    );
    const elapsed = Math.round(performance.now() - start);
    assert(elapsed < (refresh ? 12000 : 6000), `Unbounded wait: ${elapsed} ms`);
    report.searches.push({
      query: query ?? selected.name_en,
      refresh,
      elapsed_ms: elapsed,
      count: data.schemes.length,
      source_errors: data.source_errors,
    });
    assert.equal(
      await page.locator("main").getByRole("alert").count(),
      0,
      await page.locator("main").innerText(),
    );
    return data;
  }
  await page
    .getByLabel(t.chooseScheme, { exact: true })
    .selectOption(`scheme:${selected.id}`);
  await page.getByLabel(t.age, { exact: true }).fill("19");
  await page.getByLabel(t.income, { exact: true }).fill("0");
  const named = await search(null);
  assert.equal(named.schemes.length, 1);
  assert.equal(named.schemes[0].id, selected.id);
  await page.locator(".result-card").first().waitFor();
  await page.screenshot({
    path: `${output}/selected-scheme.png`,
    fullPage: true,
  });
  const refresh = await search(null, true);
  assert.equal(
    refresh.schemes.length,
    1,
    "Source failure must preserve the chosen scheme",
  );
  assert.equal(refresh.schemes[0].id, selected.id);
  const typed = await search(selected.name_en);
  assert.equal(
    typed.schemes.length,
    1,
    "An exact official title should not pad with related schemes",
  );
  const missing = await search("zzunmatchedschemeneed");
  assert.equal(missing.schemes.length, 0);
  assert.deepEqual(missing.source_errors, []);
  assert.equal(missing.refresh_status, "not_requested");
  await page.getByText(t.noSchemesHelp, { exact: true }).waitFor();
  await page.screenshot({
    path: `${output}/fast-no-match.png`,
    fullPage: true,
  });
  await search("education scholarship");
  assert.deepEqual(errors, []);
  report.browser_errors = errors;
  writeFileSync(`${output}/report.json`, JSON.stringify(report, null, 2));
  console.log(JSON.stringify(report));
} finally {
  await browser.close();
}
