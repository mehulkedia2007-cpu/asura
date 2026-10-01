"use client";

import { useLocale, useTranslations } from "next-intl";
import { useEffect, useId, useRef, useState } from "react";
import { Icon } from "@/components/Icon";
import { usePathname } from "@/i18n/navigation";

type Citation = { source_url: string; fetched_at: string };
type Verified = {
  sentences: { text: string; citation_ids: string[] }[];
  struck: { text: string; reason: string }[];
  no_data: boolean;
  message?: string;
  citations: Record<string, Citation>;
  newest_evidence_at?: string | null;
};
type AgentResult = {
  locale: string;
  provider: string;
  verification: Verified;
  cards: {
    title: string;
    summary?: string;
    source_url: string;
    fetched_at: string;
    distance_km?: number | null;
    eligibility?: { status: string } | null;
    scam?: { badge: string; reasons: string[] } | null;
  }[];
  trace: {
    tool: string;
    args: Record<string, unknown>;
    ms: number;
    provider: string;
    status: string;
  }[];
  next_question?: { field: string; query: string; text: string } | null;
  profile_update?: Record<string, string | number | boolean>;
  engine_result?: {
    kind: string;
    data: {
      steps?: {
        skill: string;
        label_en: string;
        label_te: string;
        label_hi: string;
        hours: number;
      }[];
      after?: {
        steps: {
          skill: string;
          label_en: string;
          label_te: string;
          label_hi: string;
          hours: number;
        }[];
      };
      score?: number;
      item?: { text: string } | null;
    };
  } | null;
};
type SpeechResult = { isFinal: boolean; 0: { transcript: string } };
type SpeechRecognitionLike = {
  lang: string;
  interimResults: boolean;
  continuous: boolean;
  onresult: ((event: { results: ArrayLike<SpeechResult> }) => void) | null;
  onerror: (() => void) | null;
  start: () => void;
  stop: () => void;
};
type SpeechWindow = Window & {
  SpeechRecognition?: new () => SpeechRecognitionLike;
  webkitSpeechRecognition?: new () => SpeechRecognitionLike;
};

async function websocketUrl(): Promise<string> {
  const response = await fetch("/api/connection", {
    cache: "no-store",
    signal: AbortSignal.timeout(20_000),
  });
  const data = await response.json();
  if (!response.ok || typeof data.websocketUrl !== "string")
    throw new Error("Engine unavailable");
  return data.websocketUrl;
}

export function VoicePanel({ large = false }: { large?: boolean }) {
  const locale = useLocale();
  const panelId = useId();
  const trigger = useRef<HTMLButtonElement | null>(null);
  const textInput = useRef<HTMLInputElement | null>(null);
  const panelRoot = useRef<HTMLDivElement | null>(null);
  const pathname = usePathname();
  const t = useTranslations("voice");
  const pathT = useTranslations("path");
  const [open, setOpen] = useState(large);
  const [recording, setRecording] = useState(false);
  const [busy, setBusy] = useState(false);
  const [interim, setInterim] = useState("");
  const [transcript, setTranscript] = useState("");
  const [typed, setTyped] = useState("");
  const [result, setResult] = useState<AgentResult | null>(null);
  const [pending, setPending] = useState<AgentResult["next_question"]>(null);
  const [error, setError] = useState("");
  const [stamps, setStamps] = useState<Record<string, number>>({});
  const [summary, setSummary] = useState<
    Record<string, { n: number; p50: number; p95: number }>
  >({});
  const socket = useRef<WebSocket | null>(null);
  const recorder = useRef<MediaRecorder | null>(null);
  const recognition = useRef<SpeechRecognitionLike | null>(null);
  const media = useRef<MediaStream | null>(null);
  const currentAudio = useRef<HTMLAudioElement | null>(null);
  const playback = useRef(Promise.resolve());
  const playbackVersion = useRef(0);
  const finishPlayback = useRef<(() => void) | null>(null);
  const finalSpeech = useRef("");
  const releaseAt = useRef(0);
  const audioStarted = useRef(false);
  const playbackSamples = useRef<number[]>([]);
  const cancelled = useRef(false);
  const turnVersion = useRef(0);
  const pendingRef = useRef<AgentResult["next_question"]>(null);
  const schemeProfile = useRef<Record<string, string | number | boolean>>({
    state: "Andhra Pradesh",
  });

  useEffect(() => {
    return () => {
      cancelled.current = true;
      turnVersion.current += 1;
      socket.current?.close();
      recognition.current?.stop();
      media.current?.getTracks().forEach((track) => {
        track.stop();
      });
      currentAudio.current?.pause();
      window.speechSynthesis?.cancel();
    };
  }, []);

  useEffect(() => {
    if (large || !open) return;
    textInput.current?.focus();
    const dismiss = (event: KeyboardEvent) => {
      if (event.key === "Escape") trigger.current?.click();
    };
    const outside = (event: PointerEvent) => {
      if (
        event.target instanceof Node &&
        !panelRoot.current?.contains(event.target)
      )
        trigger.current?.click();
    };
    document.addEventListener("keydown", dismiss);
    document.addEventListener("pointerdown", outside);
    return () => {
      document.removeEventListener("keydown", dismiss);
      document.removeEventListener("pointerdown", outside);
    };
  }, [large, open]);

  function closePanel() {
    cancel();
    stopPlayback();
    setOpen(false);
    trigger.current?.focus();
  }

  function stopPlayback() {
    playbackVersion.current += 1;
    currentAudio.current?.pause();
    currentAudio.current = null;
    window.speechSynthesis?.cancel();
    finishPlayback.current?.();
    finishPlayback.current = null;
    playback.current = Promise.resolve();
  }

  function markAudioStart() {
    if (audioStarted.current || !releaseAt.current) return;
    audioStarted.current = true;
    const elapsed = Math.round(performance.now() - releaseAt.current);
    playbackSamples.current = [...playbackSamples.current.slice(-199), elapsed];
    const values = [...playbackSamples.current].sort((a, b) => a - b);
    setSummary((old) => ({
      ...old,
      t_audio_start: {
        n: values.length,
        p50: values[Math.ceil(values.length * 0.5) - 1],
        p95: values[Math.ceil(values.length * 0.95) - 1],
      },
    }));
    setStamps((old) => ({
      ...old,
      t_audio_start: elapsed,
    }));
  }

  function cancel() {
    cancelled.current = true;
    turnVersion.current += 1;
    if (socket.current?.readyState === WebSocket.OPEN) {
      socket.current.send(JSON.stringify({ type: "cancel" }));
    }
    socket.current?.close();
    socket.current = null;
    if (recorder.current?.state === "recording") recorder.current.stop();
    recognition.current?.stop();
    media.current?.getTracks().forEach((track) => {
      track.stop();
    });
    stopPlayback();
    setRecording(false);
    setBusy(false);
  }

  async function playAudio(data: string, version: number) {
    if (version !== playbackVersion.current) return;
    const audio = new Audio(`data:audio/mpeg;base64,${data}`);
    currentAudio.current = audio;
    await new Promise<void>((resolve) => {
      finishPlayback.current = resolve;
      audio.onplay = markAudioStart;
      audio.onended = () => resolve();
      audio.onerror = () => resolve();
      audio.play().catch(() => resolve());
    });
  }

  async function browserSpeak(text: string, language: string, version: number) {
    if (version !== playbackVersion.current) return;
    if (!("speechSynthesis" in window)) return;
    const utterance = new SpeechSynthesisUtterance(text);
    utterance.lang = `${language}-IN`;
    await new Promise<void>((resolve) => {
      finishPlayback.current = resolve;
      utterance.onstart = markAudioStart;
      utterance.onend = () => resolve();
      utterance.onerror = () => resolve();
      window.speechSynthesis.speak(utterance);
    });
  }

  async function connect(): Promise<WebSocket> {
    if (socket.current?.readyState === WebSocket.OPEN) return socket.current;
    socket.current?.close();
    const ws = new WebSocket(await websocketUrl());
    socket.current = ws;
    ws.onmessage = (event) => {
      if (socket.current !== ws) return;
      const message = JSON.parse(event.data);
      if (message.type === "interim") setInterim(message.text);
      if (message.type === "transcript") {
        setTranscript(message.text);
        setInterim("");
      }
      if (message.type === "result") {
        const answer = message.result as AgentResult;
        setResult(answer);
        schemeProfile.current = {
          ...schemeProfile.current,
          ...answer.profile_update,
        };
        pendingRef.current = answer.next_question;
        setPending(answer.next_question);
      }
      if (message.type === "audio") {
        const version = playbackVersion.current;
        playback.current = playback.current.then(() =>
          playAudio(message.data, version),
        );
      }
      if (message.type === "browser_tts") {
        const version = playbackVersion.current;
        playback.current = playback.current.then(() =>
          browserSpeak(message.text, message.locale, version),
        );
      }
      if (message.type === "done") {
        setStamps((old) => ({ ...old, ...message.stamps_ms }));
        setSummary((old) => ({ ...old, ...message.summary_ms }));
        setBusy(false);
      }
      if (message.type === "error") {
        setError(
          t(
            message.detail === "no_transcript" ? "noTranscript" : "unavailable",
          ),
        );
        setBusy(false);
      }
    };
    ws.onclose = () => {
      if (socket.current === ws) {
        socket.current = null;
        setBusy(false);
      }
    };
    return await new Promise<WebSocket>((resolve, reject) => {
      const timeout = window.setTimeout(() => {
        ws.close();
        reject(new Error("socket_timeout"));
      }, 10_000);
      ws.onopen = () => {
        window.clearTimeout(timeout);
        resolve(ws);
      };
      ws.onerror = () => {
        window.clearTimeout(timeout);
        reject(new Error("socket"));
      };
      const onClose = ws.onclose;
      ws.onclose = (event) => {
        window.clearTimeout(timeout);
        onClose?.call(ws, event);
        reject(new Error("socket_closed"));
      };
    });
  }

  function request(text: string) {
    let held = {};
    try {
      held = JSON.parse(localStorage.getItem("daari-held") ?? "{}");
    } catch {
      held = {};
    }
    return {
      text: text || "voice input",
      locale,
      persona: large || pathname === "/voice" ? "rural" : "student",
      held,
      goal: localStorage.getItem("daari-goal") || "data_analyst",
      place: localStorage.getItem("daari-place") || "Guntur, Andhra Pradesh",
      profile: schemeProfile.current,
      pending_field: pendingRef.current?.field,
      pending_query: pendingRef.current?.query,
    };
  }

  function sendRelease(
    ws: WebSocket,
    audio: string,
    mime: string,
    browserFinal: string,
  ) {
    if (!releaseAt.current) releaseAt.current = performance.now();
    setStamps({});
    ws.send(
      JSON.stringify({
        type: "release",
        request: request(browserFinal),
        audio,
        mime,
        browser_final: browserFinal,
      }),
    );
    setBusy(true);
  }

  async function start() {
    if (recording) {
      releaseAt.current = performance.now();
      socket.current?.send(JSON.stringify({ type: "release_start" }));
      recorder.current?.stop();
      recognition.current?.stop();
      setRecording(false);
      return;
    }
    if (busy) cancel();
    stopPlayback();
    setResult(null);
    setError("");
    setInterim("");
    setTranscript("");
    releaseAt.current = 0;
    audioStarted.current = false;
    finalSpeech.current = "";
    cancelled.current = false;
    turnVersion.current += 1;
    const captureVersion = turnVersion.current;
    try {
      const ws = await connect();
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      if (cancelled.current || captureVersion !== turnVersion.current) {
        stream.getTracks().forEach((track) => {
          track.stop();
        });
        return;
      }
      media.current = stream;
      const mime = ["audio/webm;codecs=opus", "audio/mp4", "audio/webm"].find(
        (kind) => MediaRecorder.isTypeSupported(kind),
      );
      const capture = new MediaRecorder(
        stream,
        mime ? { mimeType: mime } : undefined,
      );
      recorder.current = capture;
      const chunks: Blob[] = [];
      capture.ondataavailable = (event) => {
        if (event.data.size) chunks.push(event.data);
      };
      capture.onstop = async () => {
        stream.getTracks().forEach((track) => {
          track.stop();
        });
        if (cancelled.current || captureVersion !== turnVersion.current) return;
        const blob = new Blob(chunks, { type: capture.mimeType });
        const data = await new Promise<string>((resolve) => {
          const reader = new FileReader();
          reader.onload = () =>
            resolve(String(reader.result).split(",")[1] ?? "");
          reader.readAsDataURL(blob);
        });
        if (cancelled.current || captureVersion !== turnVersion.current) return;
        sendRelease(ws, data, capture.mimeType, finalSpeech.current);
      };
      const speechWindow = window as SpeechWindow;
      const BrowserRecognition =
        speechWindow.SpeechRecognition ?? speechWindow.webkitSpeechRecognition;
      if (BrowserRecognition) {
        const speech = new BrowserRecognition();
        recognition.current = speech;
        speech.lang = `${locale}-IN`;
        speech.interimResults = true;
        speech.continuous = true;
        speech.onresult = (event) => {
          const parts = Array.from(event.results);
          finalSpeech.current = parts
            .filter((part) => part.isFinal)
            .map((part) => part[0].transcript)
            .join(" ");
          const live = parts.map((part) => part[0].transcript).join(" ");
          setInterim(live);
          if (ws.readyState === WebSocket.OPEN)
            ws.send(JSON.stringify({ type: "interim", text: live }));
        };
        speech.onerror = () => {};
        speech.start();
      }
      capture.start();
      setRecording(true);
    } catch {
      setError(t("micUnavailable"));
      media.current?.getTracks().forEach((track) => {
        track.stop();
      });
      setRecording(false);
    }
  }

  async function submitText(event: React.FormEvent) {
    event.preventDefault();
    const text = typed.trim();
    if (!text) return;
    if (busy || recording) cancel();
    stopPlayback();
    cancelled.current = false;
    turnVersion.current += 1;
    const version = turnVersion.current;
    setResult(null);
    setError("");
    setTranscript(text);
    setTyped("");
    try {
      const ws = await connect();
      if (cancelled.current || version !== turnVersion.current) return;
      releaseAt.current = performance.now();
      audioStarted.current = false;
      ws.send(JSON.stringify({ type: "release_start" }));
      sendRelease(ws, "", "audio/webm", text);
    } catch {
      setError(t("unavailable"));
    }
  }

  const content = (
    <section
      id={panelId}
      aria-label={t("title")}
      className={`voice-surface text-ink ${large ? "space-y-6" : "w-[min(90vw,28rem)] space-y-4"}`}
    >
      <div className="flex items-center justify-between gap-4">
        <div>
          <h2 className={large ? "section-label" : "font-display text-3xl"}>
            {t(large ? "tryPrompt" : "title")}
          </h2>
        </div>
        {!large && (
          <button
            type="button"
            onClick={closePanel}
            aria-label={t("close")}
            className="icon-button"
          >
            <Icon name="close" />
          </button>
        )}
      </div>
      {!large && <p className="font-ui text-graphite">{t("intro")}</p>}
      {large && (
        <div className="voice-presets">
          {(["jobsPrompt", "schemesPrompt", "pathPrompt"] as const).map(
            (key) => (
              <button
                type="button"
                key={key}
                disabled={busy || recording}
                onClick={() => {
                  setTyped(t(key));
                  textInput.current?.focus();
                }}
              >
                {t(key)}
              </button>
            ),
          )}
        </div>
      )}
      {pending && (
        <div className="border-l-2 border-amber pl-3 font-ui">
          <p>{pending.text}</p>
          <button
            type="button"
            onClick={() => {
              pendingRef.current = null;
              setPending(null);
            }}
            className="mt-2 text-sm text-signal underline"
          >
            {t("newQuestion")}
          </button>
        </div>
      )}
      <button
        type="button"
        onClick={start}
        className={`voice-prompt w-full bg-signal font-ui text-white ${large ? "min-h-24" : ""}`}
      >
        <Icon name="voice" />
        {recording ? t("release") : busy ? t("interrupt") : t("speak")}
      </button>
      <form onSubmit={submitText} className="flex gap-2">
        <input
          ref={textInput}
          value={typed}
          onChange={(event) => setTyped(event.target.value)}
          aria-label={t("textLabel")}
          placeholder={t("textPlaceholder")}
          className="min-w-0 flex-1 rounded border border-graphite/40 bg-bone px-3 py-2 font-ui"
        />
        <button
          type="submit"
          disabled={!typed.trim()}
          className="rounded border border-graphite/40 px-4 py-2 font-ui"
        >
          {t("send")}
        </button>
      </form>
      {(interim || transcript) && (
        <div
          aria-live="polite"
          className="border-t border-graphite/20 pt-3 font-ui"
        >
          <span className="font-mono text-xs uppercase text-graphite">
            {interim ? t("hearing") : t("heard")}
          </span>
          <p>{interim || transcript}</p>
        </div>
      )}
      {error && (
        <p role="alert" className="text-signal">
          {error}
        </p>
      )}
      {result && (
        <div className="space-y-4 border-t border-graphite/20 pt-4">
          <p className="font-mono text-xs uppercase text-graphite">
            {t("answer")}
          </p>
          {result.verification.no_data ? (
            <div>
              <p>{result.verification.message}</p>
              {result.verification.newest_evidence_at && (
                <p className="font-mono text-xs text-graphite">
                  {t("newest")}: {result.verification.newest_evidence_at}
                </p>
              )}
            </div>
          ) : (
            result.verification.sentences.map((row, index) => (
              <p
                key={`${row.text}-${row.citation_ids.join("-")}`}
                className="font-ui"
              >
                {row.text}{" "}
                {row.citation_ids.map((id) => {
                  const citation = result.verification.citations[id];
                  return (
                    citation && (
                      <a
                        key={id}
                        href={citation.source_url}
                        target="_blank"
                        rel="noreferrer"
                        className="ml-2 text-signal underline"
                        title={citation.fetched_at}
                      >
                        [{index + 1}]
                      </a>
                    )
                  );
                })}
              </p>
            ))
          )}
          {result.cards.length > 0 && (
            <ul className="space-y-2">
              {result.cards.map((card) => (
                <li
                  key={card.source_url}
                  className="border-l-2 border-signal pl-3"
                >
                  <a
                    href={card.source_url}
                    target="_blank"
                    rel="noreferrer"
                    className="font-ui underline"
                  >
                    {card.title}
                  </a>
                  {card.summary && (
                    <p className="text-sm text-graphite">{card.summary}</p>
                  )}
                  <p className="font-mono text-xs text-graphite">
                    {t("fetched")}: {card.fetched_at}
                  </p>
                  {card.eligibility && (
                    <p className="font-mono text-xs">
                      {t("eligibility")}:{" "}
                      {t(
                        card.eligibility.status === "true"
                          ? "eligible"
                          : "unknown",
                      )}
                    </p>
                  )}
                  {card.distance_km != null && (
                    <p className="font-mono text-xs">
                      {t("distance")}: {card.distance_km} km
                    </p>
                  )}
                  {card.scam?.badge && card.scam.badge !== "none" && (
                    <p className="font-mono text-xs text-signal">
                      {t("risk")}: {card.scam.reasons.join("; ")}
                    </p>
                  )}
                </li>
              ))}
            </ul>
          )}
          {result.engine_result && (
            <div className="border-l-2 border-sage pl-3 font-ui">
              <p className="font-mono text-xs uppercase text-graphite">
                {t("computed")}
              </p>
              {(result.engine_result.data.after?.steps ??
                result.engine_result.data.steps) && (
                <ol className="list-inside list-decimal space-y-1">
                  {(
                    result.engine_result.data.after?.steps ??
                    result.engine_result.data.steps ??
                    []
                  ).map((step) => (
                    <li key={step.skill}>
                      {locale === "te"
                        ? step.label_te
                        : locale === "hi"
                          ? step.label_hi
                          : step.label_en}{" "}
                      · {step.hours} {pathT("hours")}
                    </li>
                  ))}
                </ol>
              )}
              {result.engine_result.data.score != null && (
                <p>
                  {t("score")}: {result.engine_result.data.score}
                </p>
              )}
              {result.engine_result.data.item && (
                <p>
                  {pathT("question")}: {result.engine_result.data.item.text}
                </p>
              )}
            </div>
          )}
          <details className="border-t border-graphite/20 pt-3 font-mono text-xs">
            <summary className="cursor-pointer">{t("trace")}</summary>
            <p>
              {t("provider")}: {result.provider}
            </p>
            {result.trace.map((row) => (
              <p key={`${row.tool}-${row.ms}`}>
                {row.tool} {JSON.stringify(row.args)} · {row.ms} ms ·{" "}
                {row.provider} · {row.status}
              </p>
            ))}
            {result.verification.struck.map((row) => (
              <p key={`${row.reason}-${row.text}`}>
                {t("struck")}: {row.reason} · {row.text}
              </p>
            ))}
          </details>
        </div>
      )}
      {Object.keys(stamps).length > 0 && (
        <details className="font-mono text-xs text-graphite">
          <summary className="cursor-pointer">{t("timing")}</summary>
          {Object.entries(stamps).map(([key, value]) => (
            <p key={key}>
              {key}: {value} ms{" "}
              {summary[key]
                ? `· n ${summary[key].n} · p50 ${summary[key].p50} · p95 ${summary[key].p95}`
                : ""}
            </p>
          ))}
        </details>
      )}
    </section>
  );

  if (large) return content;
  return (
    <div className="relative" ref={panelRoot}>
      <button
        type="button"
        ref={trigger}
        onClick={() => (open ? closePanel() : setOpen(true))}
        aria-expanded={open}
        aria-controls={panelId}
        aria-label={t("open")}
        className="voice-trigger"
      >
        <Icon name="voice" />
        {t("open")}
      </button>
      {open && <div className="voice-popover">{content}</div>}
    </div>
  );
}
