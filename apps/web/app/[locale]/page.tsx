import { getTranslations } from "next-intl/server";
import { Icon } from "@/components/Icon";
import { JourneyMotion } from "@/components/JourneyMotion";
import { Link } from "@/i18n/navigation";

export default async function Home() {
  const t = await getTranslations("home");
  const nav = await getTranslations("workspace");
  return (
    <main className="product-page home-page">
      <p className="home-kicker">
        <span aria-hidden="true" />
        {t("eyebrow")}
      </p>
      <div className="home-hero">
        <div className="home-hero-copy">
          <h1 className="home-title">
            {t("title")}
            <br />
            <em>{t("titleAccent")}</em>
          </h1>
          <p>{t("intro")}</p>
          <div className="home-actions">
            <Link href="/path" className="primary-link">
              {t("primary")}
              <Icon name="arrow" />
            </Link>
            <Link href="/leads" className="secondary-link">
              {t("secondary")}
              <Icon name="arrow" />
            </Link>
          </div>
        </div>
        <section className="home-route" aria-label={t("how")}>
          <h2 className="section-label">{t("how")}</h2>
          {[1, 2, 3].map((step) => (
            <div className="journey-row" key={step}>
              <span className="journey-step" aria-hidden="true">
                0{step}
              </span>
              <div>
                <h3>{t(`step${step}`)}</h3>
                <p>{t(`step${step}Note`)}</p>
              </div>
            </div>
          ))}
        </section>
      </div>
      <JourneyMotion />
      <div className="section-heading">
        <h2>{t("choose")}</h2>
      </div>
      <div className="journey-grid">
        <section className="journey-card">
          <div className="journey-card-header">
            <span className="journey-icon">
              <Icon name="path" />
            </span>
            <span className="section-label">{t("studentTag")}</span>
          </div>
          <h3>{t("studentTitle")}</h3>
          <p>{t("studentIntro")}</p>
          <div className="journey-card-links">
            <Link href="/path">
              {nav("path")}
              <Icon name="arrow" />
            </Link>
            <Link href="/prep">
              {nav("prep")}
              <Icon name="arrow" />
            </Link>
            <Link href="/interview">
              {nav("interview")}
              <Icon name="arrow" />
            </Link>
          </div>
        </section>
        <section className="journey-card">
          <div className="journey-card-header">
            <span className="journey-icon">
              <Icon name="schemes" />
            </span>
            <span className="section-label">{t("ruralTag")}</span>
          </div>
          <h3>{t("ruralTitle")}</h3>
          <p>{t("ruralIntro")}</p>
          <div className="journey-card-links">
            <Link href="/leads">
              {nav("leads")}
              <Icon name="arrow" />
            </Link>
            <Link href="/schemes">
              {nav("schemes")}
              <Icon name="arrow" />
            </Link>
            <Link href="/voice">
              {nav("voice")}
              <Icon name="arrow" />
            </Link>
          </div>
        </section>
      </div>
      <section className="evidence-callout">
        <Icon name="evidence" />
        <div>
          <h2>{t("evidenceTitle")}</h2>
          <p>{t("evidenceIntro")}</p>
        </div>
        <Link href="/evidence" className="secondary-link">
          {nav("viewEvidence")}
          <Icon name="arrow" />
        </Link>
      </section>
    </main>
  );
}
