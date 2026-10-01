import { getLocale, getTranslations } from "next-intl/server";
import { Link } from "@/i18n/navigation";

export default async function Home() {
  const locale = await getLocale();
  const t = await getTranslations("brand");
  const pathT = await getTranslations("path");
  const liveT = await getTranslations("live");
  const voiceT = await getTranslations("voice");

  const isTelugu = locale === "te";
  const isDevanagari = locale === "hi";

  const wordmarkFont = isTelugu ? "font-telugu-serif" : "font-display";
  const statusFont = isTelugu
    ? "font-telugu-sans"
    : isDevanagari
      ? "font-devanagari-sans"
      : "font-mono";

  return (
    <main className="flex flex-1 flex-col items-start justify-center gap-6 px-6 py-16 sm:px-16">
      <h1
        className={`${wordmarkFont} text-[clamp(3.5rem,12vw,8rem)] leading-none text-ink`}
      >
        {t("wordmark")}
      </h1>
      <div aria-hidden="true" className="h-px w-16 bg-graphite" />
      <p
        className={`${statusFont} flex items-center gap-2 text-graphite text-lg`}
      >
        <span
          aria-hidden="true"
          className="inline-block h-2 w-2 rounded-full bg-sage"
        />
        {t("status")}
      </p>
      <nav className="flex flex-wrap gap-3">
        <Link
          href="/path"
          className="rounded bg-signal px-5 py-3 font-ui text-white"
        >
          {pathT("open")} →
        </Link>
        <Link
          href="/leads"
          className="rounded border border-graphite/40 px-5 py-3 font-ui"
        >
          {liveT("leadsTitle")} →
        </Link>
        <Link
          href="/schemes"
          className="rounded border border-graphite/40 px-5 py-3 font-ui"
        >
          {liveT("schemesTitle")} →
        </Link>
        <Link
          href="/voice"
          className="rounded border border-graphite/40 px-5 py-3 font-ui"
        >
          {voiceT("open")} →
        </Link>
      </nav>
    </main>
  );
}
