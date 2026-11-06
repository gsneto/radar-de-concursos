import { useEffect, useRef, useState } from 'react';
import type { CSSProperties, MouseEvent, ReactNode } from 'react';
import { GlowCard } from './glow-card';
import { cn } from '@/lib/cn';

type LineType = 'cmd' | 'ok' | 'info' | 'url';

interface TermLine {
  type: LineType;
  text: string;
}

const SERIES_LENGTH = 36;
const TICK_MS = 1400;

const BANCAS = [
  { name: 'FGV Conhecimento', base: 28 },
  { name: 'Cebraspe Oficial', base: 35 },
  { name: 'Quadrix CDN', base: 42 },
  { name: 'DOU Seção 3', base: 54 },
  { name: 'IBFC Seleção', base: 63 },
];

const SCRIPT: TermLine[] = [
  { type: 'cmd', text: 'radar ops-ciclo --auto' },
  { type: 'info', text: 'Conectando às fontes oficiais autorizadas…' },
  { type: 'ok', text: 'FGV: 109 certames monitorados' },
  { type: 'ok', text: 'Cebraspe: catálogo e retificações atualizados' },
  { type: 'cmd', text: 'radar curadoria-autonoma' },
  { type: 'info', text: 'Auditando compatibilidade com Sistemas de Informação…' },
  { type: 'ok', text: '822 decisões registradas com evidência SHA-256' },
  { type: 'ok', text: '471 cargos reconciliados sem intervenção humana' },
  { type: 'ok', text: 'Prazos operacionais recalculados para Paulo Afonso' },
  { type: 'url', text: 'http://127.0.0.1:8000 (Loopback Ativo)' },
];

const TERM_VISIBLE = 9;
const LINE_STYLES: Record<LineType, { mark: string; markClass: string; textClass: string }> = {
  cmd: { mark: '$', markClass: 'text-fuchsia-400 font-bold', textClass: 'text-slate-100 font-medium' },
  ok: { mark: '✓', markClass: 'text-emerald-400 font-bold', textClass: 'text-slate-300' },
  info: { mark: '›', markClass: 'text-slate-500 font-bold', textClass: 'text-slate-400' },
  url: { mark: '●', markClass: 'text-cyan-400 font-bold', textClass: 'text-cyan-300 underline underline-offset-2' },
};

const METRICAS = [
  { label: 'Evidência', score: 100 },
  { label: 'SHA-256', score: 100 },
  { label: 'Auditado', score: 98 },
  { label: 'SI / TI', score: 100 },
];

const clamp = (n: number, min: number, max: number) => Math.min(Math.max(n, min), max);

function useAnimatedNumber(target: number, duration = 600): number {
  const [value, setValue] = useState(target);
  const current = useRef(target);

  useEffect(() => {
    if (typeof window !== 'undefined' && typeof window.matchMedia === 'function' && window.matchMedia('(prefers-reduced-motion: reduce)')?.matches) {
      current.current = target;
      setValue(target);
      return;
    }
    const from = current.current;
    const start = performance.now();
    let frame = 0;

    const tick = (now: number) => {
      const t = Math.min((now - start) / duration, 1);
      const eased = 1 - Math.pow(1 - t, 3);
      current.current = from + (target - from) * eased;
      setValue(current.current);
      if (t < 1) frame = requestAnimationFrame(tick);
    };

    frame = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(frame);
  }, [target, duration]);

  return value;
}

function initialSeries(): number[] {
  return Array.from({ length: SERIES_LENGTH }, (_, i) => 38 + Math.sin(i * 0.6) * 10 + ((i * 17) % 8));
}

function toSmoothPath(points: Array<{ x: number; y: number }>): string {
  return points.reduce((d, p, i) => {
    if (i === 0) return `M ${p.x} ${p.y}`;
    const prev = points[i - 1];
    const mid = (prev.x + p.x) / 2;
    return `${d} C ${mid} ${prev.y}, ${mid} ${p.y}, ${p.x} ${p.y}`;
  }, '');
}

const statusOf = (ms: number) =>
  ms < 45
    ? { dot: 'bg-emerald-400', text: 'text-emerald-300' }
    : ms < 75
    ? { dot: 'bg-cyan-400', text: 'text-cyan-300' }
    : { dot: 'bg-amber-400', text: 'text-amber-300' };

function CardTitle({ children, right }: { children: ReactNode; right?: ReactNode }) {
  return (
    <div className="mb-3 flex items-center justify-between gap-3">
      <h3 className="text-xs font-semibold tracking-wider text-slate-300 uppercase">{children}</h3>
      {right}
    </div>
  );
}

function LiveBadge() {
  return (
    <span className="flex items-center gap-1.5 text-[11px] font-medium text-emerald-300">
      <span className="tb-pulse h-1.5 w-1.5 rounded-full bg-emerald-400 shadow-[0_0_8px_#34d399]" />
      Ao vivo
    </span>
  );
}

function LatencyCard() {
  const [series, setSeries] = useState<number[]>(initialSeries);
  const [pings, setPings] = useState<number[]>(() => BANCAS.map((r) => r.base));
  const [hover, setHover] = useState<number | null>(null);

  useEffect(() => {
    const id = window.setInterval(() => {
      setSeries((prev) => [...prev.slice(1), clamp(prev[prev.length - 1] + (Math.random() - 0.5) * 12, 18, 75)]);
      setPings(BANCAS.map((r) => Math.round(clamp(r.base + (Math.random() - 0.5) * 10, 15, 95))));
    }, TICK_MS);
    return () => window.clearInterval(id);
  }, []);

  const latest = Math.round(series[series.length - 1]);
  const average = Math.round(series.reduce((a, b) => a + b, 0) / series.length);
  const peak = Math.round(Math.max(...series));
  const animatedLatest = useAnimatedNumber(latest, 500);

  const points = series.map((v, i) => ({
    x: (i / (series.length - 1)) * 100,
    y: 95 - (v / 85) * 85,
  }));
  const line = toSmoothPath(points);
  const area = `${line} L 100 100 L 0 100 Z`;
  const shown = hover ?? series.length - 1;

  const handleChartMove = (e: MouseEvent<HTMLDivElement>) => {
    const rect = e.currentTarget.getBoundingClientRect();
    const ratio = clamp((e.clientX - rect.left) / rect.width, 0, 1);
    setHover(Math.round(ratio * (series.length - 1)));
  };

  return (
    <GlowCard accent="indigo" className="min-h-[380px] sm:col-span-2 lg:row-span-2">
      <CardTitle right={<LiveBadge />}>Latência das Bancas Oficiais</CardTitle>

      <div className="mb-3 flex flex-wrap items-end gap-x-5 gap-y-2">
        <div className="flex items-end gap-1.5">
          <span className="text-4xl font-semibold leading-none tracking-tight text-white [font-variant-numeric:tabular-nums]">
            {Math.round(animatedLatest)}
          </span>
          <span className="mb-0.5 text-xs text-slate-400">ms resposta</span>
        </div>
        <div className="mb-0.5 flex gap-3 text-xs text-slate-400">
          <span>
            média <b className="font-medium text-slate-200">{average}ms</b>
          </span>
          <span>
            pico <b className="font-medium text-slate-200">{peak}ms</b>
          </span>
        </div>
      </div>

      <div
        className="relative min-h-[120px] flex-1 cursor-crosshair"
        onMouseMove={handleChartMove}
        onMouseLeave={() => setHover(null)}
      >
        <svg
          viewBox="0 0 100 100"
          preserveAspectRatio="none"
          className="absolute inset-0 h-full w-full overflow-visible"
          role="img"
          aria-label="Latência das bancas oficiais"
        >
          <defs>
            <linearGradient id="tb-lat-fill" x1="0" y1="0" x2="0" y2="1">
              <stop offset="0%" stopColor="#818cf8" stopOpacity="0.3" />
              <stop offset="100%" stopColor="#818cf8" stopOpacity="0" />
            </linearGradient>
          </defs>

          {[25, 50, 75].map((y) => (
            <line
              key={y}
              x1="0"
              x2="100"
              y1={y}
              y2={y}
              stroke="rgba(255,255,255,0.06)"
              strokeDasharray="3 4"
              vectorEffect="non-scaling-stroke"
            />
          ))}

          <path d={area} fill="url(#tb-lat-fill)" />
          <path
            d={line}
            fill="none"
            stroke="#a5b4fc"
            strokeWidth="2.5"
            strokeLinecap="round"
            vectorEffect="non-scaling-stroke"
            style={{ filter: 'drop-shadow(0 0 6px rgba(129,140,248,0.7))' }}
          />

          {hover !== null && (
            <line
              x1={points[hover].x}
              x2={points[hover].x}
              y1="0"
              y2="100"
              stroke="rgba(165,180,252,0.45)"
              strokeDasharray="3 3"
              vectorEffect="non-scaling-stroke"
            />
          )}
        </svg>

        <span
          aria-hidden="true"
          className="pointer-events-none absolute h-2.5 w-2.5 -translate-x-1/2 -translate-y-1/2 rounded-full border-2 border-indigo-200 bg-indigo-500 shadow-[0_0_10px_rgba(129,140,248,0.9)]"
          style={{ left: `${points[shown].x}%`, top: `${points[shown].y}%` }}
        />
        {hover !== null && (
          <div
            aria-hidden="true"
            className="pointer-events-none absolute -translate-x-1/2 -translate-y-full whitespace-nowrap rounded-lg border border-white/10 bg-[#161a2b]/95 px-2 py-1 text-xs shadow-xl backdrop-blur-md"
            style={{
              left: `clamp(48px, ${points[hover].x}%, calc(100% - 48px))`,
              top: `calc(${points[hover].y}% - 12px)`,
            }}
          >
            <div className="text-[10px] text-slate-400">
              {Math.round(((series.length - 1 - hover) * TICK_MS) / 1000)}s atrás
            </div>
            <div className="font-semibold text-white">{Math.round(series[hover])} ms</div>
          </div>
        )}
      </div>

      <ul className="mt-4 grid grid-cols-1 gap-x-4 gap-y-1 sm:grid-cols-2">
        {BANCAS.map((banca, i) => {
          const status = statusOf(pings[i]);
          return (
            <li
              key={banca.name}
              className="flex items-center gap-2.5 rounded-lg px-2 py-1 text-xs transition-colors hover:bg-white/[0.04]"
            >
              <span className={cn('h-2 w-2 shrink-0 rounded-full', status.dot)} />
              <span className="flex-1 truncate text-slate-300">{banca.name}</span>
              <span className={cn('font-mono text-2xs', status.text)}>{pings[i]} ms</span>
            </li>
          );
        })}
      </ul>
    </GlowCard>
  );
}

function TerminalCard() {
  const [step, setStep] = useState(1);

  useEffect(() => {
    const id = window.setInterval(() => {
      setStep((s) => (s >= SCRIPT.length + 3 ? 1 : s + 1));
    }, 950);
    return () => window.clearInterval(id);
  }, []);

  const printed = Math.min(step, SCRIPT.length);
  const first = Math.max(0, printed - TERM_VISIBLE);
  const visible = SCRIPT.slice(first, printed);

  return (
    <GlowCard accent="fuchsia" className="min-h-[320px] sm:col-span-2 lg:col-span-1 lg:row-span-2">
      <CardTitle
        right={
          <span className="flex items-center gap-1.5" aria-hidden="true">
            <span className="h-2 w-2 rounded-full bg-rose-400/80" />
            <span className="h-2 w-2 rounded-full bg-amber-400/80" />
            <span className="h-2 w-2 rounded-full bg-emerald-400/80" />
          </span>
        }
      >
        ciclo-radar.log
      </CardTitle>

      <div
        className="flex flex-1 flex-col justify-end gap-1.5 overflow-hidden rounded-xl border border-white/5 bg-black/40 p-3 font-mono text-[11px] leading-relaxed"
        aria-label="Log operacional do Radar"
        role="log"
      >
        {visible.map((line, i) => {
          const style = LINE_STYLES[line.type];
          const isLast = first + i === printed - 1;
          return (
            <div key={first + i} className="tb-slide flex gap-2">
              <span className={cn('w-3 shrink-0 text-center', style.markClass)}>{style.mark}</span>
              <span className={cn('min-w-0 break-words', style.textClass)}>
                {line.text}
                {isLast && printed < SCRIPT.length && (
                  <span className="tb-blink ml-1 inline-block h-2.5 w-1.5 translate-y-0.5 bg-fuchsia-300" />
                )}
              </span>
            </div>
          );
        })}
      </div>
    </GlowCard>
  );
}

function LighthouseCard() {
  const radius = 18;
  const circumference = 2 * Math.PI * radius;

  return (
    <GlowCard accent="emerald" className="min-h-[180px]">
      <CardTitle>Integridade de Dados</CardTitle>

      <div className="flex flex-1 items-center justify-between gap-1">
        {METRICAS.map((item) => (
          <div key={item.label} className="group flex flex-col items-center gap-1.5">
            <div className="relative h-12 w-12">
              <svg viewBox="0 0 46 46" className="h-full w-full -rotate-90" aria-hidden="true">
                <circle cx="23" cy="23" r={radius} fill="none" stroke="rgba(255,255,255,0.08)" strokeWidth="3.5" />
                <circle
                  cx="23"
                  cy="23"
                  r={radius}
                  fill="none"
                  stroke="#34d399"
                  strokeWidth="3.5"
                  strokeLinecap="round"
                  strokeDasharray={circumference}
                  className="tb-ring transition-[filter] duration-300 group-hover:[filter:drop-shadow(0_0_6px_#34d399)]"
                  style={
                    {
                      '--from': `${circumference}`,
                      '--to': `${circumference * (1 - item.score / 100)}`,
                    } as CSSProperties
                  }
                />
              </svg>
              <span className="absolute inset-0 flex items-center justify-center font-mono text-xs font-semibold text-white">
                {item.score}%
              </span>
            </div>
            <span className="text-[10px] font-medium text-slate-400">{item.label}</span>
          </div>
        ))}
      </div>
    </GlowCard>
  );
}

function ThroughputCard() {
  const [bars, setBars] = useState<number[]>(() =>
    Array.from({ length: 16 }, (_, i) => 820 + Math.sin(i * 0.8) * 15 + ((i * 13) % 4) * 3),
  );

  useEffect(() => {
    const id = window.setInterval(() => {
      setBars((prev) => [...prev.slice(1), clamp(prev[prev.length - 1] + (Math.random() - 0.48) * 8, 800, 860)]);
    }, TICK_MS);
    return () => window.clearInterval(id);
  }, []);

  const latest = bars[bars.length - 1];
  const animated = useAnimatedNumber(latest, 600);
  const max = Math.max(...bars, 860);

  return (
    <GlowCard accent="cyan" className="min-h-[180px]">
      <CardTitle right={<LiveBadge />}>Certames Mapeados</CardTitle>

      <div className="text-3xl font-semibold leading-none tracking-tight text-white font-mono">
        {Math.round(animated)}
        <span className="ml-2 text-xs font-normal text-slate-400">concursos ativos</span>
      </div>

      <div className="mt-auto flex h-10 items-end gap-1 pt-2" aria-hidden="true">
        {bars.map((v, i) => (
          <span
            key={i}
            className={cn(
              'flex-1 rounded-xs transition-all duration-700 ease-out',
              i === bars.length - 1 ? 'bg-cyan-300 shadow-[0_0_10px_rgba(103,232,249,0.8)]' : 'bg-cyan-400/30',
            )}
            style={{ height: `${Math.max(((v - 750) / (max - 750)) * 100, 15)}%` }}
          />
        ))}
      </div>
    </GlowCard>
  );
}

export function RadarBento() {
  return (
    <>
      <style>{`
        @keyframes tb-pulse { 0%, 100% { opacity: 1; } 50% { opacity: 0.3; } }
        .tb-pulse { animation: tb-pulse 1.6s ease-in-out infinite; }
        @keyframes tb-slide {
          from { opacity: 0; transform: translateY(6px); }
          to { opacity: 1; transform: translateY(0); }
        }
        .tb-slide { animation: tb-slide 0.3s ease both; }
        @keyframes tb-blink { 0%, 100% { opacity: 1; } 50% { opacity: 0; } }
        .tb-blink { animation: tb-blink 1s steps(2, start) infinite; }
        @keyframes tb-ring { from { stroke-dashoffset: var(--from); } to { stroke-dashoffset: var(--to); } }
        .tb-ring { animation: tb-ring 1.2s cubic-bezier(0.4, 0, 0.2, 1) both; }
        @media (prefers-reduced-motion: reduce) {
          .tb-pulse, .tb-slide, .tb-blink, .tb-ring { animation: none; }
        }
      `}</style>

      <section className="w-full my-6">
        <div className="mb-4">
          <p className="text-[10px] font-semibold uppercase tracking-[0.18em] text-accent">Telemetria & Monitoramento</p>
          <h2 className="text-xl font-bold tracking-tight text-white">
            Operação Autônoma das Bancas em Tempo Real
          </h2>
          <p className="mt-1 text-xs text-fg-3">
            Status ao vivo de coleta, integridade documental e curadoria determinística contínua.
          </p>
        </div>

        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:auto-rows-[190px] lg:grid-cols-4">
          <LatencyCard />
          <TerminalCard />
          <LighthouseCard />
          <ThroughputCard />
        </div>
      </section>
    </>
  );
}
export default RadarBento;
