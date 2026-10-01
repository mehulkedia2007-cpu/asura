"use client";

import { useLocale, useTranslations } from "next-intl";
import { useEffect, useRef, useState } from "react";
import { Link } from "@/i18n/navigation";

async function api<T>(endpoint: string, body?: object): Promise<T> {
  const response = await fetch(`/api/engine/${endpoint}`, {
    method: body ? "POST" : "GET",
    headers: { "Content-Type": "application/json" },
    body: body ? JSON.stringify(body) : undefined,
  });
  if (!response.ok) throw new Error("request_failed");
  return response.json() as Promise<T>;
}
type Labels = { label_en: string; label_te: string; label_hi: string };
type Company = { id: string; name: string; roles: string[] };
type Question = {
  id: string;
  text: string;
  text_te?: string | null;
  text_hi?: string | null;
  kind: "reported" | "practice" | "jd_practice";
  source_url?: string;
  fetched_at?: string;
  as_of?: string;
  year?: number;
  round: string;
  topic?: string;
  source_span?: string;
  coverage?: string;
};
type Coverage = {
  coverage: "none" | "thin" | "available";
  items: number;
  sources: number;
  year_min: number | null;
  year_max: number | null;
};
type Results = {
  questions: Question[];
  stats: Coverage;
  nearest_roles: string[];
  refresh?: { errors: object[] };
};
type Fields = Record<
  string,
  {
    value: string | string[] | null;
    source_span: string | null;
    status: string;
  }
>;
type Pack = {
  company: string;
  role: string;
  goal: string;
  coverage: Coverage;
  plan: {
    feasible: boolean;
    required_hours: number;
    shortfall_hours: number;
    capacity_hours: number;
    days: {
      date: string;
      allocations: (Labels & { skill: string; hours: number })[];
    }[];
  };
  questions_by_round: Record<string, Question[]>;
  trace: { tool: string }[];
  mock_seed: object;
};
type Attempt = {
  question_id: string;
  transcript: string;
  feedback: { code: string; point: string; quote: string; fix: string }[];
  followup: string | null;
  metrics: {
    word_count: number;
    star_coverage: number;
    filler_rate: number;
    wpm: number | null;
    duration_seconds: number | null;
  };
};
type Session = {
  id: string;
  questions: Question[];
  attempts: Attempt[];
  current: number;
  coverage: Coverage;
  jd_status: string;
  locale: string;
};
const fieldNames = [
  "company",
  "role",
  "interview_date",
  "ctc",
  "eligibility",
  "rounds",
  "mode",
];
const inputStyle =
  "w-full rounded-none border border-graphite/40 bg-bone px-3 py-3 text-ink focus:outline-2 focus:outline-signal";
const buttonStyle =
  "border border-ink bg-ink px-5 py-3 text-bone disabled:opacity-50";

export function PrepNav() {
  const t = useTranslations("p5");
  const live = useTranslations("live");
  const voice = useTranslations("voice");
  const evidence = useTranslations("p6");
  const links = [
    ["home", t("home")],
    ["path", t("path")],
    ["leads", live("leadsTitle")],
    ["schemes", live("schemesTitle")],
    ["questions", t("questions")],
    ["prep", t("prep")],
    ["interview", t("interview")],
    ["voice", voice("open")],
    ["evidence", evidence("title")],
  ] as const;
  return (
    <nav
      aria-label={t("prep")}
      className="flex flex-wrap gap-x-6 gap-y-3 border-graphite/20 border-b px-6 py-4 text-sm print:hidden"
    >
      {links.map(([key, label]) => (
        <Link
          key={key}
          href={key === "home" ? "/" : `/${key}`}
          className="underline underline-offset-4"
        >
          {label}
        </Link>
      ))}
    </nav>
  );
}
function CoveragePanel({ coverage }: { coverage: Coverage }) {
  const t = useTranslations("p5");
  return (
    <aside
      className={`border-l-4 ${coverage.coverage === "available" ? "border-sage" : "border-amber"} bg-graphite/5 p-5`}
    >
      <p>{t(coverage.coverage)}</p>
      <dl className="mt-4 flex flex-wrap gap-6">
        {[
          ["items", coverage.items],
          ["sources", coverage.sources],
          [
            "yearSpan",
            coverage.year_min
              ? `${coverage.year_min}–${coverage.year_max}`
              : "—",
          ],
        ].map(([key, value]) => (
          <div key={key}>
            <dt className="text-graphite text-xs">{t(String(key))}</dt>
            <dd className="font-mono text-xl">{value}</dd>
          </div>
        ))}
      </dl>
    </aside>
  );
}
function QuestionCard({ question }: { question: Question }) {
  const locale = useLocale();
  const t = useTranslations("p5");
  return (
    <article className="min-w-0 border border-graphite/25 p-5">
      <p className="text-graphite text-xs">
        {t(question.kind)} ·{" "}
        {t.has(question.round) ? t(question.round) : question.round}
      </p>
      <p className="mt-3 text-xl leading-relaxed">
        {(locale === "te"
          ? question.text_te
          : locale === "hi"
            ? question.text_hi
            : null) || question.text}
      </p>
      {question.source_span && (
        <blockquote className="mt-3 border-graphite/30 border-l pl-3 text-graphite text-sm">
          {question.source_span}
        </blockquote>
      )}
      {question.source_url && (
        <a
          className="mt-4 inline-block text-signal underline"
          href={question.source_url}
          target="_blank"
          rel="noreferrer"
        >
          {t("source")}
        </a>
      )}
      <p className="mt-2 break-words font-mono text-xs">
        {question.as_of && `${t("asOf")}: ${question.as_of} · `}
        {question.fetched_at &&
          `${t("fetched")}: ${question.fetched_at.slice(0, 10)}`}
      </p>
      {question.coverage === "thin" && (
        <p className="mt-2 text-sm">{t("thin")}</p>
      )}
    </article>
  );
}
function Highlight({ text, quotes }: { text: string; quotes: string[] }) {
  const spans = quotes
    .map((quote) => ({
      start: text.indexOf(quote),
      end: text.indexOf(quote) + quote.length,
    }))
    .filter((span) => span.start >= 0)
    .sort((a, b) => a.start - b.start);
  const pieces: React.ReactNode[] = [];
  let cursor = 0;
  for (const span of spans) {
    if (span.start < cursor) continue;
    pieces.push(text.slice(cursor, span.start));
    pieces.push(
      <mark className="bg-amber/30 text-ink" key={`${span.start}:${span.end}`}>
        {text.slice(span.start, span.end)}
      </mark>,
    );
    cursor = span.end;
  }
  pieces.push(text.slice(cursor));
  return <p className="whitespace-pre-wrap leading-relaxed">{pieces}</p>;
}

export function Preparation({
  screen,
}: {
  screen: "questions" | "prep" | "interview";
}) {
  const t = useTranslations("p5");
  const locale = useLocale();
  const [companies, setCompanies] = useState<Company[]>([]);
  const [roles, setRoles] = useState<(Labels & { id: string })[]>([]);
  const [company, setCompany] = useState("tcs");
  const [role, setRole] = useState("Prime");
  const [goal, setGoal] = useState("data_analyst");
  const [query, setQuery] = useState("");
  const [year, setYear] = useState("");
  const [round, setRound] = useState("");
  const [results, setResults] = useState<Results | null>(null);
  const [rawNotice, setRawNotice] = useState("");
  const [fields, setFields] = useState<Fields | null>(null);
  const [confirmed, setConfirmed] = useState(false);
  const [hours, setHours] = useState(2);
  const [pack, setPack] = useState<Pack | null>(null);
  const [session, setSession] = useState<Session | null>(null);
  const [answer, setAnswer] = useState("");
  const [jobQuery, setJobQuery] = useState("");
  const [duration, setDuration] = useState<number | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [recording, setRecording] = useState(false);
  const [micPending, setMicPending] = useState(false);
  const recorder = useRef<MediaRecorder | null>(null);
  const stream = useRef<MediaStream | null>(null);
  const generation = useRef(0);
  const started = useRef(0);
  const recognition = useRef<{ stop(): void } | null>(null);
  useEffect(() => {
    let alive = true;
    Promise.all([
      api<{ companies: Company[] }>("questions/companies"),
      api<{ roles: (Labels & { id: string })[] }>("catalog"),
    ])
      .then(([a, b]) => {
        if (alive) {
          setCompanies(a.companies);
          setRoles(b.roles);
        }
      })
      .catch(() => {
        if (alive) setError("error");
      });
    if (screen === "interview") {
      const saved = sessionStorage.getItem(`daari-interview-${locale}`);
      if (saved)
        api<Session>("interview/history", { session_id: saved })
          .then((row) => {
            if (alive) setSession(row);
          })
          .catch(() => sessionStorage.removeItem(`daari-interview-${locale}`));
      const seed = sessionStorage.getItem("daari-prep-seed");
      if (seed) {
        try {
          const value = JSON.parse(seed);
          setCompany(value.company);
          setRole(value.role);
          setGoal(value.goal);
        } catch {
          sessionStorage.removeItem("daari-prep-seed");
        }
      }
    }
    return () => {
      alive = false;
      generation.current++;
      if (recorder.current?.state === "recording") recorder.current.stop();
      stream.current?.getTracks().forEach((track) => {
        track.stop();
      });
      recognition.current?.stop();
    };
  }, [screen, locale]);
  const label = (value: Labels) =>
    locale === "te"
      ? value.label_te
      : locale === "hi"
        ? value.label_hi
        : value.label_en;
  const held = (): Record<string, number> => {
    try {
      return JSON.parse(localStorage.getItem("daari-held") ?? "{}");
    } catch {
      return {};
    }
  };
  const task = async (action: () => Promise<void>) => {
    setBusy(true);
    setError("");
    try {
      await action();
    } catch {
      setError("error");
    } finally {
      setBusy(false);
    }
  };
  const saveSession = (value: Session) => {
    setSession(value);
    sessionStorage.setItem(`daari-interview-${locale}`, value.id);
  };
  async function toggleRecord() {
    if (micPending) {
      generation.current++;
      setMicPending(false);
      return;
    }
    if (recorder.current?.state === "recording") {
      recorder.current.stop();
      recognition.current?.stop();
      return;
    }
    const version = ++generation.current;
    setMicPending(true);
    let timeout: ReturnType<typeof setTimeout> | undefined;
    setError("");
    try {
      const capture = navigator.mediaDevices.getUserMedia({ audio: true });
      void capture.then(
        (media) => {
          if (version !== generation.current)
            media.getTracks().forEach((track) => {
              track.stop();
            });
        },
        () => {},
      );
      const media = await Promise.race([
        capture,
        new Promise<MediaStream>((_, reject) => {
          timeout = setTimeout(
            () => reject(new Error("microphone_timeout")),
            20000,
          );
        }),
      ]);
      clearTimeout(timeout);
      if (version !== generation.current) {
        media.getTracks().forEach((track) => {
          track.stop();
        });
        return;
      }
      setMicPending(false);
      stream.current = media;
      const chunks: Blob[] = [];
      const device = new MediaRecorder(media);
      recorder.current = device;
      started.current = performance.now();
      setAnswer("");
      setDuration(null);
      setRecording(true);
      type Recognition = {
        lang: string;
        continuous: boolean;
        interimResults: boolean;
        onresult: (event: {
          results: ArrayLike<ArrayLike<{ transcript: string }>>;
        }) => void;
        onerror: () => void;
        start(): void;
        stop(): void;
      };
      const browser = window as typeof window & {
        SpeechRecognition?: new () => Recognition;
        webkitSpeechRecognition?: new () => Recognition;
      };
      const Recognizer =
        browser.SpeechRecognition ?? browser.webkitSpeechRecognition;
      let final = "";
      if (Recognizer) {
        const instance = new Recognizer();
        recognition.current = instance;
        instance.lang = `${locale}-IN`;
        instance.continuous = true;
        instance.interimResults = true;
        instance.onresult = (event) => {
          final = Array.from(event.results)
            .map((row) => row[0].transcript)
            .join(" ");
          if (version === generation.current) setAnswer(final);
        };
        instance.onerror = () => {};
        try {
          instance.start();
        } catch {
          recognition.current = null;
        }
      }
      device.ondataavailable = (event) => chunks.push(event.data);
      device.onstop = () => {
        media.getTracks().forEach((track) => {
          track.stop();
        });
        if (version !== generation.current) return;
        setRecording(false);
        setDuration(
          Math.max(0.1, (performance.now() - started.current) / 1000),
        );
        const blob = new Blob(chunks, { type: device.mimeType });
        const reader = new FileReader();
        reader.onload = () => {
          if (version !== generation.current) return;
          void task(async () => {
            const result = await api<{ transcript: string }>(
              "interview/transcribe",
              {
                audio: String(reader.result).split(",")[1],
                mime: device.mimeType.includes("mp4")
                  ? "audio/mp4"
                  : "audio/webm",
                locale,
                browser_final: final,
              },
            );
            if (version === generation.current) setAnswer(result.transcript);
          });
        };
        reader.readAsDataURL(blob);
      };
      device.start();
    } catch {
      clearTimeout(timeout);
      if (version !== generation.current) return;
      generation.current++;
      setMicPending(false);
      recognition.current?.stop();
      stream.current?.getTracks().forEach((track) => {
        track.stop();
      });
      setRecording(false);
      setError("micError");
    }
  }
  const selector = (
    <div className="grid gap-4 md:grid-cols-3">
      <label className="grid gap-2 text-sm">
        {t("company")}
        <select
          className={inputStyle}
          value={company}
          onChange={(event) => {
            setCompany(event.target.value);
            setRole(
              companies.find((c) => c.id === event.target.value)?.roles[0] ??
                "",
            );
            setResults(null);
          }}
        >
          {companies.map((c) => (
            <option key={c.id} value={c.id}>
              {c.name}
            </option>
          ))}
        </select>
      </label>
      <label className="grid gap-2 text-sm">
        {t("role")}
        <input
          className={inputStyle}
          value={role}
          onChange={(event) => {
            setRole(event.target.value);
            setResults(null);
          }}
        />
      </label>
      <label className="grid gap-2 text-sm">
        {t("goal")}
        <select
          className={inputStyle}
          value={goal}
          onChange={(event) => setGoal(event.target.value)}
        >
          {roles.map((r) => (
            <option key={r.id} value={r.id}>
              {label(r)}
            </option>
          ))}
        </select>
      </label>
    </div>
  );
  const current = session?.questions[session.current];
  return (
    <main
      className={`mx-auto w-full max-w-6xl px-6 py-10 ${locale === "te" ? "font-telugu-sans" : locale === "hi" ? "font-devanagari-sans" : "font-ui"}`}
    >
      <p className="font-mono text-signal text-xs tracking-widest">
        {t("eyebrow")}
      </p>
      <h1
        className={`mt-4 mb-5 text-4xl leading-tight md:text-6xl ${locale === "en" ? "font-display" : ""}`}
      >
        {t(screen)}
      </h1>
      <p className="mb-8 max-w-2xl text-graphite leading-relaxed">
        {t("intro")}
      </p>
      {error && (
        <p role="alert" className="my-4 border-signal border-l-4 p-3">
          {t(error)}
        </p>
      )}
      {busy && (
        <p role="status" className="my-4 font-mono text-sm">
          {t("busy")}
        </p>
      )}
      {screen === "questions" && (
        <section className="space-y-6">
          {selector}
          <p className="text-graphite text-xs">{t("generalSeed")}</p>
          <label className="grid gap-2 text-sm">
            {t("query")}
            <input
              className={inputStyle}
              value={query}
              onChange={(event) => setQuery(event.target.value)}
            />
          </label>
          <div className="grid gap-4 md:grid-cols-2">
            <label className="grid gap-2 text-sm">
              {t("rounds")}
              <select
                className={inputStyle}
                value={round}
                onChange={(e) => setRound(e.target.value)}
              >
                <option value="">—</option>
                {["technical", "managerial", "hr"].map((key) => (
                  <option key={key} value={key}>
                    {t(key)}
                  </option>
                ))}
              </select>
            </label>
            <label className="grid gap-2 text-sm">
              {t("yearSpan")}
              <input
                type="number"
                min="2000"
                max="2100"
                className={inputStyle}
                value={year}
                onChange={(e) => setYear(e.target.value)}
              />
            </label>
          </div>
          <div className="flex flex-wrap gap-3">
            {["search", "refresh"].map((action) => (
              <button
                key={action}
                type="button"
                disabled={busy || !companies.length || !role.trim()}
                className={buttonStyle}
                onClick={() =>
                  void task(async () =>
                    setResults(
                      await api<Results>(`questions/${action}`, {
                        company,
                        role,
                        query,
                        year: year ? Number(year) : null,
                        round,
                      }),
                    ),
                  )
                }
              >
                {t(action)}
              </button>
            ))}
          </div>
          {results && (
            <>
              <CoveragePanel coverage={results.stats} />
              {results.refresh?.errors.length ? (
                <p role="status">{t("sourceErrors")}</p>
              ) : null}
              {!results.questions.length && <p>{t("noMatches")}</p>}
              {results.nearest_roles.length > 0 && (
                <p>
                  {t("nearest")}: {results.nearest_roles.join(", ")}
                </p>
              )}
              <div className="grid gap-4 md:grid-cols-2">
                {results.questions.map((q) => (
                  <QuestionCard key={q.id} question={q} />
                ))}
              </div>
            </>
          )}
        </section>
      )}
      {screen === "prep" && (
        <section className="space-y-6">
          <label className="grid gap-3">
            {t("notice")}
            <textarea
              rows={7}
              className={inputStyle}
              value={rawNotice}
              onChange={(event) => {
                setRawNotice(event.target.value);
                setFields(null);
                setConfirmed(false);
                setPack(null);
              }}
            />
          </label>
          <p className="text-graphite text-sm">{t("noticeHelp")}</p>
          <button
            className={buttonStyle}
            type="button"
            disabled={busy || !rawNotice.trim()}
            onClick={() =>
              void task(async () => {
                const result = await api<{ fields: Fields }>("prep/notice", {
                  text: rawNotice,
                });
                setFields(result.fields);
                setConfirmed(false);
                setRawNotice("");
              })
            }
          >
            {t("extract")}
          </button>
          {fields && (
            <div className="space-y-5 border-graphite/20 border-t pt-6">
              <h2 className="text-2xl">{t("review")}</h2>
              <div className="grid gap-5 md:grid-cols-2">
                {fieldNames.map((key) => (
                  <label key={key} className="grid gap-2 text-sm">
                    {t(key)}
                    <input
                      type={key === "interview_date" ? "date" : "text"}
                      className={inputStyle}
                      value={
                        Array.isArray(fields[key].value)
                          ? fields[key].value.join(", ")
                          : (fields[key].value ?? "")
                      }
                      onChange={(event) => {
                        setFields({
                          ...fields,
                          [key]: { ...fields[key], value: event.target.value },
                        });
                        setConfirmed(false);
                        setPack(null);
                      }}
                    />
                    <span className="text-graphite text-xs">
                      {fields[key].source_span ?? t("missing")}
                    </span>
                  </label>
                ))}
              </div>
              <label className="grid gap-2">
                {t("goal")}
                <select
                  className={inputStyle}
                  value={goal}
                  onChange={(e) => {
                    setGoal(e.target.value);
                    setPack(null);
                  }}
                >
                  {roles.map((r) => (
                    <option key={r.id} value={r.id}>
                      {label(r)}
                    </option>
                  ))}
                </select>
              </label>
              <label className="grid gap-2">
                {t("hours")}
                <input
                  className={inputStyle}
                  type="number"
                  min={0.25}
                  max={16}
                  step={0.25}
                  value={hours}
                  onChange={(event) => {
                    setHours(Number(event.target.value));
                    setPack(null);
                  }}
                />
              </label>
              <p className="text-sm">{t("heldNotice")}</p>
              <label className="flex items-start gap-3">
                <input
                  type="checkbox"
                  className="mt-1 size-5 accent-signal"
                  checked={confirmed}
                  onChange={(event) => {
                    setConfirmed(event.target.checked);
                    setPack(null);
                  }}
                />
                {t("confirm")}
              </label>
              <button
                type="button"
                className={buttonStyle}
                disabled={
                  busy ||
                  !confirmed ||
                  !fields.company.value ||
                  !fields.role.value ||
                  !fields.interview_date.value
                }
                onClick={() =>
                  void task(async () => {
                    setPack(
                      await api<Pack>("prep/pack", {
                        confirmed,
                        company: fields.company.value,
                        role: fields.role.value,
                        interview_date: fields.interview_date.value,
                        goal,
                        held: held(),
                        hours_per_day: hours,
                        confirmed_fields: Object.fromEntries(
                          Object.entries(fields).map(([key, row]) => [
                            key,
                            row.value,
                          ]),
                        ),
                      }),
                    );
                  })
                }
              >
                {t("build")}
              </button>
            </div>
          )}
          {pack && (
            <div className="space-y-6">
              <CoveragePanel coverage={pack.coverage} />
              <p className="border-amber border-l-4 p-4">
                {t(pack.plan.feasible ? "feasible" : "shortfall")}
              </p>
              <dl className="grid grid-cols-3 gap-3">
                {[
                  ["requiredHours", pack.plan.required_hours],
                  ["capacityHours", pack.plan.capacity_hours],
                  ["shortfallHours", pack.plan.shortfall_hours],
                ].map(([key, value]) => (
                  <div key={key}>
                    <dt className="text-sm">{t(String(key))}</dt>
                    <dd className="mt-2 font-mono text-2xl">{value}</dd>
                  </div>
                ))}
              </dl>
              <div className="flex flex-wrap gap-4 print:hidden">
                <button
                  className={buttonStyle}
                  type="button"
                  onClick={() => window.print()}
                >
                  {t("print")}
                </button>
                <Link
                  className={buttonStyle}
                  href="/interview"
                  onClick={() =>
                    sessionStorage.setItem(
                      "daari-prep-seed",
                      JSON.stringify(pack.mock_seed),
                    )
                  }
                >
                  {t("mock")}
                </Link>
              </div>
              <h2 className="text-2xl">{t("schedule")}</h2>
              <ol className="grid gap-3 md:grid-cols-2">
                {pack.plan.days.map((day) => (
                  <li key={day.date} className="border border-graphite/25 p-4">
                    <p className="font-mono text-signal">{day.date}</p>
                    {day.allocations.map((row) => (
                      <p key={row.skill} className="mt-2">
                        {label(row)}{" "}
                        <span className="font-mono">· {row.hours} h</span>
                      </p>
                    ))}
                  </li>
                ))}
              </ol>
              <div className="grid gap-4 md:grid-cols-2">
                {Object.values(pack.questions_by_round)
                  .flat()
                  .map((q) => (
                    <QuestionCard key={q.id} question={q} />
                  ))}
              </div>
              <details>
                <summary>{t("trace")}</summary>
                <pre className="overflow-auto text-xs">
                  {JSON.stringify(pack.trace, null, 2)}
                </pre>
              </details>
            </div>
          )}
        </section>
      )}
      {screen === "interview" && (
        <section className="space-y-6">
          {!session && (
            <>
              {selector}
              <label className="grid gap-2 text-sm">
                {t("jobQuery")}
                <input
                  className={inputStyle}
                  value={jobQuery}
                  onChange={(e) => setJobQuery(e.target.value)}
                />
              </label>
              <button
                className={buttonStyle}
                disabled={busy}
                type="button"
                onClick={() =>
                  void task(async () =>
                    saveSession(
                      await api<Session>("interview/start", {
                        company,
                        role,
                        goal,
                        locale,
                        held: held(),
                        job_query: jobQuery || null,
                      }),
                    ),
                  )
                }
              >
                {t("start")}
              </button>
            </>
          )}
          {session && (
            <>
              <CoveragePanel coverage={session.coverage} />
              {session.jd_status !== "anchored" && (
                <p className="text-sm">{t("jdMissing")}</p>
              )}
              <p className="font-mono text-sm">
                {Math.min(session.current + 1, 5)} / 5
              </p>
              {current ? (
                <>
                  <QuestionCard question={current} />
                  <label className="grid gap-2">
                    {t("answer")}
                    <textarea
                      rows={7}
                      className={inputStyle}
                      value={answer}
                      disabled={busy || recording || micPending}
                      onChange={(e) => {
                        setAnswer(e.target.value);
                        setDuration(null);
                      }}
                    />
                  </label>
                  <p className="text-graphite text-sm">
                    {t("transcriptReview")}
                  </p>
                  <div className="flex flex-wrap gap-3">
                    <button
                      type="button"
                      className={buttonStyle}
                      disabled={busy}
                      onClick={() => void toggleRecord()}
                    >
                      {t(
                        micPending
                          ? "cancelMic"
                          : recording
                            ? "stop"
                            : "record",
                      )}
                    </button>
                    <button
                      className={buttonStyle}
                      type="button"
                      disabled={
                        busy || recording || micPending || !answer.trim()
                      }
                      onClick={() =>
                        void task(async () => {
                          saveSession(
                            await api<Session>("interview/answer", {
                              session_id: session.id,
                              question_id: current.id,
                              transcript: answer,
                              locale,
                              duration_seconds: duration,
                            }),
                          );
                          setAnswer("");
                          setDuration(null);
                        })
                      }
                    >
                      {t("submit")}
                    </button>
                  </div>
                </>
              ) : (
                <h2 className="text-2xl">{t("complete")}</h2>
              )}
              <button
                type="button"
                disabled={busy || recording || micPending}
                className="text-sm underline"
                onClick={() =>
                  void task(async () => {
                    await api("interview/delete", { session_id: session.id });
                    sessionStorage.removeItem(`daari-interview-${locale}`);
                    setSession(null);
                    setAnswer("");
                  })
                }
              >
                {t("delete")}
              </button>
              <h2 className="border-graphite/20 border-t pt-6 text-2xl">
                {t("history")}
              </h2>
              <p className="text-graphite text-sm">{t("metricsLimit")}</p>
              {session.attempts.map((attempt, i) => (
                <article
                  key={attempt.question_id}
                  className="space-y-5 border border-graphite/30 p-5"
                >
                  <h3 className="font-mono">{i + 1} / 5</h3>
                  <Highlight
                    text={attempt.transcript}
                    quotes={attempt.feedback.map((row) => row.quote)}
                  />
                  <dl className="grid grid-cols-2 gap-3 md:grid-cols-5">
                    {[
                      ["wordCount", attempt.metrics.word_count],
                      [
                        "starCoverage",
                        `${Math.round(attempt.metrics.star_coverage * 100)}%`,
                      ],
                      [
                        "fillerRate",
                        `${Math.round(attempt.metrics.filler_rate * 100)}%`,
                      ],
                      ["pace", attempt.metrics.wpm ?? "—"],
                      [
                        "duration",
                        attempt.metrics.duration_seconds?.toFixed(1) ?? "—",
                      ],
                    ].map(([key, value]) => (
                      <div key={key}>
                        <dt className="text-graphite text-xs">
                          {t(String(key))}
                        </dt>
                        <dd className="font-mono text-lg">{value}</dd>
                      </div>
                    ))}
                  </dl>
                  <h4>{t("feedback")}</h4>
                  <ul className="space-y-4">
                    {attempt.feedback.map((row) => (
                      <li
                        key={row.code}
                        className="border-signal border-l-2 pl-4"
                      >
                        <p>{row.point}</p>
                        <blockquote className="my-2 text-graphite text-sm">
                          “{row.quote}”
                        </blockquote>
                        <p className="text-sm">{row.fix}</p>
                      </li>
                    ))}
                  </ul>
                  {attempt.followup && (
                    <aside className="bg-graphite/5 p-4">
                      <p className="text-xs">{t("followup")}</p>
                      <p className="mt-2">{attempt.followup}</p>
                    </aside>
                  )}
                </article>
              ))}
            </>
          )}
        </section>
      )}
    </main>
  );
}
