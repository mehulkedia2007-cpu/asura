import type { CSSProperties } from "react";

export type IconName =
  | "home"
  | "path"
  | "leads"
  | "schemes"
  | "questions"
  | "prep"
  | "interview"
  | "voice"
  | "evidence"
  | "arrow"
  | "menu"
  | "close"
  | "sun"
  | "moon"
  | "check";

const paths: Record<IconName, string> = {
  home: "M3 10 12 3l9 7M5 9v11h5v-6h4v6h5V9",
  path: "M5 4v7a4 4 0 0 0 4 4h6a4 4 0 0 1 4 4v1M15 4h5v5M20 4l-8 8M3 4h4M17 20h4",
  leads: "M8 7V4h8v3M3 7h18v13H3ZM3 12a24 24 0 0 0 18 0M10 12h4v3h-4Z",
  schemes: "M3 10h18M5 10v9M10 10v9M14 10v9M19 10v9M3 20h18M2 7l10-5 10 5Z",
  questions:
    "M12 5C8 2 4 3 2 4v15c4-2 7-2 10 0 3-2 6-2 10 0V4c-2-1-6-2-10 1ZM12 5v14",
  prep: "M4 5h16v16H4ZM8 2v6M16 2v6M4 10h16M8 14h3M14 14h2M8 18h3",
  interview: "M4 3h16v14H9l-5 4ZM8 7h8M8 11h5",
  voice:
    "M9 4a3 3 0 0 1 6 0v8a3 3 0 0 1-6 0ZM5 10v2a7 7 0 0 0 14 0v-2M12 19v3M8 22h8",
  evidence: "M4 4v16h17M8 16v-4M13 16V8M18 16V5",
  arrow: "M5 12h14M13 6l6 6-6 6",
  menu: "M4 6h16M4 12h16M4 18h16",
  close: "m6 6 12 12M6 18 18 6",
  sun: "M12 3V1M12 23v-2M3 12H1M23 12h-2M5 5 3 3M21 21l-2-2M5 19l-2 2M21 3l-2 2M16 12a4 4 0 1 1-8 0 4 4 0 0 1 8 0Z",
  moon: "M20 15A9 9 0 0 1 9 4a9 9 0 1 0 11 11Z",
  check: "m5 12 4 4L19 6",
};

export function Icon({
  name,
  className = "",
  style,
}: {
  name: IconName;
  className?: string;
  style?: CSSProperties;
}) {
  return (
    <svg
      aria-hidden="true"
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="1.6"
      strokeLinecap="round"
      strokeLinejoin="round"
      className={`icon ${className}`}
      style={style}
    >
      <path d={paths[name]} />
    </svg>
  );
}
