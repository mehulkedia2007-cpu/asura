"use client";

import { motion } from "motion/react";
import { useTranslations } from "next-intl";
import { useRef, useState } from "react";
import { Icon, type IconName } from "@/components/Icon";
import { Link } from "@/i18n/navigation";
import { useReducedMotion } from "@/lib/use-reduced-motion";

const features = [
  "path",
  "leads",
  "schemes",
  "questions",
  "prep",
  "interview",
  "voice",
  "evidence",
] as const;
const stages = [
  ["path", "questions", "voice"],
  ["path", "prep"],
  ["leads", "schemes", "interview"],
] as const;

export function JourneyMotion() {
  const t = useTranslations("home");
  const e = useTranslations("experience");
  const nav = useTranslations("workspace");
  const reduced = useReducedMotion();
  const dialog = useRef<HTMLDialogElement>(null);
  const trigger = useRef<HTMLButtonElement>(null);
  const [stage, setStage] = useState(0);
  const [open, setOpen] = useState(false);
  const [paused, setPaused] = useState(false);

  function close() {
    dialog.current?.close();
  }

  return (
    <>
      <button
        ref={trigger}
        className="journey-start secondary-link"
        type="button"
        onClick={() => {
          setStage(0);
          setOpen(true);
          dialog.current?.showModal();
        }}
      >
        {e("start")} <Icon name="arrow" />
      </button>
      <section className="feature-ribbon" aria-label={e("features")}>
        <div className="feature-ribbon-heading">
          <h2 className="section-label">{e("features")}</h2>
          <button
            type="button"
            aria-pressed={paused}
            onClick={() => setPaused(!paused)}
          >
            {e(paused ? "play" : "pause")}
          </button>
        </div>
        <div className={`feature-window ${paused ? "is-paused" : ""}`}>
          <div className="feature-track">
            <div className="feature-set">
              {features.map((route) => (
                <Link className="feature-item" key={route} href={`/${route}`}>
                  <Icon name={route} className="feature-icon" />
                  <span>{nav(route)}</span>
                </Link>
              ))}
            </div>
            <div className="feature-set feature-copy" aria-hidden="true">
              {features.map((route) => (
                <span className="feature-item" key={route}>
                  <Icon name={route} className="feature-icon" />
                  <span>{nav(route)}</span>
                </span>
              ))}
            </div>
          </div>
        </div>
      </section>
      <dialog
        ref={dialog}
        className="journey-dialog"
        aria-labelledby="journey-title"
        onKeyDown={(event) => {
          if (event.key === "Escape") close();
        }}
        onClose={() => {
          setOpen(false);
          trigger.current?.focus();
        }}
        onClick={(event) => {
          if (event.target === dialog.current) {
            const box = dialog.current.getBoundingClientRect();
            if (
              event.clientX < box.left ||
              event.clientX > box.right ||
              event.clientY < box.top ||
              event.clientY > box.bottom
            )
              close();
          }
        }}
      >
        <div className="journey-dialog-heading">
          <span className="section-label">DAARI / {t("how")}</span>
          <button
            type="button"
            className="icon-button"
            aria-label={e("close")}
            onClick={close}
          >
            <Icon name="close" />
          </button>
        </div>
        <h2 id="journey-title">{e("start")}</h2>
        <p className="journey-dialog-intro">{e("intro")}</p>
        <div className="journey-stage-picker">
          <svg
            viewBox="0 0 600 40"
            preserveAspectRatio="none"
            aria-hidden="true"
          >
            <path d="M100 20H500" className="journey-base-line" />
            {open && (
              <motion.path
                key={stage}
                d="M100 20H500"
                className="journey-moving-line"
                initial={{ pathLength: reduced ? 1 : 0 }}
                animate={{ pathLength: 1 }}
                transition={{ duration: reduced ? 0 : 0.65 }}
              />
            )}
          </svg>
          {[0, 1, 2].map((index) => (
            <button
              key={index}
              type="button"
              aria-pressed={stage === index}
              onClick={() => setStage(index)}
            >
              <span>0{index + 1}</span>
              <strong>{t(`step${index + 1}`)}</strong>
            </button>
          ))}
        </div>
        <div className="journey-stage-content" aria-live="polite">
          <p className="journey-stage-note">{t(`step${stage + 1}Note`)}</p>
          <div className="journey-stage-links">
            {stages[stage].map((route) => (
              <Link
                key={route}
                href={`/${route}`}
                className="secondary-link"
                onClick={close}
              >
                <Icon name={route as IconName} />
                {nav(route)}
                <Icon name="arrow" />
              </Link>
            ))}
          </div>
        </div>
      </dialog>
    </>
  );
}
