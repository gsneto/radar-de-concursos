import { useState } from 'react';
import { Button } from '@/components/ui/button';
import { ModalDialog } from '@/components/ui/dialog';

export const LESSON_DISCIPLINES = [
  { key: '', label: 'Todas as Disciplinas' },
  { key: 'Banco de Dados', label: 'Banco de Dados' },
  { key: 'Engenharia de Software', label: 'Engenharia de Software' },
  { key: 'Redes de Computadores', label: 'Redes de Computadores' },
  { key: 'Segurança da Informação', label: 'Segurança da Informação' },
  { key: 'Língua Portuguesa', label: 'Língua Portuguesa' },
  { key: 'Direito Constitucional', label: 'Direito Constitucional' },
] as const;

export interface CreateCustomLessonInput {
  titulo: string;
  disciplina: string;
  modulo: string;
  teoria_resumida: string;
  objetivos: string[];
}

interface CreateLessonModalProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  onCreateLesson: (payload: CreateCustomLessonInput) => Promise<void>;
}

export function CreateLessonModal({ open, onOpenChange, onCreateLesson }: CreateLessonModalProps) {
  const [title, setTitle] = useState('');
  const [disc, setDisc] = useState('Banco de Dados');
  const [mod, setMod] = useState('Módulo 1: Tópicos Especiais');
  const [summary, setSummary] = useState('');
  const [objective, setObjective] = useState('');
  const [creating, setCreating] = useState(false);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!title.trim() || !disc.trim()) return;
    setCreating(true);
    try {
      await onCreateLesson({
        titulo: title.trim(),
        disciplina: disc.trim(),
        modulo: mod.trim(),
        teoria_resumida: summary.trim() || `Resumo didático estruturado sobre ${title.trim()}.`,
        objetivos: [
          objective.trim() || `Dominar a aplicação prática de ${title.trim()} nas provas.`,
          'Resolver questões reais comentadas com segurança.',
        ],
      });
      onOpenChange(false);
      setTitle('');
      setSummary('');
      setObjective('');
    } finally {
      setCreating(false);
    }
  };

  return (
    <ModalDialog
      open={open}
      onOpenChange={onOpenChange}
      title="Criar Nova Aula Estruturada"
      description="Publique um novo módulo com resumo, quadro visual e flashcards automáticos."
      maxWidthClass="max-w-xl"
    >
      <form onSubmit={handleSubmit} className="space-y-3.5 p-6">
        <div className="grid gap-3 sm:grid-cols-2">
          <div>
            <label className="text-xs font-bold text-fg-2">Disciplina</label>
            <select
              value={disc}
              onChange={(e) => setDisc(e.target.value)}
              className="mt-1 h-10 w-full rounded-xl border border-line-strong bg-surface-2 px-3 text-sm text-fg"
            >
              {LESSON_DISCIPLINES.filter((d) => d.key).map((d) => (
                <option key={d.key} value={d.key}>
                  {d.label}
                </option>
              ))}
            </select>
          </div>
          <div>
            <label className="text-xs font-bold text-fg-2">Módulo</label>
            <input
              type="text"
              value={mod}
              onChange={(e) => setMod(e.target.value)}
              className="mt-1 h-10 w-full rounded-xl border border-line-strong bg-surface-2 px-3 text-sm text-fg"
            />
          </div>
        </div>
        <div>
          <label className="text-xs font-bold text-fg-2">Título da Aula</label>
          <input
            type="text"
            required
            value={title}
            onChange={(e) => setTitle(e.target.value)}
            placeholder="Ex: Aula 03: Índices B-Tree e Otimização de Consultas"
            className="mt-1 h-10 w-full rounded-xl border border-line-strong bg-surface-2 px-3 text-sm text-fg"
          />
        </div>
        <div>
          <label className="text-xs font-bold text-fg-2">Objetivo Principal</label>
          <input
            type="text"
            value={objective}
            onChange={(e) => setObjective(e.target.value)}
            placeholder="Ex: Compreender quando criar índices compostos."
            className="mt-1 h-10 w-full rounded-xl border border-line-strong bg-surface-2 px-3 text-sm text-fg"
          />
        </div>
        <div>
          <label className="text-xs font-bold text-fg-2">Resumo Teórico</label>
          <textarea
            rows={3}
            value={summary}
            onChange={(e) => setSummary(e.target.value)}
            placeholder="Síntese explicativa do conteúdo..."
            className="mt-1 w-full rounded-xl border border-line-strong bg-surface-2 p-3 text-sm text-fg"
          />
        </div>
        <div className="flex justify-end gap-2 pt-2">
          <Button variant="ghost" size="sm" onClick={() => onOpenChange(false)}>
            Cancelar
          </Button>
          <Button variant="primary" size="sm" type="submit" disabled={creating}>
            {creating ? 'Publicando...' : 'Publicar Aula'}
          </Button>
        </div>
      </form>
    </ModalDialog>
  );
}
