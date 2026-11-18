import { AlertCircle, ArrowRight, Award, Flame } from 'lucide-react';
import { Button } from '@/components/ui/button';
import type { LessonDetail } from '@/lib/types';

/** Divide a teoria em blocos numerados com títulos claros para eliminar "paredes de texto" */
export function parseStructuredTheory(raw: string): { title: string; body: string }[] {
  const paragraphs = raw
    .trim()
    .split(/\n\s*\n/)
    .map((p) => p.trim())
    .filter(Boolean);

  return paragraphs.map((p, idx) => {
    const clean = p.replace(/\*\*/g, '');
    const firstColon = clean.indexOf(':');
    if (firstColon > 0 && firstColon < 65) {
      return {
        title: clean.slice(0, firstColon).replace(/^[-•]\s*/, '').trim(),
        body: clean.slice(firstColon + 1).trim(),
      };
    }
    const titles = [
      'Visão Geral e Conceito Base',
      'Regras Fundamentais Cobradas em Prova',
      'Diferenciação Técnica e Aplicações',
      'Síntese Estratégica de Resolução',
    ];
    return {
      title: titles[idx % titles.length],
      body: clean,
    };
  });
}

interface LessonTheoryStageProps {
  lesson: LessonDetail;
  onNextStage: () => void;
}

export function LessonTheoryStage({ lesson, onNextStage }: LessonTheoryStageProps) {
  const rawTheory =
    lesson.teoria_resumida ||
    (lesson as unknown as { conteudo_resumo?: string }).conteudo_resumo ||
    '';
  const blocks = parseStructuredTheory(rawTheory);
  const bancas =
    lesson.radiografia_bancas ??
    (lesson as unknown as { bancas_destaque?: Record<string, string> }).bancas_destaque ??
    {};
  const criticalPoints = lesson.pontos_criticos ?? [];

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-center justify-between gap-3 rounded-2xl border-l-4 border-l-amber-400 border border-line-strong bg-surface p-5">
        <div>
          <span className="text-xs font-black uppercase tracking-widest text-accent-ink">
            ETAPA 1 DE 5 · BASE TEÓRICA ESQUEMATIZADA
          </span>
          <h2 className="mt-1 font-display text-xl font-extrabold text-fg">
            O que você precisa saber antes de ir para os exercícios
          </h2>
        </div>
        <Button variant="primary" size="sm" onClick={onNextStage} className="gap-1.5 font-extrabold">
          <span>Ir para Etapa 2: Quadro Digital</span>
          <ArrowRight size={14} />
        </Button>
      </div>

      <div className="grid gap-4 md:grid-cols-2">
        {blocks.map((block, idx) => (
          <div key={idx} className="rounded-2xl border border-line-strong bg-surface p-6 shadow-sm space-y-3">
            <div className="flex items-center gap-3">
              <span className="flex size-8 shrink-0 items-center justify-center rounded-lg bg-amber-400 text-sm font-black text-slate-950">
                0{idx + 1}
              </span>
              <h3 className="font-display text-base sm:text-lg font-extrabold text-fg">{block.title}</h3>
            </div>
            <p className="text-sm text-fg leading-relaxed whitespace-pre-line">{block.body}</p>
          </div>
        ))}
      </div>

      {lesson.tabela_resumo && (
        <div className="rounded-2xl border border-line-strong bg-surface overflow-hidden shadow-md">
          <div className="border-b border-line bg-surface-2 px-6 py-4">
            <span className="text-xs font-black uppercase tracking-wider text-accent-ink">
              TABELA DE COMPARAÇÃO RÁPIDA
            </span>
            <h3 className="mt-0.5 font-display text-lg font-extrabold text-fg">
              {lesson.tabela_resumo.titulo}
            </h3>
          </div>
          <div className="overflow-x-auto">
            <table className="w-full text-left border-collapse">
              <thead>
                <tr className="border-b-2 border-line bg-surface-2/60">
                  {lesson.tabela_resumo.colunas.map((col, idx) => (
                    <th
                      key={idx}
                      className="px-5 py-3.5 text-xs font-extrabold uppercase tracking-wider text-accent-ink"
                    >
                      {col}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody className="divide-y divide-line">
                {lesson.tabela_resumo.linhas.map((row, rIdx) => (
                  <tr key={rIdx} className="hover:bg-surface-2/40">
                    {row.map((cell, cIdx) => (
                      <td
                        key={cIdx}
                        className={`px-5 py-3.5 text-sm leading-relaxed ${
                          cIdx === 0 ? 'font-extrabold text-accent-ink' : 'text-fg'
                        }`}
                      >
                        {cell}
                      </td>
                    ))}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}

      <div className="grid gap-5 lg:grid-cols-2">
        <div className="rounded-2xl border-2 border-rose-500/30 bg-surface p-6 space-y-4">
          <div className="flex items-center gap-2.5">
            <span className="flex size-8 items-center justify-center rounded-lg bg-rose-500/20 text-risk-ink">
              <Flame size={18} />
            </span>
            <div>
              <span className="text-xs font-black uppercase tracking-wider text-risk-ink">
                CUIDADO NA PROVA
              </span>
              <h3 className="font-display text-lg font-extrabold text-fg">
                3 Pegadinhas Clássicas deste Assunto
              </h3>
            </div>
          </div>
          <ul className="space-y-3">
            {criticalPoints.map((ponto, idx) => (
              <li
                key={idx}
                className="flex items-start gap-3 rounded-xl border border-rose-500/25 bg-rose-500/10 p-3.5 text-sm text-fg leading-relaxed"
              >
                <AlertCircle size={16} className="text-risk-ink shrink-0 mt-0.5" />
                <span>{ponto}</span>
              </li>
            ))}
          </ul>
        </div>

        <div className="rounded-2xl border border-line-strong bg-surface p-6 space-y-4">
          <div className="flex items-center gap-2.5">
            <span className="flex size-8 items-center justify-center rounded-lg bg-amber-400/20 text-accent-ink">
              <Award size={18} />
            </span>
            <div>
              <span className="text-xs font-black uppercase tracking-wider text-accent-ink">
                RAIO-X DAS BANCAS
              </span>
              <h3 className="font-display text-lg font-extrabold text-fg">
                Como FGV, Cebraspe e Quadrix Cobram
              </h3>
            </div>
          </div>
          <div className="space-y-3">
            {Object.entries(bancas).map(([banca, analise]) => (
              <div key={banca} className="rounded-xl border border-line-strong bg-surface-2 p-3.5 space-y-1">
                <span className="inline-block rounded bg-amber-400/20 px-2 py-0.5 text-xs font-black uppercase text-accent-ink">
                  Banca {banca.toUpperCase()}
                </span>
                <p className="text-sm text-fg leading-relaxed">{analise}</p>
              </div>
            ))}
          </div>
        </div>
      </div>
    </div>
  );
}
