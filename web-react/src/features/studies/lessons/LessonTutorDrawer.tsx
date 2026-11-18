import { useState } from 'react';
import { Bot, X } from 'lucide-react';
import type { LessonTutorContextual } from '@/lib/types';

type TutorMode = 'explicar_simples' | 'exemplo_pratico' | 'comparar_conceitos' | 'resumo_1_minuto';

const TUTOR_MODES: readonly { key: TutorMode; label: string }[] = [
  { key: 'explicar_simples', label: '1. Explicar de Forma Simples' },
  { key: 'exemplo_pratico', label: '2. Dar Exemplo de Prova' },
  { key: 'comparar_conceitos', label: '3. Comparar Conceitos' },
  { key: 'resumo_1_minuto', label: '4. Resumo de 1 Minuto' },
];

interface LessonTutorDrawerProps {
  open: boolean;
  onClose: () => void;
  tutor?: LessonTutorContextual;
}

export function LessonTutorDrawer({ open, onClose, tutor }: LessonTutorDrawerProps) {
  const [activeMode, setActiveMode] = useState<TutorMode>('explicar_simples');

  if (!open || !tutor) return null;

  return (
    <div className="rounded-2xl border-2 border-amber-400/50 bg-surface p-6 shadow-xl space-y-4">
      <div className="flex items-center justify-between border-b border-line pb-3">
        <div className="flex items-center gap-3">
          <span className="flex size-10 items-center justify-center rounded-xl bg-amber-400 text-slate-950">
            <Bot size={20} />
          </span>
          <div>
            <h3 className="text-base font-extrabold text-fg">Professor Virtual · Explicação Direta da Aula</h3>
            <p className="text-xs text-fg-2">Escolha abaixo como prefere revisar este assunto agora:</p>
          </div>
        </div>
        <button
          type="button"
          onClick={onClose}
          aria-label="Fechar Professor Virtual"
          className="rounded-lg p-1.5 text-fg-3 hover:text-fg"
        >
          <X size={18} />
        </button>
      </div>

      <div className="flex flex-wrap gap-2">
        {TUTOR_MODES.map((mode) => (
          <button
            key={mode.key}
            type="button"
            onClick={() => setActiveMode(mode.key)}
            className={`rounded-xl px-4 py-2 text-xs font-extrabold transition-all ${
              activeMode === mode.key
                ? 'bg-amber-400 text-slate-950'
                : 'border border-line-strong bg-surface-2 text-fg-2 hover:text-fg'
            }`}
          >
            {mode.label}
          </button>
        ))}
      </div>

      <div className="rounded-xl border border-line-strong bg-surface-2 p-4 text-sm text-fg leading-relaxed whitespace-pre-line">
        {tutor[activeMode]}
      </div>
    </div>
  );
}
