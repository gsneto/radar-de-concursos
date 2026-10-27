import { ExternalLink } from 'lucide-react';
import { PageHeader } from '@/components/layout/page-header';
import { Card } from '@/components/ui/card';

const panels: { anchor: string; title: string; description: string }[] = [
  { anchor: 'monitoring-title', title: 'Monitoramento', description: 'Ciclos, fontes e estado do último ciclo.' },
  { anchor: 'alerts-title', title: 'Alertas', description: 'Publicações novas, alterações e falhas de coleta.' },
  { anchor: 'triage-title', title: 'Central de triagem', description: 'O que exige ação hoje, com adiamento e dispensa.' },
  { anchor: 'priorities-title', title: 'Priorização', description: 'Ranking geográfico e por preferências declaradas.' },
  { anchor: 'coverage-title', title: 'Cobertura', description: 'Funil documental e fila de lacunas.' },
  { anchor: 'pipeline-title', title: 'Pipeline documental', description: 'Estado por documento e etapa faltante.' },
  { anchor: 'official-title', title: 'Campos decisivos', description: 'Vagas, prazos, local e conflitos entre versões.' },
  { anchor: 'sources-title', title: 'Catálogo de fontes', description: 'Política de persistência, consumo e revisões.' },
  { anchor: 'review-title', title: 'Revisão humana', description: 'Fila de propostas, lotes e piloto de revisão.' },
  { anchor: 'mesa-title', title: 'Mesa de revisão', description: 'Dossiês por oportunidade e evidência.' },
  { anchor: 'carteira-title', title: 'Carteira', description: 'Matriz de elegibilidade e destaques.' },
  { anchor: 'triagem-title', title: 'Identidades e prazos', description: 'Reconciliação de cargos, conflitos e calendário.' },
  { anchor: 'nominais-title', title: 'Documentos nominais', description: 'Listas nominais e destino proposto.' },
  { anchor: 'timeline-title', title: 'Linha do tempo', description: 'Eventos documentais da base.' },
  { anchor: 'assoc-title', title: 'Associações', description: 'Documento ↔ concurso pendentes de decisão.' },
  { anchor: 'blocked-title', title: 'Bloqueados e ingestão', description: 'Restrição de robots, negativa e importação manual.' },
  { anchor: 'study-title', title: 'Estudos (técnico)', description: 'Disciplinas, cronômetro e revisões no painel antigo.' },
  { anchor: 'prep-title', title: 'Preparação', description: 'Conteúdo programático e perfil de conhecimento.' },
  { anchor: 'practice-title', title: 'Prática', description: 'Flashcards, questões e simulados no painel antigo.' },
];

export function OperationPage() {
  return (
    <>
      <PageHeader
        eyebrow="Sistema"
        title="Operação"
        description="Painéis técnicos preservados. Cada bloco abre a interface operacional completa em uma rota separada; nada aqui confirma campos automaticamente."
        meta={<span>Rota legada: /legacy/ · 19 blocos</span>}
      />

      <div className="mb-3 rounded-md border border-line bg-surface p-3">
        <p className="text-xs text-fg-2">
          A Operação mantém a interface original (HTML/CSS/JS da Fase 45) intacta, com todos os
          controles de revisão, coleta e diagnóstico. O novo app React não reimplementa esses fluxos
          para não arriscar comportamento.
        </p>
        <a
          href="/legacy/"
          className="mt-2 inline-flex h-8 items-center gap-1.5 rounded-sm bg-accent px-3 text-xs font-medium text-fg-inverse transition-colors hover:bg-accent-hover"
        >
          Abrir Operação completa <ExternalLink size={12} />
        </a>
      </div>

      <div className="grid gap-2.5 sm:grid-cols-2 xl:grid-cols-3">
        {panels.map((panel) => (
          <Card key={panel.anchor} className="transition-colors hover:border-line-strong">
            <a
              href={`/legacy/#${panel.anchor}`}
              className="group flex items-start justify-between gap-2"
            >
              <span className="min-w-0">
                <span className="block text-xs font-medium text-fg transition-colors group-hover:text-accent">
                  {panel.title}
                </span>
                <span className="mt-0.5 block text-2xs leading-snug text-fg-3">{panel.description}</span>
              </span>
              <ExternalLink size={12} className="mt-0.5 shrink-0 text-fg-3 transition-colors group-hover:text-accent" />
            </a>
          </Card>
        ))}
      </div>
    </>
  );
}
