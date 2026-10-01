import type { Metadata } from "next";
import localFont from "next/font/local";
import { notFound } from "next/navigation";
import { hasLocale, NextIntlClientProvider } from "next-intl";
import { getMessages } from "next-intl/server";
import { LanguageToggle } from "@/components/LanguageToggle";
import { PrepNav } from "@/components/Preparation";
import { VoicePanel } from "@/components/VoicePanel";
import { routing } from "@/i18n/routing";
import "../globals.css";

const geist = localFont({
  src: "../../fonts/geist-latin.woff2",
  variable: "--font-geist",
});
const geistMono = localFont({
  src: "../../fonts/geist-mono-latin.woff2",
  variable: "--font-geist-mono",
});
const instrumentSerif = localFont({
  src: "../../fonts/instrument-serif-italic.woff2",
  variable: "--font-instrument-serif",
  style: "italic",
});
const notoSansTelugu = localFont({
  src: "../../fonts/noto-sans-telugu.woff2",
  variable: "--font-noto-sans-telugu",
});
const notoSerifTelugu = localFont({
  src: "../../fonts/noto-serif-telugu.ttf",
  variable: "--font-noto-serif-telugu",
});
const notoSansDevanagari = localFont({
  src: "../../fonts/noto-sans-devanagari.ttf",
  variable: "--font-noto-sans-devanagari",
});

export const metadata: Metadata = {
  title: "DAARI",
  description: "DAARI — one path engine, two worlds.",
};

export function generateStaticParams() {
  return routing.locales.map((locale) => ({ locale }));
}

export default async function LocaleLayout({
  children,
  params,
}: {
  children: React.ReactNode;
  params: Promise<{ locale: string }>;
}) {
  const { locale } = await params;
  if (!hasLocale(routing.locales, locale)) {
    notFound();
  }

  const messages = await getMessages();

  return (
    <html
      lang={locale}
      className={`${geist.variable} ${geistMono.variable} ${instrumentSerif.variable} ${notoSansTelugu.variable} ${notoSerifTelugu.variable} ${notoSansDevanagari.variable} h-full antialiased`}
    >
      <body className="flex min-h-full flex-col bg-bone text-ink">
        <NextIntlClientProvider messages={messages}>
          <header className="flex items-center justify-between gap-4 border-graphite/20 border-b px-6 py-5">
            <VoicePanel />
            <LanguageToggle />
          </header>
          <PrepNav />
          {children}
        </NextIntlClientProvider>
      </body>
    </html>
  );
}
