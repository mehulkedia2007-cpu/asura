"use client";

import { useLocale, useTranslations } from "next-intl";
import { useEffect, useRef, useState } from "react";
import { Icon } from "@/components/Icon";
import { PageIntro } from "@/components/PageIntro";

type Lead = {
  id: string;
  title: string;
  org: string;
  location: string;
  distance_km: number | null;
  pay: string | null;
  required_skills: Record<string, number>;
  scam: { badge: string; score: number; reasons: string[] };
  source: string;
  source_url: string;
  fetched_at: string;
  new_since_visit: boolean;
  remote: boolean;
  published_at?: string;
  published_label?: string;
  government?: boolean;
  match?: {
    score: number;
    missing: string[];
    components: Record<string, number>;
  };
};
type Scheme = {
  id: string;
  name_en: string;
  name_te?: string | null;
  summary_te?: string | null;
  benefit_text: string;
  eligibility_text: string;
  documents_text?: string;
  apply_steps?: { channel: string; text: string }[];
  eligibility: { status: string; reasons: string[]; missing_fields: string[] };
  url: string;
  fetched_at: string;
  level: string;
  source?: string;
  as_of?: string | null;
};
type Result = {
  leads?: Lead[];
  schemes?: Scheme[];
  radius_km?: number;
  job_type?: string;
  demand?: Record<string, number>;
  errors?: Record<string, string>;
  error?: string | null;
  stale?: boolean;
  refresh_status?: "not_requested" | "updated" | "unavailable";
  source_errors?: string[];
  truncated?: boolean;
  coverage?: {
    indexed: number;
    ap: number;
    central: number;
    other: number;
    latest_refresh: string | null;
    sources: {
      source_id: string;
      status: string;
      error: string | null;
      links: number;
    }[];
  };
  next_question?: {
    scheme_id: string;
    field: string;
    source_snippets: string[];
  } | null;
};

export function LiveSearch({ kind }: { kind: "leads" | "schemes" }) {
  const t = useTranslations("live");
  const workspace = useTranslations("workspace");
  const locale = useLocale();
  const request = useRef<AbortController | null>(null);
  const [jobType, setJobType] = useState("local");
  const [includeRemote, setIncludeRemote] = useState(false);
  const [query, setQuery] = useState("");
  const [schemeId, setSchemeId] = useState("");
  const [choices, setChoices] = useState<
    { id: string; name_en: string; name_te?: string }[]
  >([]);
  const [place, setPlace] = useState("Guntur, Andhra Pradesh");
  const [age, setAge] = useState("");
  const [income, setIncome] = useState("");
  const [result, setResult] = useState<Result | null>(null);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const [newSchemeIds, setNewSchemeIds] = useState<string[]>([]);
  const [extraProfile, setExtraProfile] = useState<Record<string, string>>({});
  const [slotAnswer, setSlotAnswer] = useState("");
  const [skillLabels, setSkillLabels] = useState<Record<string, string>>({});
  useEffect(() => {
    if (kind !== "schemes") return;
    const controller = new AbortController();
    fetch("/api/engine/schemes/options", { signal: controller.signal })
      .then((response) => (response.ok ? response.json() : Promise.reject()))
      .then((data) => setChoices(data.schemes ?? []))
      .catch(() => {});
    return () => controller.abort();
  }, [kind]);
  useEffect(() => {
    let active = true;
    fetch("/api/engine/catalog")
      .then((response) => response.json())
      .then((data) => {
        if (active && Array.isArray(data.skills))
          setSkillLabels(
            Object.fromEntries(
              data.skills.map(
                (skill: {
                  id: string;
                  label_en: string;
                  label_te: string;
                  label_hi: string;
                }) => [
                  skill.id,
                  locale === "te"
                    ? skill.label_te
                    : locale === "hi"
                      ? skill.label_hi
                      : skill.label_en,
                ],
              ),
            ),
          );
      })
      .catch(() => {});
    return () => {
      active = false;
    };
  }, [locale]);

  function invalidate() {
    request.current?.abort();
    setResult(null);
    setError("");
    setBusy(false);
  }
  useEffect(() => () => request.current?.abort(), []);
  async function search(
    refresh = false,
    profileUpdate: Record<string, string> = {},
  ) {
    if (!query.trim() && !(kind === "leads" && jobType === "government"))
      return;
    request.current?.abort();
    const controller = new AbortController();
    request.current = controller;
    setBusy(true);
    setError("");
    try {
      let held: Record<string, number> = {};
      try {
        held = JSON.parse(localStorage.getItem("daari-held") ?? "{}");
      } catch {
        held = {};
      }
      const body =
        kind === "leads"
          ? {
              query: query.trim() || "recruitment",
              place,
              include_remote: includeRemote,
              job_type: jobType,
              held,
              refresh,
              since: localStorage.getItem("daari-leads-last-visit"),
            }
          : {
              query,
              scheme_id: schemeId || null,
              profile: {
                state: "Andhra Pradesh",
                age: age ? Number(age) : null,
                annual_income: income ? Number(income) : null,
                ...extraProfile,
                ...profileUpdate,
              },
              refresh,
              locale,
            };
      if (kind === "leads") localStorage.setItem("daari-place", place);
      const response = await fetch(`/api/engine/${kind}/search`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body),
        signal: AbortSignal.any([
          controller.signal,
          AbortSignal.timeout(
            kind === "schemes" ? (refresh ? 15_000 : 8_000) : 90_000,
          ),
        ]),
      });
      const data = await response.json();
      if (!response.ok)
        throw new Error(
          response.status >= 500
            ? t("unavailable")
            : t.has(data.detail ?? "")
              ? t(data.detail)
              : (data.detail ?? t("unavailable")),
        );
      if (controller.signal.aborted) return;
      setResult(data);
      if (kind === "leads") {
        localStorage.setItem(
          "daari-leads-last-visit",
          new Date().toISOString(),
        );
        if (data.demand)
          localStorage.setItem("daari-demand", JSON.stringify(data.demand));
      } else {
        let seen = new Set<string>();
        try {
          const previous = JSON.parse(
            localStorage.getItem("daari-seen-schemes") ?? "[]",
          );
          if (Array.isArray(previous)) seen = new Set(previous);
        } catch {
          // A damaged visit history must not turn a successful search into an error.
        }
        const ids = (data.schemes ?? []).map((item: Scheme) => item.id);
        setNewSchemeIds(ids.filter((id: string) => !seen.has(id)));
        try {
          localStorage.setItem(
            "daari-seen-schemes",
            JSON.stringify([...new Set([...seen, ...ids])]),
          );
        } catch {
          // Browser storage may be unavailable; results still remain usable.
        }
      }
    } catch (cause) {
      if (!controller.signal.aborted)
        setError(cause instanceof Error ? cause.message : t("unavailable"));
    } finally {
      if (request.current === controller) setBusy(false);
    }
  }

  return (
    <main className="product-page">
      <PageIntro
        eyebrow={workspace("discover")}
        title={t(kind === "leads" ? "leadsTitle" : "schemesTitle")}
        description={t(kind === "leads" ? "leadsIntro" : "schemesIntro")}
        icon={kind}
      />
      <p className="status-note">
        {t(kind === "leads" ? "apJobsScope" : "apSchemesScope")}
      </p>
      <label className="surface mb-5 grid gap-2">
        {t(kind === "leads" ? "chooseJob" : "chooseScheme")}
        <select
          aria-label={t(kind === "leads" ? "chooseJob" : "chooseScheme")}
          value={schemeId ? `scheme:${schemeId}` : query}
          onChange={(event) => {
            invalidate();
            const value = event.target.value;
            const chosen = choices.find(
              (item) => `scheme:${item.id}` === value,
            );
            setSchemeId(chosen?.id ?? "");
            setQuery(chosen ? chosen.name_en.slice(0, 100) : value);
          }}
        >
          <option value="">{t("choosePrompt")}</option>
          {(kind === "leads"
            ? [
                ["sales", "jobSales"],
                ["customer service", "jobSupport"],
                ["data entry", "jobEntry"],
                ["delivery", "jobDelivery"],
                ["python", "jobPython"],
              ]
            : [
                ["skill training", "schemeTraining"],
                ["education scholarship", "schemeEducation"],
                ["business loan", "schemeBusiness"],
                ["farmer", "schemeFarmer"],
                ["women", "schemeWomen"],
              ]
          ).map(([value, key]) => (
            <option key={value} value={value}>
              {t(key)}
            </option>
          ))}
          {kind === "schemes" && choices.length > 0 && (
            <optgroup label={t("namedSchemes")}>
              {choices.map((item) => (
                <option key={item.id} value={`scheme:${item.id}`}>
                  {locale === "te"
                    ? item.name_te || item.name_en
                    : item.name_en}
                </option>
              ))}
            </optgroup>
          )}
          {query &&
            !schemeId &&
            !(
              kind === "leads"
                ? [
                    "sales",
                    "customer service",
                    "data entry",
                    "delivery",
                    "python",
                  ]
                : [
                    "skill training",
                    "education scholarship",
                    "business loan",
                    "farmer",
                    "women",
                  ]
            ).includes(query) && <option value={query}>{query}</option>}
        </select>
        <span className="text-sm text-graphite">{t("choiceHelp")}</span>
      </label>
      <form
        className="control-panel flex flex-wrap gap-4"
        onSubmit={(event) => {
          event.preventDefault();
          void search();
        }}
      >
        {kind === "leads" && (
          <label className="flex min-w-48 flex-1 flex-col gap-2 text-sm">
            {t("jobType")}
            <select
              aria-label={t("jobType")}
              value={jobType}
              onChange={(event) => {
                invalidate();
                setJobType(event.target.value);
                setIncludeRemote(false);
              }}
            >
              <option value="local">{t("localJobs")}</option>
              <option value="government">{t("governmentJobs")}</option>
            </select>
          </label>
        )}
        <label className="flex min-w-48 flex-1 flex-col gap-2 text-sm">
          {t("query")}
          <input
            className="rounded border border-graphite/30 bg-background p-2"
            value={query}
            placeholder={t(
              kind === "leads" ? "searchPlaceholder" : "schemePlaceholder",
            )}
            onChange={(event) => {
              invalidate();
              setSchemeId("");
              setQuery(event.target.value);
            }}
            required={kind !== "leads" || jobType !== "government"}
          />
        </label>
        {kind === "leads" ? (
          <label className="flex min-w-48 flex-1 flex-col gap-2 text-sm">
            {t("place")}
            <input
              className="rounded border border-graphite/30 bg-background p-2"
              value={place}
              onChange={(event) => {
                invalidate();
                setPlace(event.target.value);
              }}
              required
            />
          </label>
        ) : (
          <>
            <label className="flex w-28 flex-col gap-2 text-sm">
              {t("age")}
              <input
                type="number"
                min="0"
                className="rounded border border-graphite/30 bg-background p-2"
                value={age}
                onChange={(event) => {
                  invalidate();
                  setAge(event.target.value);
                }}
              />
            </label>
            <label className="flex w-40 flex-col gap-2 text-sm">
              {t("income")}
              <input
                type="number"
                min="0"
                className="rounded border border-graphite/30 bg-background p-2"
                value={income}
                onChange={(event) => {
                  invalidate();
                  setIncome(event.target.value);
                }}
              />
            </label>
          </>
        )}
        {kind === "leads" && jobType === "local" && (
          <label className="flex items-center gap-2 text-sm">
            <input
              type="checkbox"
              checked={includeRemote}
              onChange={(event) => {
                invalidate();
                setIncludeRemote(event.target.checked);
              }}
            />
            {t("includeRemote")}
          </label>
        )}
        <div className="flex items-end gap-2">
          <button
            type="submit"
            disabled={busy}
            className="rounded bg-signal px-4 py-2 text-white disabled:opacity-50"
          >
            {t("search")}
          </button>
          <button
            type="button"
            disabled={busy || (!query.trim() && jobType !== "government")}
            onClick={() => void search(true)}
            className="rounded border border-graphite/40 px-4 py-2 disabled:opacity-50"
          >
            {t("refresh")}
          </button>
        </div>
      </form>
      {!result && !busy && !error && (
        <section className="empty-state">
          <Icon name={kind} />
          <h2>
            {t(kind === "leads" ? "emptyLeadsTitle" : "emptySchemesTitle")}
          </h2>
          <p>{t(kind === "leads" ? "emptyLeadsIntro" : "emptySchemesIntro")}</p>
        </section>
      )}
      {busy && (
        <p role="status" className="mt-5">
          {t("loading")}
        </p>
      )}
      {error && (
        <p role="alert" className="mt-5 text-signal">
          {error}
        </p>
      )}
      {result?.stale && (
        <p role="note" className="mt-5 text-graphite">
          {t("stale")}
        </p>
      )}
      {kind === "schemes" && result?.refresh_status === "updated" && (
        <p role="status" className="mt-5 text-sage">
          {t("refreshDone")}
        </p>
      )}
      {kind === "schemes" &&
        result?.refresh_status === "unavailable" &&
        !result.source_errors?.length && (
          <p role="status" className="mt-5 text-graphite">
            {t("refreshNoChange")}
          </p>
        )}
      {result?.error && (
        <p className="mt-5 text-signal">
          {t("sourceError")}: {result.error}
        </p>
      )}
      {result?.source_errors && result.source_errors.length > 0 && (
        <p className="mt-5 text-signal">
          {kind === "schemes"
            ? t("schemeRefreshUnavailable")
            : `${t("sourceError")}: ${result.source_errors.join(", ")}`}
        </p>
      )}
      {result?.truncated && (
        <p className="mt-5 text-graphite">{t("truncated")}</p>
      )}
      {result?.errors && Object.keys(result.errors).length > 0 && (
        <p className="mt-5 text-signal">
          {t("sourceError")}:{" "}
          {Object.entries(result.errors)
            .map(([name, reason]) => `${name} (${reason})`)
            .join(", ")}
        </p>
      )}
      {result && (
        <p
          className="status-note font-mono text-xs text-graphite"
          role="status"
        >
          {kind === "leads"
            ? `${result.leads?.length ?? 0} ${t("results")} · ${result.job_type === "government" ? t("statewide") : `${t("radius")} ${result.radius_km ?? 0} km`}`
            : `${result.schemes?.length ?? 0} ${t("results")}`}
        </p>
      )}
      {kind === "schemes" && result?.coverage && (
        <div className="mt-2 text-graphite text-sm">
          <p>
            {t("indexed")}: {result.coverage.indexed} · AP {result.coverage.ap}{" "}
            · {t("central")} {result.coverage.central}
            {result.coverage.other
              ? ` · ${t("other")} ${result.coverage.other}`
              : ""}
            {result.coverage.latest_refresh
              ? ` · ${t("fetched")} ${new Date(result.coverage.latest_refresh).toLocaleString()}`
              : ""}
          </p>
          {result.coverage.sources.length > 0 && (
            <details className="mt-2">
              <summary>{t("sourceStatus")}</summary>
              <ul className="mt-2 list-disc pl-5">
                {result.coverage.sources.map((source) => (
                  <li key={source.source_id}>
                    {source.source_id}: {t(`status_${source.status}`)}
                    {source.error ? ` (${source.error})` : ""}
                  </li>
                ))}
              </ul>
            </details>
          )}
        </div>
      )}
      {kind === "schemes" && result?.next_question && (
        <form
          className="mt-4 rounded-xl border border-graphite/25 p-4"
          onSubmit={(event) => {
            event.preventDefault();
            if (!slotAnswer.trim() || !result.next_question) return;
            const update = { [result.next_question.field]: slotAnswer.trim() };
            setExtraProfile((prior) => ({ ...prior, ...update }));
            setSlotAnswer("");
            void search(false, update);
          }}
        >
          <label className="block text-sm" htmlFor="scheme-slot">
            {t("oneQuestion", {
              field: t(`field_${result.next_question.field}`),
            })}
          </label>
          <input
            id="scheme-slot"
            className="mt-2 rounded border border-graphite/30 bg-background p-2"
            value={slotAnswer}
            onChange={(event) => setSlotAnswer(event.target.value)}
            required
          />
          <button
            className="ml-2 rounded bg-signal px-4 py-2 text-white"
            type="submit"
          >
            {t("checkAgain")}
          </button>
          <p className="mt-2 text-graphite text-xs">
            {result.next_question.source_snippets.join("; ")}
          </p>
        </form>
      )}
      {result && !(result.leads?.length || result.schemes?.length) && (
        <div className="surface mt-5 space-y-3">
          <p>{t("noData")}</p>
          <p>{t(kind === "leads" ? "noJobsHelp" : "noSchemesHelp")}</p>
          {kind === "leads" && (
            <a
              className="text-signal underline"
              href="https://www.ncs.gov.in/"
              target="_blank"
              rel="noreferrer"
            >
              {t("officialJobs")}
            </a>
          )}
          {kind === "schemes" && (
            <a
              className="text-signal underline"
              href="https://www.myscheme.gov.in/"
              target="_blank"
              rel="noreferrer"
            >
              {t("officialSchemes")}
            </a>
          )}
        </div>
      )}
      <div className="mt-5 grid gap-4 md:grid-cols-2">
        {result?.leads?.map((lead) => (
          <article key={lead.id} className="result-card">
            <div className="flex items-start justify-between gap-3">
              <h2 className="text-xl font-semibold">{lead.title}</h2>
              {lead.scam.badge !== "none" && (
                <span className="rounded bg-signal/10 px-2 py-1 text-signal text-sm">
                  {t("scam")}: {lead.scam.badge}
                </span>
              )}
            </div>
            <p className="mt-1 text-graphite">
              {lead.org} · {lead.location}
            </p>
            <p className="mt-2 font-mono text-xs">
              {lead.remote
                ? t("remote")
                : lead.distance_km == null
                  ? t("distanceUnknown")
                  : `${lead.distance_km} km`}{" "}
              {lead.pay ? `· ${lead.pay}` : ""}
            </p>
            {lead.government && (
              <p className="mt-2 text-graphite text-sm">{t("govWindow")}</p>
            )}
            {lead.published_at && (
              <p className="mt-2 font-mono text-xs">
                {t("published")}{" "}
                {lead.published_label ||
                  new Date(lead.published_at).toLocaleDateString()}
              </p>
            )}
            {lead.match && (
              <div className="match-panel">
                <div>
                  <span>{t("match")}</span>
                  <strong>{lead.match.score.toFixed(2)}</strong>
                </div>
                <details>
                  <summary>{t("breakdown")}</summary>
                  <dl>
                    {Object.entries(lead.match.components).map(
                      ([name, value]) => (
                        <div key={name}>
                          <dt>{t.has(name) ? t(name) : name}</dt>
                          <dd>{value.toFixed(3)}</dd>
                        </div>
                      ),
                    )}
                  </dl>
                </details>
                <p>
                  {t("missing")}:{" "}
                  {lead.match.missing.length
                    ? lead.match.missing.map((id) => (
                        <span key={id} className="missing-skill">
                          {skillLabels[id] ?? id}
                        </span>
                      ))
                    : t("none")}
                </p>
              </div>
            )}
            {lead.scam.reasons.length > 0 && (
              <p className="mt-2 text-signal text-sm">
                {lead.scam.reasons.join("; ")}
              </p>
            )}
            {lead.new_since_visit && (
              <p className="mt-2 text-sage">{t("new")}</p>
            )}
            <div className="source-footer">
              <p>
                {lead.source} · {t("fetched")}{" "}
                {new Date(lead.fetched_at).toLocaleString()}
              </p>
              <a
                className="text-signal underline underline-offset-4"
                href={lead.source_url}
                target="_blank"
                rel="noopener noreferrer"
              >
                {t("sourceLink")}
              </a>
            </div>
          </article>
        ))}
        {result?.schemes?.map((scheme) => (
          <article key={scheme.id} className="result-card">
            <h2 className="text-xl font-semibold">
              {locale === "te" && scheme.name_te
                ? scheme.name_te
                : scheme.name_en}
            </h2>
            {newSchemeIds.includes(scheme.id) && (
              <p className="mt-1 text-sage">{t("new")}</p>
            )}
            <p
              className={`eligibility-badge ${scheme.eligibility.status === "true" ? "eligible" : "unknown"}`}
            >
              {scheme.level} · {t("eligibility")}:{" "}
              {t(
                scheme.eligibility.status === "true"
                  ? "qualifies"
                  : scheme.eligibility.status === "false"
                    ? "doesNotQualify"
                    : "unknown",
              )}
            </p>
            {(locale === "te" && scheme.summary_te
              ? scheme.summary_te
              : scheme.benefit_text) && (
              <p className="mt-3 whitespace-pre-line">
                {locale === "te" && scheme.summary_te
                  ? scheme.summary_te
                  : scheme.benefit_text}
              </p>
            )}
            {scheme.eligibility.reasons.length > 0 && (
              <p className="mt-3 text-sm">
                {t(
                  scheme.eligibility.status === "false"
                    ? "unmatchedRules"
                    : "whyQualifies",
                )}
                : {scheme.eligibility.reasons.join("; ")}
              </p>
            )}
            {scheme.eligibility.missing_fields.length > 0 && (
              <p className="mt-3">
                {t("unknownQuestion")}{" "}
                {scheme.eligibility.missing_fields
                  .map((field) =>
                    t.has(`field_${field}`) ? t(`field_${field}`) : field,
                  )
                  .join(", ")}
              </p>
            )}
            {scheme.eligibility_text && (
              <details className="mt-3 text-sm">
                <summary>{t("eligibilityText")}</summary>
                <p className="mt-2 whitespace-pre-line">
                  {scheme.eligibility_text}
                </p>
              </details>
            )}
            {scheme.documents_text && (
              <details className="mt-3 text-sm">
                <summary>{t("documents")}</summary>
                <p className="mt-2 whitespace-pre-line">
                  {scheme.documents_text}
                </p>
              </details>
            )}
            {scheme.apply_steps && scheme.apply_steps.length > 0 && (
              <details className="mt-3 text-sm">
                <summary>{t("applySteps")}</summary>
                {scheme.apply_steps.map((step) => (
                  <p
                    key={`${scheme.id}-${step.channel}-${step.text}`}
                    className="mt-2 whitespace-pre-line"
                  >
                    {step.channel}: {step.text}
                  </p>
                ))}
              </details>
            )}
            <div className="source-footer">
              <p>
                {scheme.source ?? "myScheme"} · {t("fetched")}{" "}
                {new Date(scheme.fetched_at).toLocaleString()}
                {scheme.as_of ? ` · ${t("sourceUpdated")} ${scheme.as_of}` : ""}
              </p>
              <a
                className="text-signal underline underline-offset-4"
                href={scheme.url}
                target="_blank"
                rel="noopener noreferrer"
              >
                {t("sourceLink")}
              </a>
            </div>
          </article>
        ))}
      </div>
      {kind === "leads" && (
        <p className="mt-8 text-graphite text-xs">{t("osm")}</p>
      )}
    </main>
  );
}
