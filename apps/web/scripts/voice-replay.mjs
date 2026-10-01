// Cached voice gate including a real WebSocket and Chrome audio playback start.
// Run after warming clips with the API's check_voice_replay.py.
import { readFileSync } from "node:fs";
import { resolve } from "node:path";
import { chromium } from "@playwright/test";

const root = resolve(process.argv[2] ?? "../../.cache/voice/rehearsal");
const count = Number(process.argv[3] ?? 20);
if (!Number.isInteger(count) || count < 1)
  throw Error("Positive sample count required");
const browser = await chromium.launch({
  ...(process.env.CHROME_EXECUTABLE
    ? { executablePath: process.env.CHROME_EXECUTABLE }
    : {}),
  args: ["--autoplay-policy=no-user-gesture-required"],
});
let passed = true;
try {
  const page = await browser.newPage();
  await page.goto(process.env.WEB_URL ?? "http://127.0.0.1:3100/en/voice");
  for (const locale of ["en", "te", "hi"]) {
    const audio = readFileSync(resolve(root, `${locale}.mp3`)).toString(
      "base64",
    );
    const rows = await page.evaluate(
      async ({ audio, locale, count, endpoint }) => {
        const rows = [];
        for (let index = 0; index < count; index++) {
          const row = await new Promise((resolveTurn, reject) => {
            const ws = new WebSocket(endpoint);
            let start = 0;
            let first = null;
            let done = null;
            let valid = false;
            const players = [];
            const timeout = setTimeout(
              () => finish(new Error("Cached turn exceeded 5 s")),
              5000,
            );
            function finish(error) {
              if (!error && (first === null || done === null)) return;
              clearTimeout(timeout);
              ws.close();
              for (const player of players) player.pause();
              if (error || !valid)
                reject(error ?? new Error("Missing successful tool result"));
              else resolveTurn({ first, done });
            }
            ws.onerror = () => finish(new Error("WebSocket failed"));
            ws.onopen = () => {
              start = performance.now();
              ws.send(JSON.stringify({ type: "release_start" }));
              ws.send(
                JSON.stringify({
                  type: "release",
                  audio,
                  mime: "audio/mpeg",
                  request: { text: "voice input", locale },
                }),
              );
            };
            ws.onmessage = ({ data }) => {
              const event = JSON.parse(data);
              if (event.type === "error" || event.type === "browser_tts") {
                finish(new Error(`Unexpected ${event.type}`));
              } else if (event.type === "result") {
                const result = event.result;
                valid = Boolean(
                  (result.cards.length || result.engine_result) &&
                    result.trace.length &&
                    result.trace.every((row) => row.status === "ok"),
                );
              } else if (event.type === "audio") {
                const player = new Audio(
                  `data:audio/mpeg;base64,${event.data}`,
                );
                players.push(player);
                player.onplaying = () => {
                  first ??= performance.now() - start;
                  finish();
                };
                player.play().catch(finish);
              } else if (event.type === "done") {
                done = performance.now() - start;
                finish();
              }
            };
          });
          rows.push(row);
        }
        return rows;
      },
      {
        audio,
        locale,
        count,
        endpoint: process.env.VOICE_WS ?? "ws://127.0.0.1:8100/ws/voice",
      },
    );
    const percentile = (key) =>
      rows.map((row) => row[key]).sort((a, b) => a - b)[
        Math.ceil(count * 0.95) - 1
      ];
    const first = percentile("first");
    const done = percentile("done");
    const ok = first < 1500 && done < 4000;
    passed &&= ok;
    console.log(
      JSON.stringify({
        locale,
        n: count,
        first_playback_p95_ms: Math.round(first),
        response_done_p95_ms: Math.round(done),
        passed: ok,
      }),
    );
  }
} finally {
  await browser.close();
}
if (!passed) process.exitCode = 1;
