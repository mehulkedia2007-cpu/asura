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
    <nav aria-label={t("languageLabel")} className="flex items-center gap-3">
      {routing.locales.map((loc, i) => (
        <span key={loc} className="flex items-center gap-3">
          {i > 0 && (
            <span aria-hidden="true" className="h-3 w-px bg-graphite/40" />
          )}
          <Link
            href={pathname}
            locale={loc}
            aria-current={loc === locale ? "true" : undefined}
            className={`font-mono text-sm tracking-wide transition-colors ${
              loc === locale ? "text-ink" : "text-graphite hover:text-ink"
            }`}
          >
            {codes[loc]}
          </Link>
        </span>
      ))}
    </nav>
  );
}
