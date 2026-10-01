import { expect, test } from "@playwright/test";
import { GET } from "../../app/api/connection/route";

test("voice resolves the private cloud API address at request time", async () => {
  const previous = process.env.DAARI_API_URL;
  try {
    process.env.DAARI_API_URL = "https://api.example/";
    const response = GET();
    expect(response.status).toBe(200);
    expect(await response.json()).toEqual({
      websocketUrl: "wss://api.example/ws/voice",
    });
    process.env.DAARI_API_URL = "https://other.example";
    expect((await GET().json()).websocketUrl).toBe(
      "wss://other.example/ws/voice",
    );
  } finally {
    if (previous === undefined) delete process.env.DAARI_API_URL;
    else process.env.DAARI_API_URL = previous;
  }
});

test("voice does not publish credentials or a localhost URL on Vercel", async () => {
  const previous = {
    api: process.env.DAARI_API_URL,
    vercel: process.env.VERCEL,
  };
  try {
    process.env.VERCEL = "1";
    delete process.env.DAARI_API_URL;
    expect(GET().status).toBe(503);
    process.env.DAARI_API_URL = "https://user:secret@api.example";
    const response = GET();
    expect(response.status).toBe(503);
    expect(await response.text()).not.toContain("secret");
  } finally {
    if (previous.api === undefined) delete process.env.DAARI_API_URL;
    else process.env.DAARI_API_URL = previous.api;
    if (previous.vercel === undefined) delete process.env.VERCEL;
    else process.env.VERCEL = previous.vercel;
  }
});
