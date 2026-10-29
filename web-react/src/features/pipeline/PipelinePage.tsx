import { useMemo, useState } from 'react';
import { Link } from 'react-router-dom';
import { usePipelineCoverage, usePipelineDocuments, usePipelineSummary } from '@/app/queries';
import { PageHeader } from '@/components/layout/page-header';
import { Badge, type Tone } from '@/components/ui/badge';
import { Card } from '@/components/ui/card';
import { Kpi, NumberTicker } from '@/components/ui/kpi';
import { EmptyState, ErrorState, SkeletonRows } from '@/components/ui/states';
import { integer, percentOf, truncate } from '@/lib/format';
import type { PipelineDocument } from '@/lib/types';

const STAGES = ['descoberto', 'baixado', 'validado', 'classificado', 'extraido'] as const;

const BLOCKER_LABELS: Record<string, string> = {
  sem_versao: 'Sem versão baixada',
  nao_iniciada: 'Extração não iniciada',
  sem_texto: 'PDF sem camada de texto',
  falhou: 'Extração falhou',
  sem_propostas: 'Texto sem propostas',
  associacao_pendente: 'Associação pendente',
  pronto_para_revisao: 'Pronto para revisão',
};

const CATEGORY_LABELS: Record<string, string> = {
  campo_confirmado: 'Campo confirmado',
  proposta_sem_campo_decisivo: 'Proposta sem campo decisivo',
  campo_candidato: 'Campo candidato',
  texto_sem_campo: 'Texto sem campo',
  documento_nao_extraido: 'Documento não extraído',
  documento_sem_texto: 'Documento sem texto',
  sem_documento: 'Sem documento',
};

const blockerTone = (blocker: string | null): Tone => {
  if (!blocker) return 'neutral';
  if (blocker === 'pronto_para_revisao') return 'ok';
  if (blocker === 'falhou' || blocker === 'sem_texto') return 'risk';
  if (blocker === 'associacao_pendente') return 'warn';
  return 'neutral';
};

function StageTrail({ stages }: { stages: string[] }) {
  const reached = new Set(stages);
  return (
    <ol className="flex flex-wrap items-center gap-1" aria-label="Etapas do documento">
      {STAGES.map((stage, index) => {
        const done = reached.has(stage);
        return (
          <li key={stage} className="flex items-center gap-1">
            {index > 0 && <span aria-hidden className="text-fg-3">›</span>}
            <span
              className={
                'rounded-xs px-1.5 py-0.5 text-[10px] ' +
                (done ? 'bg-ok-soft text-ok' : 'bg-white/[0.04] text-fg-3')
              }
            >
              {stage}
            </span>
          </li>
        );
      })}
    </ol>
  );
}

function DocumentCard({ document }: { document: PipelineDocument }) {
  return (
    <li className="border-t border-line/70 px-4 py-3 first:border-t-0">
      <div className="flex flex-wrap items-start justify-between gap-2">
        <div className="min-w-0">
          <p className="truncate text-[13px] font-medium text-fg">
            {document.title ?? 'Documento sem título'}
          </p>
          <p className="mt-0.5 truncate text-2xs text-fg-3">
            {document.tipo_documental ?? document.kind ?? 'tipo não classificado'}
            {document.issuer ? ` · ${document.issuer}` : ''}
            {document.source_identifier ? ` · ${document.source_identifier}` : ''}
          </p>
        </div>
        <Badge tone={blockerTone(document.blocked_at)}>
          {BLOCKER_LABELS[document.blocked_at ?? ''] ?? document.blocked_at ?? 'sem bloqueio'}
        </Badge>
      </div>

      <div className="mt-2">
        <StageTrail stages={document.stages} />
      </div>

      <p className="mt-1.5 text-2xs text-fg-3">
        {integer(document.versions)} versão(ões) · {integer(document.blocks)} bloco(s) ·{' '}
        {integer(document.proposals)} proposta(s)
        {document.last_extraction_state ? ` · extração ${document.last_extraction_state}` : ''}
        {document.blocked_reason ? ` · ${document.blocked_reason}` : ''}
      </p>

      <div className="mt-1.5 flex flex-wrap gap-3 text-2xs">
        <Link
          to={`/dossie/${document.contest_id}`}
          className="font-medium text-accent hover:underline"
        >
          Abrir dossiê
        </Link>
        {document.official_url && (
          <a
            href={document.official_url}
            target="_blank"
            rel="noreferrer noopener"
            className="font-medium text-accent hover:underline"
          >
            Abrir documento oficial
          </a>
        )}
      </div>
    </li>
  );
}

export function PipelinePage() {
  const [pending, setPending] = useState(true);
  const [contestId, setContestId] = useState('');

  const summary = usePipelineSummary();
  const coverage = usePipelineCoverage(500);
  const documents = usePipelineDocuments({
    pending,
    contestId: contestId.trim() || undefined,
    limit: 100,
  });

  const data = summary.data;
  const documentos = useMemo(() => documents.data?.itens ?? [], [documents.data]);
  const pctTexto = data ? percentOf(data.documentos_com_texto, data.documentos) : null;
  const pctEdital = data ? percentOf(data.concursos_com_edital, data.concursos) : null;

  return (
    <>
      <PageHeader
        eyebrow="Diagnóstico"
        title="Pipeline documental"
        description="Baixar não é extrair; extrair não é confirmar. Cada documento aparece com a primeira etapa que falta e o motivo — nunca como “sem dados”."
        meta={data ? <span>Base de {data.generated_at.slice(0, 10)}</span> : null}
      />

      {summary.isLoading ? (
        <SkeletonRows rows={3} />
      ) : summary.isError ? (
        <Card>
          <ErrorState message={summary.error.message} onRetry={() => summary.refetch()} />
        </Card>
      ) : data ? (
        <>
          <section aria-label="Resumo do pipeline" className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
            <Kpi
              feature
              tone="accent"
              label="Concursos com edital"
              value={<NumberTicker value={data.concursos_com_edital} />}
              context={`de ${integer(data.concursos)} concursos (${pctEdital === null ? '—' : `${pctEdital}%`})`}
            />
            <Kpi
              label="Documentos com texto"
              value={<NumberTicker value={data.documentos_com_texto} />}
              context={`de ${integer(data.documentos)} baixados (${pctTexto === null ? '—' : `${pctTexto}%`})`}
            />
            <Kpi
              label="Propostas extraídas"
              value={<NumberTicker value={data.propostas} />}
              context={`${integer(data.campos_confirmados)} campo(s) confirmado(s) por humano`}
            />
            <Kpi
              label="Falhas de extração"
              value={
                <NumberTicker
                  value={Object.values(data.falhas_por_codigo).reduce((sum, value) => sum + value, 0)}
                />
              }
              context={
                Object.entries(data.falhas_por_codigo)
                  .map(([code, value]) => `${code.replace(/_/g, ' ')}: ${value}`)
                  .join(' · ') || 'nenhuma falha registrada'
              }
            />
          </section>

          <div className="mt-3 grid gap-3 xl:grid-cols-[1.2fr_1fr]">
            <Card
              title="Documentos"
              subtitle="A primeira etapa que falta, com o motivo."
              flush
              action={
                <label className="flex items-center gap-1.5 text-2xs text-fg-2">
                  <input
                    type="checkbox"
                    name="somente-pendentes"
                    checked={pending}
                    onChange={(event) => setPending(event.target.checked)}
                    className="size-3.5 accent-[var(--color-accent)]"
                  />
                  Só com bloqueio
                </label>
              }
            >
              <div className="border-b border-line px-4 py-2">
                <label className="flex flex-col gap-1">
                  <span className="text-[9px] font-semibold tracking-[0.08em] text-fg-3 uppercase">
                    Concurso (ID)
                  </span>
                  <input
                    type="search"
                    name="concurso"
                    autoComplete="off"
                    value={contestId}
                    onChange={(event) => setContestId(event.target.value)}
                    placeholder="opcional"
                    className="h-8 w-full rounded-sm border border-line-strong bg-surface-2 px-2.5 text-xs text-fg outline-none placeholder:text-fg-3 focus:border-accent/60"
                  />
                </label>
              </div>

              {documents.isLoading ? (
                <SkeletonRows rows={5} />
              ) : documents.isError ? (
                <ErrorState message={documents.error.message} onRetry={() => documents.refetch()} />
              ) : !documentos.length ? (
                <EmptyState
                  title="Nenhum documento com esses filtros"
                  description="Documento ausente não é documento inexistente: ajuste o filtro para ver o resto."
                />
              ) : (
                <>
                  <ul>
                    {documentos.map((document) => (
                      <DocumentCard key={document.document_id} document={document} />
                    ))}
                  </ul>
                  {documents.data?.truncated && (
                    <p className="border-t border-line px-4 py-2 text-2xs text-fg-3">
                      Mostrando {integer(documents.data.returned)} de{' '}
                      {integer(documents.data.total)} documento(s). Refine o filtro para ver o resto.
                    </p>
                  )}
                </>
              )}
            </Card>

            <div className="grid gap-3">
              <Card title="Bloqueios" subtitle="Por etapa que impede o avanço.">
                {documents.data ? (
                  <ul className="space-y-1.5">
                    {Object.entries(documents.data.por_bloqueio)
                      .sort((a, b) => b[1] - a[1])
                      .map(([blocker, value]) => (
                        <li key={blocker} className="flex items-center justify-between gap-2 text-2xs">
                          <span className="min-w-0 truncate text-fg-2">
                            {BLOCKER_LABELS[blocker] ?? blocker}
                          </span>
                          <span className="tabular text-fg-3">{integer(value)}</span>
                        </li>
                      ))}
                  </ul>
                ) : (
                  <p className="text-2xs text-fg-3">Carregando…</p>
                )}
              </Card>

              <Card title="Cobertura por concurso" subtitle="Categoria exclusiva por certame.">
                {coverage.isLoading ? (
                  <SkeletonRows rows={4} />
                ) : coverage.isError ? (
                  <ErrorState message={coverage.error.message} onRetry={() => coverage.refetch()} />
                ) : coverage.data ? (
                  <ul className="space-y-1.5">
                    {Object.entries(coverage.data.por_categoria)
                      .sort((a, b) => b[1] - a[1])
                      .map(([category, value]) => (
                        <li key={category} className="flex items-center justify-between gap-2 text-2xs">
                          <span className="min-w-0 truncate text-fg-2">
                            {CATEGORY_LABELS[category] ?? category}
                          </span>
                          <span className="tabular text-fg-3">{integer(value)}</span>
                        </li>
                      ))}
                  </ul>
                ) : null}
                {coverage.data?.limitacao && (
                  <p className="mt-2 text-2xs text-fg-3">{truncate(coverage.data.limitacao, 220)}</p>
                )}
              </Card>
            </div>
          </div>

          {documents.data?.limitacao && (
            <p className="mt-3 text-2xs text-fg-3">{documents.data.limitacao}</p>
          )}
        </>
      ) : null}
    </>
  );
}
