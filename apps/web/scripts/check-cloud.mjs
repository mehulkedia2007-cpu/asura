// Real deployment readiness + WebSocket turns. Synthetic text, no microphone.
import assert from "node:assert/strict";
import { mkdirSync, writeFileSync } from "node:fs";
import { chromium } from "@playwright/test";

const origin = process.env.WEB_URL ?? "http://127.0.0.1:3015";
const output = process.env.CLOUD_REPORT_DIR ?? "../../.cache/cloud";
mkdirSync(output, { recursive: true });
const browser = await chromium.launch();
const page = await browser.newPage();
const errors = [];
page.on("pageerror", (error) => errors.push(error.message));
const report = {
  origin,
  checkedAt: new Date().toISOString(),
  voice: [],
  errors,
};
try {
  const ready = await page.request.get(`${origin}/api/engine/ready`);
  assert.equal(ready.status(), 200);
  report.ready = await ready.json();
  assert.equal(report.ready.ok, true);
  const connection = await page.request.get(`${origin}/api/connection`);
  assert.equal(connection.status(), 200);
  const endpoint = (await connection.json()).websocketUrl;
  assert.match(endpoint, /^wss?:\/\//);
  report.websocketUrl = endpoint;
  await page.goto(`${origin}/en/voice`);
  for (const [locale, text] of [
    ["en", "Show my roadmap to become a data analyst"],
    ["te", "డేటా అనలిస్ట్ కోసం నా అభ్యాస ప్రణాళిక చూపించు"],
    ["hi", "डेटा एनालिस्ट बनने के लिए मेरा रोडमैप दिखाओ"],
  ]) {
    const turn = await page.evaluate(
      ({ endpoint, locale, text }) =>
        new Promise((resolve, reject) => {
          const socket = new WebSocket(endpoint);
          const start = performance.now();
          const events = [];
          let result;
          let audio = 0;
          let browserTts = 0;
          const timeout = setTimeout(
            () => finish(new Error("Cloud voice turn timed out")),
            120000,
          );
          function finish(error) {
            clearTimeout(timeout);
            socket.close();
            if (error) reject(error);
          }
          socket.onerror = () =>
            finish(new Error("WebSocket connection failed"));
          socket.onopen = () =>
            socket.send(
              JSON.stringify({ type: "interim", text: "connection check" }),
            );
          socket.onmessage = (event) => {
            const message = JSON.parse(event.data);
            events.push(message.type);
            if (message.type === "interim") {
              socket.send(
                JSON.stringify({
                  type: "release",
                  request: {
                    text,
                    locale,
                    persona: "student",
                    held: {},
                    goal: "data_analyst",
                  },
                  audio: "",
                  mime: "audio/webm",
                  browser_final: text,
                }),
              );
            }
            if (message.type === "error")
              finish(new Error(`Voice error: ${message.detail}`));
            if (message.type === "audio") audio++;
            if (message.type === "browser_tts") browserTts++;
            if (message.type === "result") result = message.result;
            if (message.type === "done") {
              finish();
              resolve({
                locale,
                events,
                provider: result?.provider,
                engine: result?.engine_result?.kind,
                trace: result?.trace?.map(({ tool, status }) => ({
                  tool,
                  status,
                })),
                audio,
                browserTts,
                elapsedMs: Math.round(performance.now() - start),
                stamps: message.stamps_ms,
              });
            }
          };
        }),
      { endpoint, locale, text },
    );
    report.voice.push(turn);
    assert.equal(turn.engine, "get_roadmap");
    assert(
      turn.events.includes("transcript") && turn.events.includes("result"),
    );
    assert(turn.audio + turn.browserTts > 0);
    assert(
      turn.trace.some(
        (entry) => entry.tool === "get_roadmap" && entry.status === "ok",
      ),
    );
    console.log(
      `${locale}: real WebSocket, ${turn.engine}, ${turn.provider}, ${turn.elapsedMs} ms`,
    );
  }
  assert.deepEqual(errors, []);
  report.passed = true;
} finally {
  writeFileSync(`${output}/connection.json`, JSON.stringify(report, null, 2));
  await browser.close();
}
