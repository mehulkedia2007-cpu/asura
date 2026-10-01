import { getTranslations } from "next-intl/server";
import { EvidenceBoard } from "@/components/EvidenceBoard";

export default async function EvidencePage() {
  const t = await getTranslations("p6");
  return (
    <main className="mx-auto w-full max-w-[1440px] flex-1 px-6 py-12 sm:px-10 sm:py-16 lg:px-16">
      <div className="max-w-4xl">
        <p className="font-mono text-graphite text-xs uppercase tracking-[0.2em]">
          {t("eyebrow")}
        </p>
        <h1 className="mt-5 max-w-3xl font-display text-5xl text-ink leading-[0.95] sm:text-7xl">
          {t("title")}
        </h1>
        <p className="mt-6 max-w-2xl font-ui text-graphite text-base leading-7">
          {t("intro")}
        </p>
      </div>
      <div className="mt-12">
        <EvidenceBoard />
      </div>
    </main>
  );
}
