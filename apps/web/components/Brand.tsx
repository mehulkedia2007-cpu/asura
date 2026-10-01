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
          d="M5 33V18a8 8 0 0 1 8-8h19M23 2l9 8-9 8"
          stroke="currentColor"
          strokeWidth="2"
          strokeLinecap="round"
          strokeLinejoin="round"
        />
        <circle cx="5" cy="33" r="3" fill="currentColor" />
      </svg>
      <span>DAARI</span>
    </span>
  );
}
