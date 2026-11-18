import { useState } from 'react';
import { ArrowRight } from 'lucide-react';
import { Button } from '@/components/ui/button';
import type { LessonDetail } from '@/lib/types';

interface LessonVisualStageProps {
  lesson: LessonDetail;
  onNextStage: () => void;
}

export function LessonVisualStage({ lesson, onNextStage }: LessonVisualStageProps) {
  const [activeVisualStep, setActiveVisualStep] = useState(0);
  const [selectedMindMapNodeId, setSelectedMindMapNodeId] = useState<string | null>(null);

  const steps = lesson.quadro_visual?.passos_animados ?? [];
  const activeStep = steps[activeVisualStep] ?? steps[0];
  const mindMapNodes = lesson.mapa_mental?.nos ?? [];
  const activeNode = mindMapNodes.find((n) => n.id === selectedMindMapNodeId) ?? mindMapNodes[0];

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-center justify-between gap-3 rounded-2xl border-l-4 border-l-sky-400 border border-line-strong bg-surface p-5">
        <div>
          <span className="text-xs font-black uppercase tracking-widest text-info-ink">
            ETAPA 2 DE 5 · ESQUEMA VISUAL & MAPA INTERATIVO
          </span>
          <h2 className="mt-1 font-display text-xl font-extrabold text-fg">
            {lesson.quadro_visual?.titulo || 'Quadro Digital Esquematizado'}
          </h2>
        </div>
        <Button variant="primary" size="sm" onClick={onNextStage} className="gap-1.5 font-extrabold">
          <span>Ir para Etapa 3: Videoaula</span>
          <ArrowRight size={14} />
        </Button>
      </div>

      {lesson.quadro_visual && (lesson.quadro_visual.relacoes_conceituais ?? []).length > 0 && (
        <div className="grid gap-5 lg:grid-cols-3">
          {lesson.quadro_visual.relacoes_conceituais.map((rel, rIdx) => (
            <div
              key={rel.id}
              className="flex flex-col justify-between rounded-2xl border-2 border-line-strong bg-surface p-5 shadow-md space-y-4"
            >
              <div className="space-y-3">
                <div className="flex items-center justify-between">
                  <span className="rounded-lg bg-amber-400 px-3 py-1 text-xs font-black uppercase tracking-wider text-slate-950">
                    {rel.categoria}
                  </span>
                  <span className="text-xs font-extrabold text-fg-3">Bloco #{rIdx + 1}</span>
                </div>

                <div className="flex flex-wrap gap-1.5 pt-1">
                  {rel.conectivos.map((c) => (
                    <span
                      key={c}
                      className="rounded-lg border border-amber-400/40 bg-amber-400/10 px-2.5 py-1 text-xs font-bold text-accent-ink"
                    >
                      {c}
                    </span>
                  ))}
                </div>

                <div className="rounded-xl border border-line-strong bg-surface-2 p-3.5">
                  <span className="block text-[10px] font-black uppercase tracking-wider text-info-ink mb-1">
                    DEFINIÇÃO DIRETA
                  </span>
                  <p className="text-sm font-bold text-fg leading-relaxed">{rel.regra_ouro}</p>
                </div>
              </div>

              <div className="rounded-xl border border-emerald-500/30 bg-emerald-500/10 p-3.5">
                <span className="block text-[10px] font-black uppercase tracking-wider text-ok-ink mb-1">
                  COMO CAI NA PROVA
                </span>
                <p className="text-xs font-medium text-fg leading-relaxed">{rel.exemplo_destacado}</p>
              </div>
            </div>
          ))}
        </div>
      )}

      {steps.length > 0 && activeStep && (
        <div className="rounded-2xl border border-line-strong bg-surface p-6 space-y-4">
          <div className="flex flex-wrap items-center justify-between gap-2">
            <div>
              <span className="text-xs font-black uppercase tracking-wider text-accent-ink">
                RACIOCÍNIO PASSO A PASSO
              </span>
              <h3 className="font-display text-lg font-extrabold text-fg">
                Como resolver qualquer questão deste tema em 3 passos
              </h3>
            </div>
            <div className="flex items-center gap-1.5">
              {steps.map((st, idx) => (
                <button
                  key={st.passo}
                  type="button"
                  onClick={() => setActiveVisualStep(idx)}
                  className={`rounded-xl px-3.5 py-2 text-xs font-extrabold transition-all ${
                    activeVisualStep === idx
                      ? 'bg-amber-400 text-slate-950'
                      : 'border border-line-strong bg-surface-2 text-fg-2 hover:text-fg'
                  }`}
                >
                  Passo {st.passo}
                </button>
              ))}
            </div>
          </div>

          <div className="rounded-xl border border-amber-400/40 bg-surface-2 p-5 space-y-3">
            <h4 className="font-display text-base sm:text-lg font-extrabold text-accent-ink">
              {activeStep.titulo}
            </h4>
            <p className="text-sm text-fg leading-relaxed">{activeStep.detalhe}</p>
            <div className="rounded-lg border border-line-strong bg-surface p-3 font-mono text-xs font-bold text-ok-ink">
              {activeStep.destaque_codigo}
            </div>
          </div>
        </div>
      )}

      {lesson.mapa_mental && mindMapNodes.length > 0 && (
        <div className="rounded-2xl border border-line-strong bg-surface p-6 space-y-4">
          <div>
            <span className="text-xs font-black uppercase tracking-wider text-info-ink">
              MAPA MENTAL INTERATIVO
            </span>
            <h3 className="font-display text-lg font-extrabold text-fg">
              Clique em qualquer ramo abaixo para expandir os detalhes
            </h3>
          </div>

          <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
            {mindMapNodes.map((node) => {
              const isSelected = selectedMindMapNodeId === node.id;
              return (
                <button
                  key={node.id}
                  type="button"
                  onClick={() => setSelectedMindMapNodeId(isSelected ? null : node.id)}
                  className={`text-left rounded-xl border-2 p-4 transition-all ${
                    isSelected
                      ? 'border-amber-400 bg-amber-400/10'
                      : 'border-line-strong bg-surface-2 hover:border-amber-400/50'
                  }`}
                >
                  <span className="text-xs font-black uppercase text-accent-ink block">{node.titulo}</span>
                  <p className="mt-1 text-xs text-fg-2 line-clamp-2">{node.descricao}</p>
                </button>
              );
            })}
          </div>

          {activeNode && (
            <div className="rounded-xl border border-line-strong bg-surface-2 p-5 grid gap-4 md:grid-cols-3">
              <div>
                <span className="text-[11px] font-black uppercase text-accent-ink">CONCEITO SELECIONADO</span>
                <h4 className="mt-1 font-display text-base font-extrabold text-fg">{activeNode.titulo}</h4>
                <p className="mt-1 text-xs text-fg-2 leading-relaxed">{activeNode.descricao}</p>
              </div>
              <div>
                <span className="text-[11px] font-black uppercase text-ok-ink">APLICAÇÃO PRÁTICA</span>
                <p className="mt-1 text-xs text-fg leading-relaxed">{activeNode.exemplo}</p>
              </div>
              <div>
                <span className="text-[11px] font-black uppercase text-risk-ink">DICA DE BANCA</span>
                <p className="mt-1 text-xs text-fg leading-relaxed">{activeNode.dica_banca}</p>
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
