import { Link } from 'react-router-dom';
import { PageHeader } from '@/components/layout/page-header';
import { Card } from '@/components/ui/card';
import { LinkButton } from '@/components/ui/button';

interface Entry {
  to: string;
  title: string;
  description: string;
}

const TELAS: Entry[] = [
  {
    to: '/revisao',
    title: 'Revisão',
    description: 'Linhas prontas para conferir, com evidência e decisão por campo.',
  },
  {
    to: '/identidades',
    title: 'Identidades',
    description: 'Reconciliar rótulo de cargo e ver conflitos por causa declarada.',
  },
  {
    to: '/mesa',
    title: 'Mesa',
    description: 'Cada concurso × cargo com o estado documental e dos campos decisivos.',
  },
  {
    to: '/pipeline',
    title: 'Pipeline documental',
    description: 'Onde cada documento parou: baixar, extrair e revisar são etapas distintas.',
  },
  {
    to: '/prazos',
    title: 'Prazos',
    description: 'Calendário por evento, com estado operacional e documento de origem.',
  },
  {
    to: '/oportunidades',
    title: 'Oportunidades',
    description: 'Carteira priorizada, com prontidão e filtros por perfil.',
  },
];

const CLI: Entry[] = [
  {
    to: '',
    title: 'Coleta e monitoramento',
    description: 'python -m radar collect / monitorar / confirmacao-lote',
  },
  {
    to: '',
    title: 'Extração e OCR',
    description: 'python -m radar documentos-extrair / ocr-executar / documentos-lote',
  },
  {
    to: '',
    title: 'Fontes e orçamento',
    description: 'python -m radar fontes / fontes-consumo / aquisicao-executar',
  },
  {
    to: '',
    title: 'Prontidão e contrato',
    description: 'python -m radar prontidao / api-contrato --verificar',
  },
];

export function OperationPage() {
  return (
    <>
      <PageHeader
        eyebrow="Sistema"
        title="Diagnóstico"
        description="Atalhos para as telas de trabalho e os comandos que não têm interface. Nada aqui confirma campo automaticamente."
        meta={<span>{TELAS.length} telas · {CLI.length} grupos de comando</span>}
      />

      <div className="mb-3 rounded-md border border-line bg-surface p-3">
        <p className="text-xs text-fg-2">
          A interface antiga (<code className="font-mono text-2xs">/legacy/</code>) foi removida. Tudo o
          que ela fazia em tela está nas páginas abaixo; o que sobrou de operação roda por linha de
          comando, com o mesmo efeito registrado no banco.
        </p>
      </div>

      <h2 className="mb-2 font-display text-sm font-semibold text-fg">Telas</h2>
      <div className="grid gap-2.5 sm:grid-cols-2 xl:grid-cols-3">
        {TELAS.map((entry) => (
          <Card key={entry.to} className="transition-colors hover:border-line-strong">
            <Link to={entry.to} className="block">
              <span className="block text-xs font-medium text-fg transition-colors hover:text-accent">
                {entry.title}
              </span>
              <span className="mt-0.5 block text-2xs leading-snug text-fg-3">
                {entry.description}
              </span>
            </Link>
          </Card>
        ))}
      </div>

      <h2 className="mt-5 mb-2 font-display text-sm font-semibold text-fg">
        Operação por linha de comando
      </h2>
      <div className="grid gap-2.5 sm:grid-cols-2">
        {CLI.map((entry) => (
          <Card key={entry.title}>
            <span className="block text-xs font-medium text-fg">{entry.title}</span>
            <code className="mt-1 block break-words font-mono text-2xs text-fg-2">
              {entry.description}
            </code>
          </Card>
        ))}
      </div>

      <p className="mt-3 text-2xs text-fg-3">
        Comandos rodam no servidor local e gravam no mesmo banco; a interface lê o resultado. Consulte
        o README para a lista completa.
      </p>

      <div className="mt-4">
        <LinkButton to="/revisao" size="sm" variant="primary">
          Ir para a revisão
        </LinkButton>
      </div>
    </>
  );
}
