import type { NextRequest } from "next/server";

const allowed = new Set([
  "catalog",
  "questions/companies",
  "questions/search",
  "questions/refresh",
  "prep/notice",
  "prep/pack",
  "interview/start",
  "interview/feedback",
  "interview/answer",
  "interview/history",
  "interview/delete",
  "interview/transcribe",

  "roadmap",
  "simulate-skill-update",
  "market-shock",
  "match",
  "profile",
  "assess/next",
  "assess/answer",
  "leads/search",
  "schemes/search",
  "schemes/coverage",
  "schemes/sources",
  "evidence",
]);

async function forward(
  request: NextRequest,
  context: { params: Promise<{ path: string[] }> },
) {
  const { path } = await context.params;
  const endpoint = path.join("/");
  if (!allowed.has(endpoint))
    return Response.json({ detail: "Unknown tool" }, { status: 404 });
  try {
    const upstream = await fetch(
      `${process.env.DAARI_API_URL ?? "http://127.0.0.1:8000"}/engine/${endpoint}${request.method === "GET" ? request.nextUrl.search : ""}`,
      {
        method: request.method,
        headers: { "Content-Type": "application/json" },
        body: request.method === "POST" ? await request.text() : undefined,
        cache: "no-store",
        signal: AbortSignal.timeout(60_000),
      },
    );
    return new Response(await upstream.text(), {
      status: upstream.status,
      headers: { "Content-Type": "application/json" },
    });
  } catch {
    return Response.json({ detail: "Engine unavailable" }, { status: 503 });
  }
}

export const GET = forward;
export const POST = forward;
