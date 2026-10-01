import assert from "node:assert/strict";
import { mkdirSync, readFileSync, writeFileSync } from "node:fs";
import { chromium } from "@playwright/test";

const origin = process.env.WEB_URL ?? "http://127.0.0.1:3000";
const output = "../../.cache/web-audit";
mkdirSync(output, { recursive: true });
const browser = await chromium.launch({
  ...(process.env.CHROME_EXECUTABLE
    ? { executablePath: process.env.CHROME_EXECUTABLE }
    : {}),
});
const findings = [];
try {
  for (const locale of ["en", "te", "hi"]) {
    const t = JSON.parse(readFileSync(`messages/${locale}.json`, "utf8")).path;
    const page = await browser.newPage({
      viewport: { width: 390, height: 844 },
    });
    const errors = [];
    page.on("pageerror", (error) => errors.push(error.message));
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
      const response = await page.goto(`${origin}/${locale}/${route}`);
      await page.locator("h1").waitFor();
      if (["path", "questions", "prep", "interview"].includes(route)) {
        await page.waitForFunction(() =>
          Array.from(document.querySelectorAll("select")).every(
            (s) => s.options.length > 0,
          ),
        );
      }
      if (route === "path") {
        await page
          .getByRole("button", { name: t.simulate, exact: true })
          .waitFor();
        await page.waitForFunction(
          () => document.querySelectorAll("main ol li").length > 0,
        );
        assert.equal(
          await page.evaluate(() => localStorage.getItem("daari-held")),
          null,
        );
        await page
          .getByRole("button", { name: t.simulate, exact: true })
          .click();
        await page
          .getByRole("heading", { name: t.after, exact: true })
          .waitFor();
        await page.waitForFunction(
          () =>
            JSON.parse(localStorage.getItem("daari-held") ?? "{}")
              .sql_querying === 4,
        );
        await page.locator("main select").nth(2).selectOption("spoken_english");
        const beforeCard = page.locator("main section").filter({
          has: page.getByRole("heading", { name: t.before, exact: true }),
        });
        const afterCard = page.locator("main section").filter({
          has: page.getByRole("heading", { name: t.after, exact: true }),
        });
        const orderBeforeShock = await beforeCard
          .locator("ol li")
          .allTextContents();
        await page.getByRole("button", { name: t.shock, exact: true }).click();
        await page.waitForFunction(
          () =>
            JSON.parse(localStorage.getItem("daari-demand") ?? "{}")
              .spoken_english > 1,
        );
        await page.waitForFunction(
          ({ oldOrder, heading }) => {
            const section = Array.from(
              document.querySelectorAll("main section"),
            ).find(
              (candidate) =>
                candidate.querySelector("h2")?.textContent?.trim() === heading,
            );
            const current = Array.from(
              section?.querySelectorAll("ol li") ?? [],
            ).map((item) => item.textContent);
            return JSON.stringify(current) !== JSON.stringify(oldOrder);
          },
          { oldOrder: orderBeforeShock, heading: t.after },
        );
        const orderAfterShock = await afterCard
          .locator("ol li")
          .allTextContents();
        assert.notDeepEqual(
          orderAfterShock,
          orderBeforeShock,
          `${locale}/path market shock did not move the path`,
        );
        await page.locator("main select").nth(2).selectOption("sql_querying");
        await page.getByRole("button", { name: t.assess, exact: true }).click();
        await page
          .getByRole("textbox", { name: t.answer, exact: true })
          .waitFor();
        const question = await page
          .getByTestId("assessment-question-text")
          .textContent();
        assert(question, `${locale}/path assessment question was empty`);
        assert(
          locale === "te"
            ? /[\u0c00-\u0c7f]/u.test(question)
            : locale === "hi"
              ? /[\u0900-\u097f]/u.test(question)
              : true,
          `${locale}/path assessment question was not localized`,
        );
      }
      await page.waitForTimeout(350);
      const row = {
        locale,
        route,
        status: response.status(),
        overflow: await page.evaluate(
          () => document.documentElement.scrollWidth > innerWidth,
        ),
        errors: [...errors],
      };
      findings.push(row);
      await page.screenshot({
        path: `${output}/${locale}-${route || "home"}.png`,
        fullPage: true,
      });
      await page.setViewportSize({ width: 1440, height: 1000 });
      await page.emulateMedia({ colorScheme: "dark" });
      assert(
        !(await page.evaluate(
          () => document.documentElement.scrollWidth > innerWidth,
        )),
        `${locale}/${route} desktop overflow`,
      );
      await page.screenshot({
        path: `${output}/${locale}-${route || "home"}-desktop-dark.png`,
        fullPage: true,
      });
      await page.setViewportSize({ width: 390, height: 844 });
      await page.emulateMedia({ colorScheme: "light" });
    }
    await page.close();
  }
  writeFileSync(`${output}/report.json`, JSON.stringify(findings, null, 2));
  console.log(JSON.stringify(findings, null, 2));
  assert(
    findings.every(
      (row) => row.status === 200 && !row.overflow && !row.errors.length,
    ),
    "Browser audit found failures",
  );
} finally {
  await browser.close();
}
