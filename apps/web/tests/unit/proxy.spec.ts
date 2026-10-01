import { expect, test } from "@playwright/test";
import { NextRequest } from "next/server";
import { GET } from "../../app/api/engine/[...path]/route";

test("readiness forwards to the cloud health path and preserves failure status", async () => {
  const previous = { api: process.env.DAARI_API_URL, fetch: globalThis.fetch };
  try {
    process.env.DAARI_API_URL = "https://api.example/";
    let forwarded = "";
    globalThis.fetch = async (input) => {
      forwarded = input.toString();
      return Response.json({ ok: false }, { status: 503 });
    };
    const response = await GET(
      new NextRequest("https://web.example/api/engine/ready?check=2"),
      {
        params: Promise.resolve({ path: ["ready"] }),
      },
    );
    expect(forwarded).toBe("https://api.example/ready?check=2");
    expect(response.status).toBe(503);
    expect(await response.json()).toEqual({ ok: false });
  } finally {
    globalThis.fetch = previous.fetch;
    if (previous.api === undefined) delete process.env.DAARI_API_URL;
    else process.env.DAARI_API_URL = previous.api;
  }
});

test("missing production backend fails without attempting localhost", async () => {
  const previous = {
    api: process.env.DAARI_API_URL,
    vercel: process.env.VERCEL,
    fetch: globalThis.fetch,
  };
  try {
    delete process.env.DAARI_API_URL;
    process.env.VERCEL = "1";
    let called = false;
    globalThis.fetch = async () => {
      called = true;
      throw new Error("Unexpected fetch");
    };
    const response = await GET(
      new NextRequest("https://web.example/api/engine/catalog"),
      {
        params: Promise.resolve({ path: ["catalog"] }),
      },
    );
    expect(response.status).toBe(503);
    expect(called).toBe(false);
  } finally {
    globalThis.fetch = previous.fetch;
    if (previous.api === undefined) delete process.env.DAARI_API_URL;
    else process.env.DAARI_API_URL = previous.api;
    if (previous.vercel === undefined) delete process.env.VERCEL;
    else process.env.VERCEL = previous.vercel;
  }
});
