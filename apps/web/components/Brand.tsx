export function Brand() {
  return (
    <span className="brand-lockup">
      <svg
        className="brand-mark"
        viewBox="0 0 40 40"
        aria-hidden="true"
        fill="none"
      >
        <path
          className="brand-path"
          pathLength={1}
          d="M6 33V7h13l15 13-15 13H6ZM12 27V13h6l9 7-9 7h-6M18 20h16"
          stroke="currentColor"
          strokeWidth="2"
          strokeLinecap="round"
          strokeLinejoin="round"
        />
      </svg>
      <span>DAARI</span>
    </span>
  );
}
