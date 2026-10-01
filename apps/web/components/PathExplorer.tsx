"use client";

import { useLocale, useTranslations } from "next-intl";
import { useEffect, useState } from "react";

type Skill = {
  id: string;
  label_en: string;
  label_te: string;
  label_hi: string;
};
type Role = {
  id: string;
  label_en: string;
  label_te: string;
  label_hi: string;
  required_skills: Record<string, number>;
};
type Step = Skill & {
  skill: string;
  hours: number;
  demand: number;
  why: string[];
  source: string;
};
type Path = { goal: string; steps: Step[]; total_hours: number; weeks: number };
type Change = {
  before: Path;
  after: Path;
  diff: {
    removed: string[];
    added: string[];
    reordered: string[];
    hours_delta: number;
    cause: string;
  };
  profile_vector?: {
    cosine_shift: number | null;
    before_version: string | null;
    after_version: string | null;
  };
  held_after?: Record<string, number>;
  demand_after?: Record<string, number>;
};
type Item = {
  id: string;
  text: string;
  source: string;
  display_language: "en" | "te" | "hi";
};
type AssessState = { theta: number; se: number; answered: [string, boolean][] };

async function api<T>(endpoint: string, body?: object): Promise<T> {
  const response = await fetch(`/api/engine/${endpoint}`, {
    method: body ? "POST" : "GET",
    headers: { "Content-Type": "application/json" },
    body: body ? JSON.stringify(body) : undefined,
  });
  const data = await response
    .json()
    .catch(() => ({ detail: "Engine request failed" }));
  if (!response.ok) throw new Error(data.detail ?? "Engine request failed");
  return data as T;
}

async function persistProfile(held: Record<string, number>) {
  localStorage.setItem("daari-held", JSON.stringify(held));
  const key = "daari-p2-profile-id";
  let profileId = localStorage.getItem(key);
  if (!profileId) {
    profileId = crypto.randomUUID();
    localStorage.setItem(key, profileId);
  }
  await api("profile", { profile_id: profileId, held });
}

function savedNumbers(key: string, levels = false): Record<string, number> {
  try {
    const value: unknown = JSON.parse(localStorage.getItem(key) ?? "{}");
    if (!value || typeof value !== "object" || Array.isArray(value)) return {};
    return Object.fromEntries(
      Object.entries(value).filter(
        ([, n]) =>
          typeof n === "number" &&
          Number.isFinite(n) &&
          (levels ? Number.isInteger(n) && n >= 1 && n <= 5 : n >= 0),
      ),
    );
  } catch {
    return {};
  }
}

export function PathExplorer() {
  const t = useTranslations("path");
  const locale = useLocale();
  const [skills, setSkills] = useState<Skill[]>([]);
  const [roles, setRoles] = useState<Role[]>([]);
  const [goal, setGoal] = useState("data_analyst");
  const [persona, setPersona] = useState<"student" | "rural">("student");
  const [held, setHeld] = useState<Record<string, number>>({});
  const [demand, setDemand] = useState<Record<string, number>>({});
  const [selected, setSelected] = useState("sql_querying");
  const [level, setLevel] = useState(4);
  const [path, setPath] = useState<Path | null>(null);
  const [change, setChange] = useState<Change | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [assessment, setAssessment] = useState<AssessState | null>(null);
  const [item, setItem] = useState<Item | null>(null);
  const [answer, setAnswer] = useState("");
  const [result, setResult] = useState("");

  useEffect(() => {
    try {
      setHeld(savedNumbers("daari-held", true));
      const savedGoal = localStorage.getItem("daari-goal");
      if (savedGoal) setGoal(savedGoal);
      setDemand(savedNumbers("daari-demand"));
    } catch {
      localStorage.removeItem("daari-held");
      localStorage.removeItem("daari-demand");
    }
  }, []);
  useEffect(() => {
    api<{ skills: Skill[]; roles: Role[] }>("catalog")
      .then((data) => {
        setSkills(data.skills);
        setRoles(data.roles);
        setGoal((current) =>
          data.roles.some((role) => role.id === current)
            ? current
            : (data.roles[0]?.id ?? "data_analyst"),
        );
      })
      .catch((err) => setError(String(err)));
  }, []);
  useEffect(() => {
    if (!roles.length) return;
    let active = true;
    setBusy(true);
    setPath(null);
    api<Path>("roadmap", { goal, held, demand, persona })
      .then((data) => {
        if (!active) return;
        setPath(data);
        setError("");
      })
      .catch(() => {
        if (active) setError(t("unavailable"));
      })
      .finally(() => {
        if (active) setBusy(false);
      });
    return () => {
      active = false;
    };
  }, [goal, persona, roles.length, held, demand, t]);

  const label = (entry: Skill | Role) =>
    locale === "te"
      ? entry.label_te
      : locale === "hi"
        ? entry.label_hi
        : entry.label_en;
  const skillName = (id: string) => {
    const found = skills.find((s) => s.id === id);
    return found ? label(found) : id;
  };
  const selectedOnPath =
    path?.steps.some((step) => step.skill === selected) ?? false;
  const base = { goal, held, demand, persona };

  async function run(endpoint: "simulate-skill-update" | "market-shock") {
    setBusy(true);
    setError("");
    try {
      const update =
        endpoint === "simulate-skill-update"
          ? { ...base, skill: selected, level }
          : {
              ...base,
              skill: selected,
              added_listings: 50,
              total_listings: 100,
            };
      const data = await api<Change>(endpoint, update);
      setChange(data);
      setPath(data.after);
      if (data.held_after) setHeld(data.held_after);
      if (data.demand_after) {
        setDemand(data.demand_after);
        localStorage.setItem("daari-demand", JSON.stringify(data.demand_after));
      }
      if (data.held_after) await persistProfile(data.held_after);
    } catch (err) {
      setError(String(err));
    } finally {
      setBusy(false);
    }
  }

  async function startAssessment() {
    setBusy(true);
    try {
      const data = await api<{ state: AssessState; item: Item | null }>(
        "assess/next",
        { skill: selected, locale },
      );
      setAssessment(data.state);
      setItem(data.item);
      setResult(data.item ? "" : t("noAssessment"));
      setError("");
    } catch (err) {
      setError(String(err));
    } finally {
      setBusy(false);
    }
  }

  async function submitAnswer() {
    if (!assessment || !item) return;
    setBusy(true);
    try {
      const data = await api<{
        state: AssessState;
        correct: boolean;
        done: boolean;
        level: number;
        se: number;
        rationale: string;
        expected_answer: string;
      }>("assess/answer", {
        skill: selected,
        locale,
        ...assessment,
        item_id: item.id,
        answer,
      });
      setAssessment(data.state);
      setResult(
        `${data.correct ? t("correct") : t("incorrect")} · ${t("expected")}: ${data.expected_answer} · ${t("level")} ${data.level} · ${t("errorBar")} ±${data.se.toFixed(2)}. ${data.rationale}`,
      );
      setAnswer("");
      if (data.done) {
        setItem(null);
        const update = await api<Change>("simulate-skill-update", {
          ...base,
          skill: selected,
          level: data.level,
          se: data.se,
        });
        setChange(update);
        setPath(update.after);
        if (update.held_after) {
          setHeld(update.held_after);
          await persistProfile(update.held_after);
        }
      } else {
        const next = await api<{ item: Item | null }>("assess/next", {
          skill: selected,
          locale,
          ...data.state,
        });
        setItem(next.item);
      }
    } catch (err) {
      setError(String(err));
    } finally {
      setBusy(false);
    }
  }

  function PathCard({ title, value }: { title: string; value: Path }) {
    return (
      <section className="rounded-xl border border-graphite/25 bg-background p-5">
        <h2 className="font-mono text-sm uppercase tracking-wider text-signal">
          {title}
        </h2>
        <p className="mt-2 text-2xl font-semibold">
          {value.total_hours} {t("hours")} · {value.weeks} {t("weeks")}
        </p>
        <ol className="mt-6 ml-3 border-graphite/30 border-l">
          {value.steps.map((step, index) => (
            <li key={step.skill} className="relative pb-6 pl-6 last:pb-0">
              <span
                aria-hidden="true"
                className="absolute rounded-full border-2 border-background bg-sage"
                style={{
                  width: `${Math.round(12 * step.demand)}px`,
                  height: `${Math.round(12 * step.demand)}px`,
                  left: `${-Math.round(6 * step.demand)}px`,
                  top: "2px",
                }}
              />
              <div className="flex justify-between gap-3">
                <span>
                  <span className="mr-3 font-mono text-graphite">
                    {String(index + 1).padStart(2, "0")}
                  </span>
                  {label(step)}
                </span>
                <span className="shrink-0 font-mono text-sm">
                  {step.hours}h
                </span>
              </div>
              <p className="mt-1 pl-8 text-graphite text-sm">
                {(roles.find((role) => role.id === goal)?.required_skills[
                  step.skill
                ]
                  ? t("required")
                  : t("prerequisite")) +
                  (step.demand > 1
                    ? ` · ${t("demandWeight")} ${step.demand.toFixed(2)}×`
                    : "")}
              </p>
            </li>
          ))}
        </ol>
      </section>
    );
  }

  return (
    <main className="mx-auto w-full max-w-7xl px-6 py-10 sm:px-12">
      <p className="font-mono text-signal text-sm uppercase tracking-widest">
        DAARI / P2
      </p>
      <h1 className="mt-3 font-display text-5xl sm:text-7xl">{t("title")}</h1>
      <p className="mt-3 max-w-2xl text-graphite">{t("intro")}</p>
      <div className="mt-8 grid gap-4 rounded-xl border border-graphite/25 p-5 sm:grid-cols-4">
        <label className="flex flex-col gap-2 text-sm">
          {t("persona")}
          <select
            disabled={busy}
            className="rounded border border-graphite/30 bg-background p-2"
            value={persona}
            onChange={(event) => {
              setChange(null);
              setPersona(event.target.value as "student" | "rural");
            }}
          >
            <option value="student">{t("student")}</option>
            <option value="rural">{t("rural")}</option>
          </select>
        </label>
        <label className="flex flex-col gap-2 text-sm">
          {t("goal")}
          <select
            disabled={busy || !roles.length}
            className="rounded border border-graphite/30 bg-background p-2"
            value={goal}
            onChange={(event) => {
              setChange(null);
              setGoal(event.target.value);
              localStorage.setItem("daari-goal", event.target.value);
            }}
          >
            {roles.map((r) => (
              <option key={r.id} value={r.id}>
                {label(r)}
              </option>
            ))}
          </select>
        </label>
        <label className="flex flex-col gap-2 text-sm">
          {t("skill")}
          <select
            disabled={busy || !skills.length}
            className="rounded border border-graphite/30 bg-background p-2"
            value={selected}
            onChange={(event) => {
              setSelected(event.target.value);
              setItem(null);
              setAssessment(null);
            }}
          >
            {skills.map((s) => (
              <option key={s.id} value={s.id}>
                {label(s)}
              </option>
            ))}
          </select>
        </label>
        <label className="flex flex-col gap-2 text-sm">
          {t("level")}
          <select
            className="rounded border border-graphite/30 bg-background p-2"
            value={level}
            onChange={(event) => setLevel(Number(event.target.value))}
          >
            {[1, 2, 3, 4, 5].map((v) => (
              <option key={v} value={v}>
                {v}
              </option>
            ))}
          </select>
        </label>
        <div className="flex flex-wrap gap-3 sm:col-span-4">
          <button
            type="button"
            disabled={busy || !path}
            className="rounded bg-signal px-4 py-2 font-medium text-white disabled:opacity-50"
            onClick={() => run("simulate-skill-update")}
          >
            {t("simulate")}
          </button>
          <button
            type="button"
            disabled={busy || !path || !selectedOnPath}
            className="rounded border border-graphite/40 px-4 py-2 disabled:opacity-50"
            onClick={() => run("market-shock")}
          >
            {t("shock")}
          </button>
          <button
            type="button"
            disabled={busy || !skills.length}
            className="rounded border border-graphite/40 px-4 py-2 disabled:opacity-50"
            onClick={startAssessment}
          >
            {t("assess")}
          </button>
          {path && !selectedOnPath && (
            <p className="basis-full text-graphite text-sm" role="note">
              {t("shockPickOnPath")}
            </p>
          )}
        </div>
      </div>
      {error && (
        <p role="alert" className="mt-5 text-signal">
          {error}
        </p>
      )}
      {busy && (
        <p className="mt-5" role="status">
          {t("loading")}
        </p>
      )}
      {item && (
        <section className="mt-6 rounded-xl border border-graphite/25 p-5">
          <h2 className="font-semibold">
            {t("question")} {(assessment?.answered.length ?? 0) + 1} / 6
          </h2>
          {item.display_language !== locale && (
            <p className="mt-2 text-amber-800 text-sm" role="note">
              {t("englishQuestion")}
            </p>
          )}
          <p data-testid="assessment-question-text" className="mt-3">
            {item.text}
          </p>
          <p className="mt-2 text-graphite text-xs">{item.source}</p>
          <div className="mt-4 flex gap-2">
            <input
              aria-label={t("answer")}
              value={answer}
              onChange={(e) => setAnswer(e.target.value)}
              className="min-w-0 flex-1 rounded border border-graphite/30 bg-background p-2"
            />
            <button
              type="button"
              disabled={busy || !answer.trim()}
              onClick={submitAnswer}
              className="rounded bg-ink px-4 py-2 text-bone disabled:opacity-50"
            >
              {t("submit")}
            </button>
          </div>
        </section>
      )}
      {result && (
        <p role="status" className="mt-4">
          {result}
        </p>
      )}
      {change && (
        <section className="mt-6 rounded-xl border border-sage/50 bg-sage/10 p-5">
          <h2 className="font-semibold">{t("change")}</h2>
          <p className="mt-2">
            {t("removed")}:{" "}
            {change.diff.removed.map(skillName).join(", ") || t("none")} ·{" "}
            {t("reordered")}:{" "}
            {change.diff.reordered.map(skillName).join(", ") || t("none")}
          </p>
          <p>
            {t("hoursDelta")}: {change.diff.hours_delta > 0 ? "+" : ""}
            {change.diff.hours_delta}h
            {change.profile_vector?.cosine_shift != null
              ? ` · ${t("cosineShift")}: ${change.profile_vector.cosine_shift > 0 ? "+" : ""}${change.profile_vector.cosine_shift}`
              : ""}
          </p>
        </section>
      )}
      <div className="mt-6 grid gap-5 lg:grid-cols-2">
        {change && <PathCard title={t("before")} value={change.before} />}
        {path && (
          <PathCard title={change ? t("after") : t("current")} value={path} />
        )}
      </div>
    </main>
  );
}
