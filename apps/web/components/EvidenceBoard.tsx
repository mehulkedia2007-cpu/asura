"use client";

import { useLocale, useTranslations } from "next-intl";
import { useEffect, useState } from "react";
import { Link } from "@/i18n/navigation";

type MetricProps = {
  label: string;
  value: string;
  detail?: string;
  passed?: boolean;
};

type Board = {
  phase: string;
  generated_at: string;
  ci_sha: string;
  scope: string;
  shared_engine: {
    counters: Record<string, Record<string, number>>;
    import_graph: { status: string; shared_by: string[] };
  };
  roadmap: {
    passed: boolean;
    baseline_hours: number;
    after_learning_hours: number;
    checks: Record<string, boolean>;
  };
  match_ablations: {
    passed: boolean;
    graph_on: number;
    graph_off: number;
    vector_on: number;
    vector_off: number;
  };
  scheme_retrieval: {
    passed: boolean;
    precision_at_5: number;
    recall_at_5: number;
    hit_at_5: number;
    precision_en: number;
    precision_te: number;
    cases: number;
    corpus_records: number;
    scope?: string;
  };
  live_scheme_retrieval: {
    available: boolean;
    passed: boolean;
    precision_at_5?: number;
    recall_at_5?: number;
    cases: number;
    scope: string;
  };
  scam: {
    passed: boolean;
    recall: number;
    precision: number;
    false_positive: number;
    false_negative: number;
    cases: number;
  };
  grounding: {
    passed: boolean;
    f1: number;
    no_data: { violations: number; cases: number };
  };
  interview: {
    intel: { recall_at_5: number; cases: number };
    feedback: { must_mention_recall: number; cases: number };
  };
  notice: { field_accuracy: number; cases: number };
  voice: {
    cached_browser: {
      results: Record<
        string,
        { first_playback_p95_ms: number; response_done_p95_ms: number }
      >;
    };
    live_samples: Record<string, { n: number; p50: number; p95: number }>;
  };
  i18n: { keys: number; passed: boolean };
  constitution: {
    article: string;
    title: string;
    test: string;
    status: string;
  }[];
  sources: {
    scheme_corpus: number;
    scheme_golden: number;
    interview_report: number;
  };
};

function Metric({ label, value, detail, passed }: MetricProps) {
  return (
    <div className="border-graphite/25 border-t pt-3">
      <div className="flex items-start justify-between gap-3">
        <p className="font-ui text-graphite text-xs uppercase tracking-[0.14em]">
          {label}
        </p>
        {passed !== undefined && (
          <span className={passed ? "text-sage" : "text-signal"}>
            {passed ? "●" : "○"}
          </span>
        )}
      </div>
      <p className="mt-2 font-mono text-2xl text-ink tabular-nums">{value}</p>
      {detail && <p className="mt-1 font-ui text-graphite text-xs">{detail}</p>}
    </div>
  );
}

function Panel({
  eyebrow,
  title,
  children,
}: {
  eyebrow: string;
  title: string;
  children: React.ReactNode;
}) {
  return (
    <section className="border-graphite/30 border-t pt-5">
      <p className="font-mono text-graphite text-xs uppercase tracking-[0.18em]">
        {eyebrow}
      </p>
      <h2 className="mt-2 font-display text-3xl text-ink sm:text-4xl">
        {title}
      </h2>
      <div className="mt-6">{children}</div>
    </section>
  );
}

function Bar({ label, on, off }: { label: string; on: number; off: number }) {
  const max = Math.max(Math.abs(on), Math.abs(off), 0.01);
  return (
    <div className="space-y-2">
      <div className="flex justify-between gap-4 font-ui text-graphite text-xs">
        <span>{label}</span>
        <span className="font-mono">
          {on.toFixed(3)} / {off.toFixed(3)}
        </span>
      </div>
      <div
        role="img"
        className="grid grid-cols-2 gap-2"
        aria-label={`${label}: on ${on}, off ${off}`}
      >
        <div
          className="h-2 bg-signal"
          style={{ width: `${Math.max(8, (Math.abs(on) / max) * 100)}%` }}
        />
        <div
          className="h-2 bg-graphite/40"
          style={{ width: `${Math.max(8, (Math.abs(off) / max) * 100)}%` }}
        />
      </div>
    </div>
  );
}

function BoardContent({ board }: { board: Board }) {
  const t = useTranslations("p6");
  const locale = useLocale();
  const counters = board.shared_engine.counters;
  const studentCalls = Object.values(counters.student ?? {}).reduce(
    (sum, value) => sum + value,
    0,
  );
  const ruralCalls = Object.values(counters.rural ?? {}).reduce(
    (sum, value) => sum + value,
    0,
  );
  const cached = board.voice.cached_browser.results;
  const formatPercent = (value: number) => `${Math.round(value * 100)}%`;
  const checkLabels: Record<string, string> = {
    learning_never_lengthens: t("learningCheck"),
    market_shock_computes: t("marketCheck"),
    deterministic_replay: t("deterministicCheck"),
  };

  return (
    <>
      <div className="flex flex-wrap items-center justify-between gap-4 border-graphite/25 border-y py-3">
        <p className="max-w-2xl font-ui text-graphite text-sm">{t("scope")}</p>
        <p className="font-mono text-graphite text-xs">
          {t("sha")}: {board.ci_sha} ·{" "}
          {new Date(board.generated_at).toLocaleString(locale)}
        </p>
      </div>

      <div className="mt-16 grid gap-16 lg:grid-cols-[1.2fr_0.8fr]">
        <Panel eyebrow={t("engine")} title={t("shared")}>
          <p className="max-w-xl font-ui text-graphite text-sm">
            {t("sharedIntro")}
          </p>
          <div className="mt-8 grid gap-6 sm:grid-cols-2">
            <Metric
              label={t("student")}
              value={`${studentCalls}`}
              detail={t("calls")}
            />
            <Metric
              label={t("rural")}
              value={`${ruralCalls}`}
              detail={t("calls")}
            />
          </div>
        </Panel>
        <div className="border-graphite/25 border-t pt-5">
          <p className="font-mono text-graphite text-xs uppercase tracking-[0.18em]">
            {t("importGraph")}
          </p>
          <p className="mt-4 font-mono text-sage text-sm">
            {board.shared_engine.import_graph.status.toUpperCase()}
          </p>
          <p className="mt-4 font-ui text-graphite text-sm">{t("clean")}</p>
          <p className="mt-5 font-mono text-graphite text-xs">
            {t("sharedBy")}: {t("student")} · {t("rural")}
          </p>
        </div>
      </div>

      <div className="mt-20">
        <Panel eyebrow={t("regression")} title={t("quality")}>
          <div className="grid gap-x-8 gap-y-10 sm:grid-cols-2 lg:grid-cols-5">
            <Metric
              label={t("scheme")}
              value={formatPercent(board.scheme_retrieval.precision_at_5)}
              detail={`${t("precision")} · ${board.scheme_retrieval.cases} ${t("cases")} · ${t("frozenSnapshot")}`}
              passed={board.scheme_retrieval.passed}
            />
            <Metric
              label={t("liveScheme")}
              value={
                board.live_scheme_retrieval.available &&
                board.live_scheme_retrieval.precision_at_5 !== undefined
                  ? formatPercent(board.live_scheme_retrieval.precision_at_5)
                  : "—"
              }
              detail={
                board.live_scheme_retrieval.available
                  ? `${t("precision")} · ${board.live_scheme_retrieval.cases} ${t("cases")} · ${t("liveSchemeScope")}`
                  : t("liveSchemeUnavailable")
              }
              passed={
                board.live_scheme_retrieval.available &&
                board.live_scheme_retrieval.passed
              }
            />
            <Metric
              label={t("scam")}
              value={formatPercent(board.scam.recall)}
              detail={`${t("falseNegative")}: ${board.scam.false_negative}`}
              passed={board.scam.passed}
            />
            <Metric
              label={t("grounding")}
              value={board.grounding.f1.toFixed(3)}
              detail={`${t("violations")}: ${board.grounding.no_data.violations}`}
              passed={board.grounding.passed}
            />
            <Metric
              label={t("interview")}
              value={formatPercent(
                board.interview.feedback.must_mention_recall,
              )}
              detail={`${board.interview.feedback.cases} ${t("answerCases")}`}
              passed={board.interview.feedback.must_mention_recall >= 0.8}
            />
            <Metric
              label={t("notice")}
              value={formatPercent(board.notice.field_accuracy)}
              detail={`${board.notice.cases} ${t("syntheticNotices")}`}
              passed={board.notice.field_accuracy >= 0.9}
            />
          </div>
          <div className="mt-12 grid gap-8 lg:grid-cols-2">
            <div>
              <h3 className="font-ui text-ink text-sm">{t("roadmap")}</h3>
              <div className="mt-4 grid gap-3 sm:grid-cols-3">
                {Object.entries(board.roadmap.checks).map(([name, passed]) => (
                  <div key={name} className="border-graphite/20 border p-3">
                    <span
                      className={
                        passed
                          ? "font-mono text-sage text-xs"
                          : "font-mono text-signal text-xs"
                      }
                    >
                      {passed ? "PASS" : "CHECK"}
                    </span>
                    <p className="mt-2 font-ui text-graphite text-xs">
                      {checkLabels[name] ?? name.replaceAll("_", " ")}
                    </p>
                  </div>
                ))}
              </div>
              <p className="mt-4 font-mono text-graphite text-xs">
                {board.roadmap.baseline_hours}h →{" "}
                {board.roadmap.after_learning_hours}h
              </p>
            </div>
            <div>
              <h3 className="font-ui text-ink text-sm">{t("ablations")}</h3>
              <div className="mt-4 space-y-5">
                <Bar
                  label={`${t("graphOn")} / ${t("graphOff")}`}
                  on={board.match_ablations.graph_on}
                  off={board.match_ablations.graph_off}
                />
                <Bar
                  label={`${t("vectorOn")} / ${t("vectorOff")}`}
                  on={board.match_ablations.vector_on}
                  off={board.match_ablations.vector_off}
                />
              </div>
            </div>
          </div>
        </Panel>
      </div>

      <div className="mt-20 grid gap-16 lg:grid-cols-2">
        <Panel eyebrow={t("voiceSection")} title={t("voice")}>
          <p className="max-w-lg font-ui text-graphite text-sm">
            {t("voiceIntro")}
          </p>
          <div className="mt-8 grid gap-6 sm:grid-cols-3">
            {Object.entries(cached).map(([cachedLocale, result]) => (
              <div
                key={cachedLocale}
                className="border-graphite/25 border-t pt-3"
              >
                <p className="font-mono text-ink text-sm uppercase">
                  {cachedLocale}
                </p>
                <p className="mt-3 font-mono text-2xl text-ink">
                  {result.first_playback_p95_ms}ms
                </p>
                <p className="mt-1 font-ui text-graphite text-xs">
                  {t("firstPlayback")}
                </p>
                <p className="mt-3 font-mono text-graphite text-sm">
                  {result.response_done_p95_ms}ms
                </p>
                <p className="mt-1 font-ui text-graphite text-xs">
                  {t("responseDone")}
                </p>
              </div>
            ))}
          </div>
        </Panel>
        <Panel eyebrow={t("coverage")} title={t("i18n")}>
          <div className="grid gap-6 sm:grid-cols-3">
            <Metric
              label={t("keys")}
              value={`${board.i18n.keys}`}
              passed={board.i18n.passed}
            />
            <Metric
              label={t("schemeCorpus")}
              value={`${board.sources.scheme_corpus}`}
            />
            <Metric
              label={t("reports")}
              value={`${board.sources.interview_report}`}
            />
          </div>
          <p className="mt-6 font-mono text-graphite text-xs">
            {t("golden")}: {board.sources.scheme_golden}
          </p>
        </Panel>
      </div>

      <div className="mt-20">
        <Panel eyebrow={t("constitutionSection")} title={t("constitution")}>
          <p className="max-w-2xl font-ui text-graphite text-sm">
            {t("constitutionIntro")}
          </p>
          <div className="mt-8 overflow-x-auto border-graphite/25 border-y">
            <table className="w-full min-w-[680px] border-collapse text-left">
              <thead>
                <tr className="border-graphite/20 border-b font-mono text-graphite text-xs uppercase tracking-[0.12em]">
                  <th className="px-3 py-3">{t("article")}</th>
                  <th className="px-3 py-3">{t("status")}</th>
                  <th className="px-3 py-3">{t("test")}</th>
                </tr>
              </thead>
              <tbody>
                {board.constitution.map((article) => (
                  <tr
                    key={article.article}
                    className="border-graphite/15 border-b last:border-0"
                  >
                    <td className="px-3 py-3 font-ui text-ink text-sm">
                      {article.article} · {article.title}
                    </td>
                    <td className="px-3 py-3 font-mono text-amber text-xs">
                      {article.status.toUpperCase()}
                    </td>
                    <td className="px-3 py-3 font-mono text-graphite text-xs">
                      {article.test}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </Panel>
      </div>
    </>
  );
}

export function EvidenceBoard() {
  const t = useTranslations("p6");
  const [board, setBoard] = useState<Board | null>(null);
  const [error, setError] = useState(false);
  const [refresh, setRefresh] = useState(0);

  useEffect(() => {
    let active = true;
    fetch(`/api/engine/evidence?refresh=${refresh}`, { cache: "no-store" })
      .then((response) => {
        if (!response.ok) throw new Error("request_failed");
        return response.json() as Promise<Board>;
      })
      .then((value) => {
        if (active) {
          setBoard(value);
          setError(false);
        }
      })
      .catch(() => active && setError(true));
    return () => {
      active = false;
    };
  }, [refresh]);

  if (error) {
    return (
      <p className="border-signal border-l-2 p-4 font-ui text-graphite text-sm">
        {t("unavailable")}
      </p>
    );
  }
  if (!board) {
    return <p className="font-mono text-graphite text-sm">{t("loading")}</p>;
  }

  return (
    <div>
      <div className="mb-10 flex flex-wrap items-center justify-between gap-4">
        <p className="font-mono text-graphite text-xs">{t("scope")}</p>
        <button
          type="button"
          onClick={() => setRefresh((value) => value + 1)}
          className="border border-ink px-4 py-2 font-ui text-ink text-sm hover:bg-ink hover:text-bone"
        >
          {t("refresh")}
        </button>
      </div>
      <BoardContent board={board} />
      <div className="mt-16 border-graphite/25 border-t pt-5">
        <Link
          href="/"
          className="font-ui text-ink text-sm underline underline-offset-4"
        >
          ← {t("back")}
        </Link>
      </div>
    </div>
  );
}
