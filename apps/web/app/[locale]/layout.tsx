import type { Metadata } from "next";
import localFont from "next/font/local";
import { notFound } from "next/navigation";
import { hasLocale, NextIntlClientProvider } from "next-intl";
import { getMessages } from "next-intl/server";
import { AppShell } from "@/components/AppShell";
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
      data-theme="light"
      className={`${geist.variable} ${geistMono.variable} ${instrumentSerif.variable} ${notoSansTelugu.variable} ${notoSerifTelugu.variable} ${notoSansDevanagari.variable} h-full antialiased`}
    >
      <body className="flex min-h-full flex-col bg-bone text-ink">
        <NextIntlClientProvider messages={messages}>
          <AppShell>{children}</AppShell>
        </NextIntlClientProvider>
      </body>
    </html>
  );
}
