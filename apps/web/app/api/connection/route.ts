// Resolve at request time so changing the private API URL also repairs voice.
export function GET() {
  try {
    const base =
      process.env.DAARI_API_URL ||
      (process.env.VERCEL ? undefined : "http://127.0.0.1:8000");
    if (!base) throw new Error("Backend not configured");
    const url = new URL(base);
    if (
      !["http:", "https:"].includes(url.protocol) ||
      url.username ||
      url.password
    )
      throw new Error("Invalid backend URL");
    url.protocol = url.protocol === "https:" ? "wss:" : "ws:";
    url.pathname = `${url.pathname.replace(/\/$/, "")}/ws/voice`;
    url.search = "";
    url.hash = "";
    return Response.json(
      { websocketUrl: url.toString() },
      {
        headers: { "Cache-Control": "no-store" },
      },
    );
  } catch {
    return Response.json({ detail: "Engine unavailable" }, { status: 503 });
  }
}
