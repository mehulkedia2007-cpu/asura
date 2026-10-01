"use client";

import { useTranslations } from "next-intl";
import { useEffect, useState } from "react";
import { Icon, type IconName } from "@/components/Icon";
import { LanguageToggle } from "@/components/LanguageToggle";
import { VoicePanel } from "@/components/VoicePanel";
import { Link, usePathname } from "@/i18n/navigation";

export function AppShell({ children }: { children: React.ReactNode }) {
  const t = useTranslations("workspace");
  const pathname = usePathname();
  const [menuOpen, setMenuOpen] = useState(false);
  const [dark, setDark] = useState(false);
  const [connection, setConnection] = useState<
    "checking" | "online" | "offline"
  >("checking");
  const [retry, setRetry] = useState(0);
  const groups = [
    { label: "discover", routes: ["home", "path", "leads", "schemes"] },
    { label: "prepare", routes: ["questions", "prep", "interview"] },
    { label: "support", routes: ["voice", "evidence"] },
  ];
  const current = pathname.split("/").filter(Boolean)[0] || "home";

  useEffect(() => {
    try {
      const saved = localStorage.getItem("daari-theme") === "dark";
      setDark(saved);
      document.documentElement.dataset.theme = saved ? "dark" : "light";
    } catch {
      /* The default paper theme works without local storage. */
    }
  }, []);

  useEffect(() => {
    let active = true;
    const abort = new AbortController();
    const timeout = setTimeout(() => abort.abort(), 6000);
    setConnection("checking");
    fetch(`/api/engine/catalog?check=${retry}`, { signal: abort.signal })
      .then(async (response) => {
        const data = await response.json();
        if (!response.ok || !Array.isArray(data.skills))
          throw new Error("unavailable");
        if (active) setConnection("online");
      })
      .catch(() => {
        if (active) setConnection("offline");
      })
      .finally(() => clearTimeout(timeout));
    return () => {
      active = false;
      clearTimeout(timeout);
      abort.abort();
    };
  }, [retry]);

  useEffect(() => {
    if (!menuOpen) return;
    const close = (event: KeyboardEvent) => {
      if (event.key === "Escape") {
        setMenuOpen(false);
        document.getElementById("navigation-toggle")?.focus();
      }
    };
    document.addEventListener("keydown", close);
    return () => document.removeEventListener("keydown", close);
  }, [menuOpen]);

  function toggleTheme() {
    const next = !dark;
    setDark(next);
    document.documentElement.dataset.theme = next ? "dark" : "light";
    try {
      localStorage.setItem("daari-theme", next ? "dark" : "light");
    } catch {
      /* Theme still changes for this visit. */
    }
  }

  return (
    <div className="workspace">
      <a className="skip-link" href="#main-content">
        {t("skip")}
      </a>
      <header className="workspace-topbar">
        <div className="topbar-location">
          <button
            id="navigation-toggle"
            type="button"
            className="icon-button mobile-menu"
            aria-label={t(menuOpen ? "closeMenu" : "openMenu")}
            aria-expanded={menuOpen}
            aria-controls="workspace-navigation"
            onClick={() => setMenuOpen(!menuOpen)}
          >
            <Icon name={menuOpen ? "close" : "menu"} />
          </button>
          <Link href="/" className="mobile-brand">
            DAARI<span>↗</span>
          </Link>
          <span className="desktop-breadcrumb">
            {t("yourWorkspace")}
            <span aria-hidden="true">/</span>
            <strong>{t.has(current) ? t(current) : t("home")}</strong>
          </span>
        </div>
        <div className="topbar-tools">
          <LanguageToggle />
          <span className="tool-divider" />
          <button
            type="button"
            className="icon-button theme-toggle"
            aria-label={t(dark ? "lightTheme" : "darkTheme")}
            onClick={toggleTheme}
          >
            <Icon name={dark ? "sun" : "moon"} />
          </button>
          <VoicePanel />
        </div>
      </header>
      <aside
        className={`workspace-sidebar ${menuOpen ? "is-open" : ""}`}
        id="workspace-navigation"
      >
        <Link
          href="/"
          className="workspace-brand"
          onClick={() => setMenuOpen(false)}
        >
          DAARI<span>↗</span>
          <small>{t("brandNote")}</small>
        </Link>
        <nav aria-label={t("navigation")}>
          {groups.map((group) => (
            <div className="nav-group" key={group.label}>
              <p>{t(group.label)}</p>
              {group.routes.map((route) => {
                const href = route === "home" ? "/" : `/${route}`;
                const active = current === route;
                return (
                  <Link
                    key={route}
                    href={href}
                    aria-current={active ? "page" : undefined}
                    className={`workspace-nav-link ${active ? "active" : ""}`}
                    onClick={() => setMenuOpen(false)}
                  >
                    <Icon name={route as IconName} />
                    <span>{t(route)}</span>
                    {active && (
                      <span className="active-dot" aria-hidden="true" />
                    )}
                  </Link>
                );
              })}
            </div>
          ))}
        </nav>
        <div className="sidebar-note">
          <span className={`connection-dot ${connection}`} />
          <span>{t(connection)}</span>
          <Link href="/evidence" onClick={() => setMenuOpen(false)}>
            {t("viewEvidence")} ↗
          </Link>
        </div>
      </aside>
      <div className="workspace-content" id="main-content" tabIndex={-1}>
        {connection === "offline" && (
          <div className="connection-banner" role="status">
            <span>{t("offlineNotice")}</span>
            <button
              type="button"
              onClick={() => setRetry((value) => value + 1)}
            >
              {t("retry")} ↻
            </button>
          </div>
        )}
        {children}
        <footer className="workspace-footer">
          <span>
            DAARI <span aria-hidden="true">/</span> {t("footer")}
          </span>
          <Link href="/evidence">
            {t("viewEvidence")} <Icon name="arrow" />
          </Link>
        </footer>
      </div>
    </div>
  );
}
