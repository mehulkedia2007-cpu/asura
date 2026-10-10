"use client";

import { useTranslations } from "next-intl";

export function HowTo({
  section,
}: {
  section: "path" | "questions" | "prep" | "interview" | "evidence";
}) {
  const t = useTranslations("help");
  return (
    <aside className="surface mb-6 space-y-3" aria-label={t("title")}>
      <h2 className="text-lg font-semibold">{t("title")}</h2>
      <p>{t(`${section}Intro`)}</p>
      <ol className="list-decimal space-y-2 pl-5 text-sm text-graphite">
        {[1, 2, 3].map((step) => (
          <li key={step}>{t(`${section}${step}`)}</li>
        ))}
      </ol>
    </aside>
  );
}
