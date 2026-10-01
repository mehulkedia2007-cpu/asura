"use client";

import { motion, useMotionValue, useSpring } from "motion/react";
import { useTranslations } from "next-intl";
import { useEffect, useRef, useState } from "react";
import { usePathname } from "@/i18n/navigation";
import { useReducedMotion } from "@/lib/use-reduced-motion";

export function Experience() {
  const t = useTranslations("experience");
  const pathname = usePathname();
  const reduced = useReducedMotion();
  const [sound, setSound] = useState(true);
  const [paused, setPaused] = useState(false);
  const [pointer, setPointer] = useState(false);
  const [visible, setVisible] = useState(false);
  const [hover, setHover] = useState(false);
  const audio = useRef<AudioContext | null>(null);
  const voicePanels = useRef(new Set<string>());
  const x = useMotionValue(-100);
  const y = useMotionValue(-100);
  const followX = useSpring(x, { stiffness: 260, damping: 28 });
  const followY = useSpring(y, { stiffness: 260, damping: 28 });

  useEffect(() => {
    try {
      setSound(localStorage.getItem("daari-sound-v1") !== "off");
    } catch {
      /* Session preference works without storage. */
    }
    const media = matchMedia("(hover: hover) and (pointer: fine)");
    const update = () => setPointer(media.matches);
    update();
    media.addEventListener("change", update);
    const voice = (event: Event) => {
      const { id, active } = (
        event as CustomEvent<{ id: string; active: boolean }>
      ).detail;
      if (active) {
        voicePanels.current.add(id);
        void audio.current?.suspend().catch(() => {});
      } else voicePanels.current.delete(id);
      setPaused(voicePanels.current.size > 0);
    };
    window.addEventListener("daari:voice", voice);
    return () => {
      media.removeEventListener("change", update);
      window.removeEventListener("daari:voice", voice);
      void audio.current?.close();
    };
  }, []);

  useEffect(() => {
    document.documentElement.dataset.motionPaused = paused ? "true" : "false";
    return () => {
      delete document.documentElement.dataset.motionPaused;
    };
  }, [paused]);

  useEffect(() => {
    if (!pointer || reduced || paused) return;
    const move = (event: PointerEvent) => {
      x.set(event.clientX);
      y.set(event.clientY);
      setVisible(true);
      setHover(
        event.target instanceof Element && !!event.target.closest("a,button"),
      );
    };
    const leave = () => setVisible(false);
    document.addEventListener("pointermove", move, { passive: true });
    document.addEventListener("pointerleave", leave);
    return () => {
      document.removeEventListener("pointermove", move);
      document.removeEventListener("pointerleave", leave);
    };
  }, [pointer, reduced, paused, x, y]);

  useEffect(() => {
    if (!sound || paused || pathname === "/voice") return;
    const click = (event: MouseEvent) => {
      if (
        !event.isTrusted ||
        event.button !== 0 ||
        event.ctrlKey ||
        event.metaKey ||
        event.shiftKey ||
        event.altKey ||
        !(event.target instanceof Element)
      )
        return;
      const link = event.target.closest<HTMLAnchorElement>("a[href]");
      if (
        !link ||
        link.target === "_blank" ||
        link.origin !== location.origin ||
        link.pathname === location.pathname ||
        link.hash
      )
        return;
      try {
        const context = audio.current ?? new AudioContext();
        audio.current = context;
        void context
          .resume()
          .then(() => {
            if (context.state !== "running" || voicePanels.current.size > 0)
              return;
            const tone = context.createOscillator();
            const gain = context.createGain();
            tone.type = "sine";
            tone.frequency.setValueAtTime(640, context.currentTime);
            tone.frequency.exponentialRampToValueAtTime(
              920,
              context.currentTime + 0.08,
            );
            gain.gain.setValueAtTime(0, context.currentTime);
            gain.gain.linearRampToValueAtTime(
              0.035,
              context.currentTime + 0.008,
            );
            gain.gain.exponentialRampToValueAtTime(
              0.0001,
              context.currentTime + 0.12,
            );
            tone.connect(gain);
            gain.connect(context.destination);
            tone.start();
            tone.stop(context.currentTime + 0.13);
            tone.onended = () => {
              tone.disconnect();
              gain.disconnect();
            };
          })
          .catch(() => {});
      } catch {
        /* Navigation works if audio is unavailable. */
      }
    };
    document.addEventListener("click", click);
    return () => document.removeEventListener("click", click);
  }, [sound, paused, pathname]);

  function toggle() {
    setSound(!sound);
    if (sound) void audio.current?.suspend();
    try {
      localStorage.setItem("daari-sound-v1", sound ? "off" : "on");
    } catch {
      /* Keep the preference for this visit. */
    }
  }

  return (
    <>
      <button
        className="icon-button sound-toggle"
        type="button"
        aria-label={t(sound ? "mute" : "unmute")}
        aria-pressed={sound}
        onClick={toggle}
        title={t(sound ? "mute" : "unmute")}
      >
        <svg
          viewBox="0 0 24 24"
          className="icon"
          aria-hidden="true"
          fill="none"
          stroke="currentColor"
          strokeWidth="1.6"
          strokeLinecap="round"
          strokeLinejoin="round"
        >
          <path d="M4 9h4l5-4v14l-5-4H4Z" />
          <path
            d={
              sound
                ? "M17 8a6 6 0 0 1 0 8M20 5a10 10 0 0 1 0 14"
                : "m17 9 5 6m0-6-5 6"
            }
          />
        </svg>
      </button>
      {pointer && !reduced && !paused && (
        <motion.div
          className="cursor-orbit"
          aria-hidden="true"
          style={{ x: followX, y: followY }}
          animate={{ opacity: visible ? 0.65 : 0, scale: hover ? 1.6 : 1 }}
          transition={{ duration: 0.18 }}
        >
          <span className="cursor-orbit-dot" />
        </motion.div>
      )}
      {!reduced && !paused && (
        <motion.div
          key={pathname}
          className="route-signal"
          aria-hidden="true"
          initial={{ scaleX: 0, opacity: 1 }}
          animate={{ scaleX: 1, opacity: 0 }}
          transition={{
            scaleX: { duration: 0.4 },
            opacity: { delay: 0.4, duration: 0.2 },
          }}
        />
      )}
    </>
  );
}
