"use client";

import { useLocale, useTranslations } from "next-intl";
import { Link, usePathname } from "@/i18n/navigation";
import { routing } from "@/i18n/routing";

export function LanguageToggle() {
  const locale = useLocale();
  const t = useTranslations("nav");
  const pathname = usePathname();
  const codes: Record<(typeof routing.locales)[number], string> = {
    en: "EN",
    te: "TE",
    hi: "HI",
  };

  return (
    <nav aria-label={t("languageLabel")} className="language-switch">
      {routing.locales.map((loc) => (
        <Link
          href={pathname}
          locale={loc}
          key={loc}
          aria-current={loc === locale ? "true" : undefined}
          hrefLang={loc}
          className={loc === locale ? "selected" : ""}
        >
          {codes[loc]}
        </Link>
      ))}
    </nav>
  );
}
