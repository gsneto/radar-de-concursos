import { motion, useReducedMotion } from 'motion/react';
import { useId, useState, type ReactNode } from 'react';
import { cn } from '@/lib/cn';
import { integer, percent } from '@/lib/format';

export interface SeriesPoint {
  label: string;
  value: number;
  color?: string;
  title?: string;
}

/* ------------------------------------------------------------------ */
/* Alternativa textual: toda visualização tem tabela equivalente.      */
/* ------------------------------------------------------------------ */

export function DataTableFallback({
  summary = 'Ver dados em tabela',
  caption,
  columns,
  rows,
}: {
  summary?: string;
  caption?: string;
  columns: string[];
  rows: (string | number)[][];
}) {
  return (
    <details className="group mt-3">
      <summary className="cursor-pointer list-none text-2xs font-medium text-fg-3 transition-colors hover:text-fg-2">
        <span className="mr-1 inline-block transition-transform group-open:rotate-90">▸</span>
        {summary}
      </summary>
      <table className="mt-2 w-full border-collapse text-2xs">
        {caption && <caption className="pb-1 text-left text-fg-3">{caption}</caption>}
        <thead>
          <tr>
            {columns.map((column, index) => (
              <th
                key={column}
                scope="col"
                className={cn(
                  'border-b border-line px-2 py-1 font-medium text-fg-3',
                  index === columns.length - 1 ? 'text-right' : 'text-left',
                )}
              >
                {column}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {rows.map((row, rowIndex) => (
            <tr key={rowIndex}>
              {row.map((cell, cellIndex) => (
                <td
                  key={cellIndex}
                  className={cn(
                    'border-b border-line/60 px-2 py-1 text-fg-2',
                    cellIndex === row.length - 1 && 'text-right tabular',
                  )}
                >
                  {cell}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </details>
  );
}

/* ------------------------------------------------------------------ */
/* Curva suave (Catmull-Rom → Bézier cúbica).                          */
/* ------------------------------------------------------------------ */

function smoothPath(points: { x: number; y: number }[], tension = 0.22): string {
  if (!points.length) return '';
  if (points.length === 1) return `M ${points[0].x} ${points[0].y}`;
  let d = `M ${points[0].x} ${points[0].y}`;
  for (let i = 0; i < points.length - 1; i += 1) {
    const p0 = points[i - 1] ?? points[i];
    const p1 = points[i];
    const p2 = points[i + 1];
    const p3 = points[i + 2] ?? p2;
    const c1x = p1.x + (p2.x - p0.x) * tension;
    const c1y = p1.y + (p2.y - p0.y) * tension;
    const c2x = p2.x - (p3.x - p1.x) * tension;
    const c2y = p2.y - (p3.y - p1.y) * tension;
    d += ` C ${c1x.toFixed(2)} ${c1y.toFixed(2)}, ${c2x.toFixed(2)} ${c2y.toFixed(2)}, ${p2.x.toFixed(2)} ${p2.y.toFixed(2)}`;
  }
  return d;
}

function niceMax(value: number): number {
  const magnitude = 10 ** Math.floor(Math.log10(Math.max(value, 1)));
  const normalized = value / magnitude;
  const step = normalized <= 1 ? 1 : normalized <= 2 ? 2 : normalized <= 5 ? 5 : 10;
  return step * magnitude;
}

/* ------------------------------------------------------------------ */
/* Área: série temporal com curva suave, gradiente, crosshair e tooltip. */
/* ------------------------------------------------------------------ */

export function AreaChart({
  data,
  height = 210,
  ariaLabel,
  description,
  color = 'var(--color-accent)',
  unit = '',
  emptyLabel = 'Sem dados no período',
  className,
  footer,
}: {
  data: SeriesPoint[];
  height?: number;
  ariaLabel: string;
  description?: string;
  color?: string;
  unit?: string;
  emptyLabel?: string;
  className?: string;
  footer?: ReactNode;
}) {
  const id = useId();
  const reduce = useReducedMotion();
  const [active, setActive] = useState<number | null>(null);

  const width = 720;
  const pad = { top: 18, right: 14, bottom: 26, left: 40 };
  const plotW = width - pad.left - pad.right;
  const plotH = height - pad.top - pad.bottom;

  const max = niceMax(Math.max(...data.map((d) => d.value), 1));
  const stepX = data.length > 1 ? plotW / (data.length - 1) : 0;

  const points = data.map((item, index) => ({
    x: pad.left + (data.length === 1 ? plotW / 2 : index * stepX),
    y: pad.top + plotH - (item.value / max) * plotH,
    item,
  }));

  const line = smoothPath(points);
  const area = points.length
    ? `${line} L ${points[points.length - 1].x} ${pad.top + plotH} L ${points[0].x} ${pad.top + plotH} Z`
    : '';

  const total = data.reduce((sum, item) => sum + item.value, 0);
  const peak = data.reduce((best, item) => (item.value > best.value ? item : best), {
    label: '—',
    value: 0,
  });

  const cursor = active !== null ? points[active] : null;

  const handleMove = (event: React.PointerEvent<HTMLDivElement>) => {
    if (!data.length) return;
    const rect = event.currentTarget.getBoundingClientRect();
    const ratio = (event.clientX - rect.left - (pad.left / width) * rect.width) /
      (rect.width * (plotW / width));
    const index = Math.round(ratio * (data.length - 1));
    setActive(Math.min(data.length - 1, Math.max(0, index)));
  };

  return (
    <div className={cn('w-full', className)}>
      <div className="mb-2 flex items-end justify-between gap-3">
        <div>
          <p className="font-display text-[1.35rem] leading-none font-semibold tabular text-fg">
            {integer(total)}{unit ? ' ' : ''}
            {unit && <span className="ml-1 text-xs font-medium tracking-normal text-fg-3">{unit}</span>}
          </p>
          <p className="mt-1 text-2xs text-fg-3">
            pico em {peak.label} · {integer(peak.value)} {unit}
          </p>
        </div>
        {footer}
      </div>

      <div
        className="relative touch-pan-y select-none"
        style={{ height }}
        onPointerMove={handleMove}
        onPointerLeave={() => setActive(null)}
      >
        <svg
          viewBox={`0 0 ${width} ${height}`}
          role="img"
          aria-labelledby={`${id}-t ${id}-d`}
          preserveAspectRatio="none"
          className="block w-full overflow-visible"
          style={{ height }}
        >
          <title id={`${id}-t`}>{ariaLabel}</title>
          <desc id={`${id}-d`}>{description ?? ariaLabel}</desc>

          <defs>
            <linearGradient id={`${id}-fill`} x1="0" y1="0" x2="0" y2="1">
              <stop offset="0%" stopColor={color} stopOpacity="0.34" />
              <stop offset="55%" stopColor={color} stopOpacity="0.10" />
              <stop offset="100%" stopColor={color} stopOpacity="0" />
            </linearGradient>
            <linearGradient id={`${id}-stroke`} x1="0" y1="0" x2="1" y2="0">
              <stop offset="0%" stopColor={color} stopOpacity="0.65" />
              <stop offset="55%" stopColor={color} stopOpacity="1" />
              <stop offset="100%" stopColor={color} stopOpacity="0.9" />
            </linearGradient>
          </defs>

          {[0, 1, 2, 3, 4].map((tick) => {
            const y = pad.top + (plotH / 4) * tick;
            return (
              <g key={tick}>
                <line
                  x1={pad.left}
                  y1={y}
                  x2={width - pad.right}
                  y2={y}
                  stroke="rgb(255 255 255 / 0.055)"
                  strokeWidth="1"
                  strokeDasharray={tick === 4 ? undefined : '2 4'}
                />
                <text x={pad.left - 8} y={y + 3} textAnchor="end" fill="var(--color-fg-3)" fontSize="9">
                  {integer(Math.round(max - (max / 4) * tick))}
                </text>
              </g>
            );
          })}

          {!data.length && (
            <text
              x={pad.left + plotW / 2}
              y={pad.top + plotH / 2}
              textAnchor="middle"
              fill="var(--color-fg-3)"
              fontSize="11"
            >
              {emptyLabel}
            </text>
          )}

          {area && <motion.path d={area} fill={`url(#${id}-fill)`} initial={{ opacity: 0 }} animate={{ opacity: 1 }} transition={{ duration: reduce ? 0 : 0.5 }} />}

          {line && (
            <motion.path
              d={line}
              fill="none"
              stroke={`url(#${id}-stroke)`}
              strokeWidth="2"
              strokeLinecap="round"
              strokeLinejoin="round"
              vectorEffect="non-scaling-stroke"
              initial={reduce ? false : { pathLength: 0 }}
              animate={{ pathLength: 1 }}
              transition={{ duration: 0.9, ease: [0.16, 1, 0.3, 1] }}
            />
          )}

          {cursor && (
            <g>
              <line
                x1={cursor.x}
                y1={pad.top}
                x2={cursor.x}
                y2={pad.top + plotH}
                stroke="rgb(255 255 255 / 0.16)"
                strokeWidth="1"
                strokeDasharray="3 3"
              />
              <circle cx={cursor.x} cy={cursor.y} r="4.5" fill="var(--color-bg)" stroke={color} strokeWidth="2" />
            </g>
          )}

          {data.map((item, index) => {
            const show = index % Math.max(1, Math.ceil(data.length / 8)) === 0 || index === data.length - 1;
            if (!show) return null;
            return (
              <text
                key={`${item.label}-${index}`}
                x={pad.left + (data.length === 1 ? plotW / 2 : index * stepX)}
                y={height - 8}
                textAnchor={index === 0 ? 'start' : index === data.length - 1 ? 'end' : 'middle'}
                fill="var(--color-fg-3)"
                fontSize="9"
              >
                {item.label}
              </text>
            );
          })}
        </svg>

        {cursor && (
          <div
            className="pointer-events-none absolute z-10 -translate-x-1/2 -translate-y-full rounded-xs border border-line-strong bg-surface-3 px-2 py-1 text-2xs shadow-float"
            style={{
              left: `${(cursor.x / width) * 100}%`,
              top: `${(cursor.y / height) * 100}%`,
              marginTop: -8,
            }}
          >
            <span className="mr-1.5 text-fg-3">{cursor.item.label}</span>
            <span className="font-medium tabular text-fg">
              {integer(cursor.item.value)}{unit ? ' ' : ''}
              {unit && <span className="text-fg-3">{unit}</span>}
            </span>
          </div>
        )}
      </div>
    </div>
  );
}

/* ------------------------------------------------------------------ */
/* Colunas: comparação categórica com cantos suaves e realce no hover. */
/* ------------------------------------------------------------------ */

export function ColumnChart({
  data,
  height = 190,
  ariaLabel,
  description,
  color = 'var(--color-accent)',
  emptyLabel = 'Sem dados no período',
  className,
}: {
  data: SeriesPoint[];
  height?: number;
  ariaLabel: string;
  description?: string;
  color?: string;
  emptyLabel?: string;
  className?: string;
}) {
  const id = useId();
  const reduce = useReducedMotion();
  const [active, setActive] = useState<number | null>(null);

  const width = 640;
  const pad = { top: 14, right: 8, bottom: 26, left: 34 };
  const plotW = width - pad.left - pad.right;
  const plotH = height - pad.top - pad.bottom;
  const max = niceMax(Math.max(...data.map((d) => d.value), 1));
  const slot = data.length ? plotW / data.length : plotW;
  const barWidth = Math.max(5, Math.min(26, slot * 0.5));
  const labelEvery = Math.max(1, Math.ceil(data.length / 7));

  return (
    <div className={cn('w-full', className)}>
      <svg
        viewBox={`0 0 ${width} ${height}`}
        role="img"
        aria-labelledby={`${id}-t ${id}-d`}
        preserveAspectRatio="none"
        className="block w-full overflow-visible"
        style={{ height }}
        onPointerLeave={() => setActive(null)}
      >
        <title id={`${id}-t`}>{ariaLabel}</title>
        <desc id={`${id}-d`}>{description ?? ariaLabel}</desc>
        <defs>
          <linearGradient id={`${id}-bar`} x1="0" y1="0" x2="0" y2="1">
            <stop offset="0%" stopColor={color} stopOpacity="1" />
            <stop offset="100%" stopColor={color} stopOpacity="0.42" />
          </linearGradient>
        </defs>

        {[0, 1, 2, 3, 4].map((tick) => {
          const y = pad.top + (plotH / 4) * tick;
          return (
            <g key={tick}>
              <line
                x1={pad.left}
                y1={y}
                x2={width - pad.right}
                y2={y}
                stroke="rgb(255 255 255 / 0.055)"
                strokeWidth="1"
                strokeDasharray={tick === 4 ? undefined : '2 4'}
              />
              <text x={pad.left - 6} y={y + 3} textAnchor="end" fill="var(--color-fg-3)" fontSize="9">
                {integer(Math.round(max - (max / 4) * tick))}
              </text>
            </g>
          );
        })}

        {!data.length && (
          <text
            x={pad.left + plotW / 2}
            y={pad.top + plotH / 2}
            textAnchor="middle"
            fill="var(--color-fg-3)"
            fontSize="11"
          >
            {emptyLabel}
          </text>
        )}

        {data.map((item, index) => {
          const barH = max ? (item.value / max) * plotH : 0;
          const x = pad.left + slot * index + (slot - barWidth) / 2;
          const y = pad.top + plotH - barH;
          const dim = active !== null && active !== index;
          return (
            <g key={`${item.label}-${index}`} onPointerEnter={() => setActive(index)}>
              <rect
                x={pad.left + slot * index}
                y={pad.top}
                width={slot}
                height={plotH}
                fill="transparent"
              />
              <motion.rect
                x={x}
                width={barWidth}
                rx="3"
                fill={item.color ?? `url(#${id}-bar)`}
                initial={reduce ? false : { y: pad.top + plotH, height: 0 }}
                animate={{ y, height: Math.max(item.value > 0 ? 2 : 0, barH) }}
                transition={{ duration: 0.55, delay: index * 0.035, ease: [0.16, 1, 0.3, 1] }}
                opacity={dim ? 0.45 : 1}
              >
                <title>{item.title ?? `${item.label}: ${integer(item.value)}`}</title>
              </motion.rect>
              {item.value > 0 && slot > 30 && (
                <text
                  x={x + barWidth / 2}
                  y={y - 5}
                  textAnchor="middle"
                  fill="var(--color-fg-2)"
                  fontSize="9"
                  fontWeight="600"
                  opacity={dim ? 0.5 : 1}
                >
                  {integer(item.value)}
                </text>
              )}
              {(index % labelEvery === 0 || index === data.length - 1) && (
                <text
                  x={pad.left + slot * index + slot / 2}
                  y={height - 8}
                  textAnchor="middle"
                  fill="var(--color-fg-3)"
                  fontSize="9"
                >
                  {item.label}
                </text>
              )}
            </g>
          );
        })}
      </svg>
    </div>
  );
}

/* ------------------------------------------------------------------ */
/* Sparkline compacta.                                                 */
/* ------------------------------------------------------------------ */

export function Sparkline({
  data,
  labels,
  height = 44,
  color = 'var(--color-accent)',
  fill = true,
  ariaLabel,
  className,
}: {
  data: number[];
  labels?: string[];
  height?: number;
  color?: string;
  fill?: boolean;
  ariaLabel: string;
  className?: string;
}) {
  const gradientId = useId();
  const [active, setActive] = useState<number | null>(null);
  const points = data.length;

  if (!points) {
    return <div className={cn('h-11 rounded-xs bg-surface-2', className)} aria-hidden />;
  }

  const max = Math.max(...data);
  const min = Math.min(...data);
  const span = max - min || 1;
  const step = points === 1 ? 100 : 100 / (points - 1);
  const coords = data.map((value, index) => ({
    x: points === 1 ? 50 : index * step,
    y: 46 - ((value - min) / span) * 38,
    value,
  }));

  const line = coords
    .map((point, index) => (index === 0 ? `M ${point.x} ${point.y}` : `L ${point.x} ${point.y}`))
    .join(' ');
  const area = `${line} L ${coords[coords.length - 1].x} 48 L ${coords[0].x} 48 Z`;
  const cursor = active !== null ? coords[active] : null;

  return (
    <div className={cn('relative w-full', className)} style={{ height }}>
      <div
        role="img"
        aria-label={ariaLabel}
        className="absolute inset-0 touch-pan-y"
        onPointerMove={(event) => {
          const rect = event.currentTarget.getBoundingClientRect();
          const ratio = (event.clientX - rect.left) / rect.width;
          const index = Math.min(points - 1, Math.max(0, Math.round(ratio * (points - 1))));
          setActive(index);
        }}
        onPointerLeave={() => setActive(null)}
      >
        <svg
          width="100%"
          height={height}
          viewBox="0 0 100 48"
          preserveAspectRatio="none"
          aria-hidden
          className="block overflow-visible"
        >
          <defs>
            <linearGradient id={gradientId} x1="0" y1="0" x2="0" y2="1">
              <stop offset="0%" stopColor={color} stopOpacity="0.3" />
              <stop offset="100%" stopColor={color} stopOpacity="0" />
            </linearGradient>
          </defs>
          {fill && <path d={area} fill={`url(#${gradientId})`} />}
          <path
            d={line}
            fill="none"
            stroke={color}
            strokeWidth="1.6"
            strokeLinecap="round"
            strokeLinejoin="round"
            vectorEffect="non-scaling-stroke"
          />
        </svg>
        {cursor && (
          <>
            <span
              aria-hidden
              className="pointer-events-none absolute inset-y-0 w-px -translate-x-1/2 opacity-25"
              style={{ left: `${cursor.x}%`, background: color }}
            />
            <span
              aria-hidden
              className="pointer-events-none absolute size-2 -translate-x-1/2 -translate-y-1/2 rounded-full ring-2 ring-surface"
              style={{ left: `${cursor.x}%`, top: `${(cursor.y / 48) * 100}%`, background: color }}
            />
            <span
              aria-hidden
              className="pointer-events-none absolute z-10 -translate-x-1/2 -translate-y-full whitespace-nowrap rounded-xs border border-line-strong bg-surface-3 px-2 py-1 text-2xs text-fg shadow-float"
              style={{ left: `${cursor.x}%`, top: `${(cursor.y / 48) * 100}%` }}
            >
              {labels?.[active!] ? <span className="mr-1 text-fg-3">{labels[active!]}</span> : null}
              <span className="tabular font-medium">{integer(cursor.value)}</span>
            </span>
          </>
        )}
      </div>
    </div>
  );
}

/* ------------------------------------------------------------------ */
/* Rank bars: rótulo, barra e valor, com preenchimento animado.        */
/* ------------------------------------------------------------------ */

export function BarList({
  data,
  ariaLabel,
  className,
  max: explicitMax,
}: {
  data: SeriesPoint[];
  ariaLabel: string;
  className?: string;
  max?: number;
}) {
  const reduce = useReducedMotion();
  const max = explicitMax ?? Math.max(...data.map((d) => d.value), 1);
  return (
    <ul className={cn('space-y-2.5', className)} aria-label={ariaLabel}>
      {data.map((item, index) => (
        <li key={item.label} className="grid grid-cols-[minmax(88px,34%)_1fr_auto] items-center gap-3">
          <span className="truncate text-xs text-fg-2" title={item.title ?? item.label}>
            {item.label}
          </span>
          <span className="h-1.5 overflow-hidden rounded-full bg-white/[0.06]">
            <motion.span
              className="block h-full rounded-full"
              style={{ background: item.color ?? 'var(--color-accent)' }}
              initial={reduce ? false : { width: 0 }}
              animate={{ width: `${Math.max(item.value > 0 ? 2 : 0, (item.value / max) * 100)}%` }}
              transition={{ duration: 0.6, delay: index * 0.04, ease: [0.16, 1, 0.3, 1] }}
            />
          </span>
          <span className="min-w-10 text-right text-xs font-medium tabular text-fg">
            {integer(item.value)}
          </span>
        </li>
      ))}
    </ul>
  );
}

/* ------------------------------------------------------------------ */
/* Barra empilhada + legenda.                                          */
/* ------------------------------------------------------------------ */

export function StackedBar({ segments, ariaLabel }: { segments: SeriesPoint[]; ariaLabel: string }) {
  const total = segments.reduce((sum, segment) => sum + segment.value, 0);
  return (
    <div
      role="img"
      aria-label={`${ariaLabel}: ${segments.map((s) => `${s.label} ${integer(s.value)}`).join(', ')}`}
      className="flex h-2.5 w-full overflow-hidden rounded-full bg-white/[0.06]"
    >
      {segments.map((segment) => {
        if (!segment.value) return null;
        return (
          <span
            key={segment.label}
            className="h-full min-w-[3px] first:rounded-l-full last:rounded-r-full"
            style={{
              width: `${total ? (segment.value / total) * 100 : 0}%`,
              background: segment.color,
            }}
            title={`${segment.label}: ${integer(segment.value)}`}
          />
        );
      })}
    </div>
  );
}

export function Legend({ segments }: { segments: SeriesPoint[] }) {
  const total = segments.reduce((sum, segment) => sum + segment.value, 0);
  return (
    <ul className="mt-3 flex flex-wrap gap-x-4 gap-y-1.5">
      {segments.map((segment) => (
        <li key={segment.label} className="inline-flex items-center gap-1.5 text-2xs text-fg-2">
          <span className="size-2 shrink-0 rounded-[3px]" style={{ background: segment.color }} />
          <span>{segment.label}</span>
          <span className="font-medium tabular text-fg">{integer(segment.value)}</span>
          <span className="text-fg-3">{percent(share(segment.value, total))}</span>
        </li>
      ))}
    </ul>
  );
}

function share(value: number, total: number): number | null {
  return total > 0 ? (value / total) * 100 : null;
}

/* ------------------------------------------------------------------ */
/* Anel: prontidão e progresso com denominador.                        */
/* ------------------------------------------------------------------ */

export function Ring({
  value,
  total,
  size = 76,
  thickness = 7,
  color = 'var(--color-accent)',
  track = 'rgb(255 255 255 / 0.07)',
  label,
  children,
}: {
  value: number;
  total: number;
  size?: number;
  thickness?: number;
  color?: string;
  track?: string;
  label: string;
  children?: ReactNode;
}) {
  const radius = (size - thickness) / 2;
  const circumference = 2 * Math.PI * radius;
  const ratio = total > 0 ? Math.min(1, Math.max(0, value / total)) : 0;

  return (
    <div
      className="relative grid place-items-center"
      style={{ width: size, height: size }}
      role="img"
      aria-label={`${label}: ${integer(value)} de ${integer(total)}`}
    >
      <svg width={size} height={size} className="-rotate-90" aria-hidden>
        <circle cx={size / 2} cy={size / 2} r={radius} fill="none" stroke={track} strokeWidth={thickness} />
        <circle
          cx={size / 2}
          cy={size / 2}
          r={radius}
          fill="none"
          stroke={color}
          strokeWidth={thickness}
          strokeLinecap="round"
          strokeDasharray={`${circumference * ratio} ${circumference}`}
          className="transition-[stroke-dasharray] duration-500"
        />
      </svg>
      <div className="absolute inset-0 grid place-items-center text-center leading-none">
        {children}
      </div>
    </div>
  );
}

/* ------------------------------------------------------------------ */
/* Medidor linear com rótulo e valor.                                  */
/* ------------------------------------------------------------------ */

export function Meter({
  label,
  value,
  total,
  color = 'var(--color-accent)',
  hint,
}: {
  label: string;
  value: number;
  total: number;
  color?: string;
  hint?: string;
}) {
  const ratio = total > 0 ? Math.min(100, (value / total) * 100) : null;
  return (
    <div className="space-y-1.5">
      <div className="flex items-baseline justify-between gap-2 text-xs">
        <span className="text-fg-2">{label}</span>
        <span className="font-medium tabular text-fg">
          {ratio === null ? '—' : `${percent(ratio)} · ${integer(value)}/${integer(total)}`}
        </span>
      </div>
      <div
        className="h-1.5 overflow-hidden rounded-full bg-white/[0.06]"
        role="progressbar"
        aria-valuemin={0}
        aria-valuemax={total}
        aria-valuenow={value}
        aria-label={label}
      >
        <div
          className="h-full rounded-full transition-[width] duration-500"
          style={{ width: `${ratio ?? 0}%`, background: color }}
        />
      </div>
      {hint && <p className="text-2xs text-fg-3">{hint}</p>}
    </div>
  );
}

