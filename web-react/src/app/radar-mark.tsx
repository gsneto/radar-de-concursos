/** Marca do Radar: anéis + varredura âmbar. SVG puro, sem dependência. */
export function RadarMark({ size = 32, sweep = true }: { size?: number; sweep?: boolean }) {
  return (
    <span
      className="relative grid shrink-0 place-items-center overflow-hidden rounded-[9px] border border-white/10 bg-[#0b0f17]"
      style={{ width: size, height: size }}
      aria-hidden
    >
      <svg width={size} height={size} viewBox="0 0 32 32" className="block">
        <circle cx="16" cy="16" r="10.5" fill="none" stroke="var(--color-accent)" strokeWidth="1.1" opacity="0.35" />
        <circle cx="16" cy="16" r="6.5" fill="none" stroke="var(--color-accent)" strokeWidth="1" opacity="0.55" />
        <circle cx="16" cy="16" r="2.6" fill="none" stroke="var(--color-accent)" strokeWidth="0.9" opacity="0.75" />
        {sweep && (
          <g className="origin-center [animation:sweep_3.6s_linear_infinite]">
            <path d="M16 16 L26 7.5" stroke="var(--color-accent)" strokeWidth="1.6" strokeLinecap="round" opacity="0.9" />
          </g>
        )}
        <circle cx="16" cy="16" r="1.6" fill="var(--color-fg)" />
        <circle cx="24.2" cy="9.1" r="1.5" fill="var(--color-accent)" />
      </svg>
    </span>
  );
}
