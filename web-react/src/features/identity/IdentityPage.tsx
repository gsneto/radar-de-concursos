import { useMemo, useState } from 'react';
import { Link } from 'react-router-dom';
import {
  useConflicts,
  useDecideReconciliation,
  useReconciliation,
  type ReconciliationFilters,
} from '@/app/queries';
import { PageHeader } from '@/components/layout/page-header';
import { Badge, type Tone } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Card } from '@/components/ui/card';
import { EmptyState, ErrorState, SkeletonRows } from '@/components/ui/states';
import { integer, truncate } from '@/lib/format';
import { readReviewer, saveReviewer } from '@/lib/reviewer';
import type { ConflictGroup, ReconciliationItem } from '@/lib/types';

const NATURES = [
  { value: '', label: 'Todas as naturezas' },
  { value: 'cargo_literal', label: 'Cargo literal' },
  { value: 'cargo_com_codigo', label: 'Código + nome' },
  { value: 'abreviacao', label: 'Abreviação' },
  { value: 'especialidade', label: 'Especialidade' },
  { value: 'codigo_sem_nome', label: 'Só código' },
  { value: 'generico_sem_cargo', label: 'Genérico sem cargo' },
  { value: 'nao_e_cargo', label: 'Não é cargo' },
];

const STATES = [
  { value: '', label: 'Todos os estados' },
  { value: 'exata', label: 'Correspondência exata' },
  { value: 'alias', label: 'Alias' },
  { value: 'provavel', label: 'Provável' },
  { value: 'ambigua', label: 'Ambígua' },
  { value: 'duplicata_de_identidade', label: 'Duplicata de identidade' },
  { value: 'confirmada', label: 'Confirmada' },
  { value: 'rejeitada', label: 'Rejeitada' },
  { value: 'nao_e_cargo', label: 'Não é cargo' },
];

const CAUSES = [
  { value: '', label: 'Todas as causas' },
  { value: 'retificacao_posterior', label: 'Retificação posterior' },
  { value: 'mesmo_documento_valores_distintos', label: 'Mesmo documento, valores distintos' },
  { value: 'documentos_diferentes_sem_ordem', label: 'Documentos sem ordem' },
  { value: 'escopo_diferente', label: 'Escopo diferente' },
  { value: 'cargos_diferentes_sem_identificacao', label: 'Cargos diferentes' },
  { value: 'documentos_com_data_distinta', label: 'Datas distintas' },
  { value: 'variacao_de_extracao', label: 'Variação de extração' },
];

const stateTone = (state: string): Tone =>
  state === 'confirmada' || state === 'exata'
    ? 'ok'
    : state === 'rejeitada' || state === 'nao_e_cargo'
      ? 'risk'
      : state === 'ambigua' || state === 'duplicata_de_identidade'
        ? 'warn'
        : 'neutral';

function formatValue(value: unknown): string {
  if (value === null || value === undefined || value === '') return 'Não informado';
  if (typeof value === 'string') return value;
  if (typeof value === 'object') return JSON.stringify(value);
  return String(value);
}

function LabelCard({
  item,
  reviewer,
  reason,
  onReason,
}: {
  item: ReconciliationItem;
  reviewer: string;
  reason: string;
  onReason: (value: string) => void;
}) {
  const decide = useDecideReconciliation();
  const suggestion = item.suggestions[0] ?? null;
  const ready = Boolean(reviewer.trim() && reason.trim());

  const submit = (state: 'confirmada' | 'rejeitada' | 'ambigua', roleId?: string | null) =>
    decide.mutate({
      contestId: item.contest_id,
      label: item.label,
      state,
      reviewer: reviewer.trim(),
      reason: reason.trim(),
      roleId: roleId ?? null,
      nature: item.nature,
    });

  return (
    <Card flush as="article">
      <header className="border-b border-line px-4 py-3">
        <div className="flex flex-wrap items-start justify-between gap-2">
          <div className="min-w-0">
            <p className="text-[13px] font-medium text-fg">{item.label}</p>
            <p className="mt-0.5 truncate text-2xs text-fg-3">
              {item.contest_id.slice(0, 8)} · {item.nature_label} ·{' '}
              {integer(item.proposals)} proposta(s)
              {item.pages.length ? ` · p. ${item.pages.slice(0, 4).join(', ')}` : ''}
            </p>
          </div>
          <div className="flex flex-wrap items-center gap-1.5">
            <Badge tone={stateTone(item.state)}>{item.state.replace(/_/g, ' ')}</Badge>
            {item.cargo_count === 0 && <Badge tone="warn">sem cargo canônico</Badge>}
          </div>
        </div>

        {item.first_evidence?.quote && (
          <blockquote className="mt-2 border-l-2 border-accent/40 pl-2.5 text-2xs leading-relaxed text-fg-2">
            “{truncate(item.first_evidence.quote, 240)}”
            {item.first_evidence.document_title && (
              <span className="mt-1 block text-fg-3">
                {item.first_evidence.document_title}
                {item.first_evidence.published_at ? ` · ${item.first_evidence.published_at}` : ''}
              </span>
            )}
          </blockquote>
        )}

        {suggestion ? (
          <div className="mt-2 rounded-sm border border-line bg-surface-2 px-2.5 py-2">
            <p className="text-2xs text-fg-3">
              Sugestão estrutural · pontuação {integer(suggestion.pontuacao)} (não é probabilidade)
            </p>
            <p className="mt-0.5 text-xs font-medium text-fg">{suggestion.role_name}</p>
            <ul className="mt-1 space-y-0.5">
              {suggestion.fatores.slice(0, 3).map((factor) => (
                <li key={factor.fator} className="text-2xs text-fg-3">
                  {factor.motivo} (+{factor.pontos})
                </li>
              ))}
            </ul>
          </div>
        ) : (
          <p className="mt-2 text-2xs text-fg-3">
            Sem sugestão de identidade: não há cargo comparável neste concurso.
          </p>
        )}

        {item.decision && (
          <p className="mt-2 text-2xs text-fg-2">
            Decidido como <strong>{item.decision.state}</strong> por {item.decision.reviewer} ·{' '}
            {item.decision.reason}
          </p>
        )}
      </header>

      <div className="border-b border-line bg-surface-2/40 px-4 py-2">
        <label className="flex flex-col gap-1">
          <span className="text-[9px] font-semibold tracking-[0.08em] text-fg-3 uppercase">
            Justificativa deste rótulo
          </span>
          <input
            type="text"
            name="justificativa"
            autoComplete="off"
            value={reason}
            onChange={(event) => onReason(event.target.value)}
            placeholder="Por que este é (ou não é) o cargo…"
            className="h-8 w-full rounded-sm border border-line-strong bg-surface-2 px-2.5 text-xs text-fg outline-none placeholder:text-fg-3 focus:border-accent/60"
          />
        </label>
      </div>

      <div className="flex flex-wrap items-center gap-1.5 px-4 py-2.5">
        <Button
          size="sm"
          variant="primary"
          disabled={!ready || !suggestion || decide.isPending}
          title={suggestion ? undefined : 'Confirmação exige um cargo sugerido'}
          onClick={() => submit('confirmada', suggestion?.role_id)}
        >
          Confirmar cargo
        </Button>
        <Button
          size="sm"
          variant="danger"
          disabled={!ready || decide.isPending}
          onClick={() => submit('rejeitada')}
        >
          Rejeitar
        </Button>
        <Button
          size="sm"
          variant="ghost"
          disabled={!ready || decide.isPending}
          onClick={() => submit('ambigua')}
        >
          Marcar ambígua
        </Button>
        <Link
          to={`/dossie/${item.contest_id}`}
          className="ml-auto text-2xs font-medium text-accent hover:underline"
        >
          Abrir dossiê
        </Link>
      </div>

      {decide.isError && (
        <p role="alert" className="px-4 pb-2.5 text-2xs text-risk">
          {decide.error.message}
        </p>
      )}
      {decide.isSuccess && (
        <p role="status" className="px-4 pb-2.5 text-2xs text-ok">
          Decisão registrada: {decide.data?.state ?? 'ok'}.
        </p>
      )}
    </Card>
  );
}

function ConflictCard({ group }: { group: ConflictGroup }) {
  return (
    <Card flush as="article">
      <header className="border-b border-line px-4 py-3">
        <div className="flex flex-wrap items-start justify-between gap-2">
          <div className="min-w-0">
            <p className="text-[13px] font-medium text-fg">{group.cause_label}</p>
            <p className="mt-0.5 truncate text-2xs text-fg-3">
              {group.contest_id.slice(0, 8)}
              {group.scope ? ` · ${group.scope.replace(/^label:/, '')}` : ''} ·{' '}
              {group.field_name} · {integer(group.valores_distintos)} valor(es)
            </p>
          </div>
          <Badge tone={group.prioridade <= 2 ? 'risk' : 'warn'}>
            prioridade {integer(group.prioridade)}
          </Badge>
        </div>
        <p className="mt-1.5 text-2xs text-fg-2">{group.proxima_acao}</p>
        {group.motivos.length > 0 && (
          <ul className="mt-1 space-y-0.5">
            {group.motivos.map((motivo) => (
              <li key={motivo} className="text-2xs text-fg-3">
                · {motivo}
              </li>
            ))}
          </ul>
        )}
      </header>
      <ul>
        {group.propostas.map((proposal) => (
          <li key={proposal.proposal_id} className="border-t border-line/70 px-4 py-2.5 first:border-t-0">
            <p className="text-xs font-medium text-fg">{formatValue(proposal.value)}</p>
            <p className="mt-0.5 text-2xs text-fg-3">
              {proposal.document_title ?? 'Documento'}
              {proposal.published_at ? ` · ${proposal.published_at}` : ''}
              {proposal.page_number ? ` · p. ${proposal.page_number}` : ''} ·{' '}
              {proposal.tipo_documental ?? 'tipo não informado'}
            </p>
            {proposal.quote && (
              <p className="mt-1 text-2xs text-fg-2">“{truncate(proposal.quote, 200)}”</p>
            )}
          </li>
        ))}
      </ul>
      <footer className="border-t border-line px-4 py-2 text-2xs text-fg-3">
        Conflito não escolhe valor: todos os candidatos continuam visíveis.
      </footer>
    </Card>
  );
}

export function IdentityPage() {
  const [tab, setTab] = useState<'cargos' | 'conflitos'>('cargos');
  // Começa pelo que é acionável: rótulo com sugestão de identidade. Rótulo sem
  // sugestão (inclusive "não é cargo") aparece desmarcando a caixa.
  const [filters, setFilters] = useState<ReconciliationFilters>({
    limit: 25,
    offset: 0,
    minCandidates: 1,
  });
  const [cause, setCause] = useState('');
  const [reviewer, setReviewer] = useState(readReviewer);
  const [reasons, setReasons] = useState<Record<string, string>>({});

  const reconciliation = useReconciliation(filters);
  const conflicts = useConflicts({ cause: cause || undefined, limit: 20 });
  const items = useMemo(() => reconciliation.data?.itens ?? [], [reconciliation.data]);
  const conflictItems = useMemo(() => conflicts.data?.itens ?? [], [conflicts.data]);

  const update = (changes: Partial<ReconciliationFilters>) =>
    setFilters((current) => ({ ...current, ...changes, offset: 0 }));

  return (
    <>
      <PageHeader
        eyebrow="Trabalho"
        title="Identidades"
        description="Reconciliação de cargo é decisão humana e append-only. Conflito entre propostas não escolhe vencedor: a causa é declarada e os valores ficam visíveis."
        meta={
          reconciliation.data ? (
            <span>
              {integer(reconciliation.data.total)} rótulo(s) na fila ·{' '}
              {integer(conflicts.data?.total ?? 0)} conflito(s)
            </span>
          ) : null
        }
      />

      <Card className="mb-3">
        <div className="flex flex-wrap items-end gap-3">
          <label className="flex min-w-[220px] flex-1 flex-col gap-1">
            <span className="text-[9px] font-semibold tracking-[0.08em] text-fg-3 uppercase">
              Responsável (local)
            </span>
            <input
              type="text"
              name="revisor"
              autoComplete="off"
              spellCheck={false}
              value={reviewer}
              onChange={(event) => {
                setReviewer(event.target.value);
                saveReviewer(event.target.value);
              }}
              placeholder="Seu nome, registrado em cada decisão"
              className="h-9 w-full rounded-sm border border-line-strong bg-surface-2 px-2.5 text-xs text-fg outline-none placeholder:text-fg-3 focus:border-accent/60"
            />
          </label>
          {!reviewer.trim() && (
            <p className="pb-2 text-2xs text-warn">Sem responsável, as decisões ficam bloqueadas.</p>
          )}
        </div>
      </Card>

      <div role="tablist" aria-label="Seções de identidade" className="mb-3 flex flex-wrap gap-1 border-b border-line pb-px">
        {[
          { id: 'cargos' as const, label: 'Cargos', count: reconciliation.data?.total },
          { id: 'conflitos' as const, label: 'Conflitos', count: conflicts.data?.total },
        ].map((entry) => (
          <button
            key={entry.id}
            type="button"
            role="tab"
            aria-selected={tab === entry.id}
            onClick={() => setTab(entry.id)}
            className={
              'rounded-t-xs px-3 py-2 text-xs font-medium transition-colors ' +
              (tab === entry.id
                ? 'text-accent after:relative after:-bottom-2 after:block after:h-0.5 after:rounded-full after:bg-accent'
                : 'text-fg-3 hover:text-fg-2')
            }
          >
            {entry.label}
            {entry.count !== undefined && (
              <span className="ml-1.5 tabular text-2xs text-fg-3">{integer(entry.count)}</span>
            )}
          </button>
        ))}
      </div>

      {tab === 'cargos' ? (
        <>
          <Card className="mb-3">
            <div className="flex flex-wrap items-end gap-2">
              <label className="flex flex-col gap-1">
                <span className="text-[9px] font-semibold tracking-[0.08em] text-fg-3 uppercase">
                  Natureza
                </span>
                <select
                  name="natureza"
                  autoComplete="off"
                  value={filters.nature ?? ''}
                  onChange={(event) => update({ nature: event.target.value || undefined })}
                  className="h-8 min-w-[170px] rounded-sm border border-line-strong bg-surface-2 px-2.5 text-xs text-fg outline-none focus:border-accent/60"
                >
                  {NATURES.map((option) => (
                    <option key={option.value} value={option.value}>{option.label}</option>
                  ))}
                </select>
              </label>
              <label className="flex flex-col gap-1">
                <span className="text-[9px] font-semibold tracking-[0.08em] text-fg-3 uppercase">
                  Estado
                </span>
                <select
                  name="estado"
                  autoComplete="off"
                  value={filters.state ?? ''}
                  onChange={(event) => update({ state: event.target.value || undefined })}
                  className="h-8 min-w-[170px] rounded-sm border border-line-strong bg-surface-2 px-2.5 text-xs text-fg outline-none focus:border-accent/60"
                >
                  {STATES.map((option) => (
                    <option key={option.value} value={option.value}>{option.label}</option>
                  ))}
                </select>
              </label>
              <label className="flex flex-col gap-1">
                <span className="text-[9px] font-semibold tracking-[0.08em] text-fg-3 uppercase">
                  Concurso (ID)
                </span>
                <input
                  type="search"
                  name="concurso"
                  autoComplete="off"
                  value={filters.contestId ?? ''}
                  onChange={(event) => update({ contestId: event.target.value || undefined })}
                  placeholder="opcional"
                  className="h-8 min-w-[180px] rounded-sm border border-line-strong bg-surface-2 px-2.5 text-xs text-fg outline-none placeholder:text-fg-3 focus:border-accent/60"
                />
              </label>
              <label className="flex items-center gap-1.5 pb-1.5 text-2xs text-fg-2">
                <input
                  type="checkbox"
                  name="com-sugestao"
                  checked={Boolean(filters.minCandidates)}
                  onChange={(event) => update({ minCandidates: event.target.checked ? 1 : undefined })}
                  className="size-3.5 accent-[var(--color-accent)]"
                />
                Só com sugestão
              </label>
            </div>
          </Card>

          {reconciliation.isLoading ? (
            <SkeletonRows rows={5} />
          ) : reconciliation.isError ? (
            <Card>
              <ErrorState
                message={reconciliation.error.message}
                onRetry={() => reconciliation.refetch()}
              />
            </Card>
          ) : !items.length ? (
            <Card>
              <EmptyState
                title="Nenhum rótulo com esses filtros"
                description="Ajuste natureza ou estado. Rótulo que não é cargo não precisa de identidade."
              />
            </Card>
          ) : (
            <div className="grid gap-3">
              {items.map((item) => (
                <LabelCard
                  key={`${item.contest_id}-${item.label}`}
                  item={item}
                  reviewer={reviewer}
                  reason={reasons[`${item.contest_id}-${item.label}`] ?? ''}
                  onReason={(value) =>
                    setReasons((current) => ({
                      ...current,
                      [`${item.contest_id}-${item.label}`]: value,
                    }))
                  }
                />
              ))}
            </div>
          )}

          {reconciliation.data && reconciliation.data.total > items.length && (
            <nav
              aria-label="Paginação de identidades"
              className="mt-3 flex flex-wrap items-center justify-between gap-2 text-2xs text-fg-3"
            >
              <span className="tabular">
                Mostrando {items.length} de {integer(reconciliation.data.total)} rótulo(s)
              </span>
              <div className="flex gap-1.5">
                <Button
                  variant="ghost"
                  size="sm"
                  disabled={(filters.offset ?? 0) <= 0}
                  onClick={() =>
                    setFilters((current) => ({
                      ...current,
                      offset: Math.max(0, (current.offset ?? 0) - (current.limit ?? 25)),
                    }))
                  }
                >
                  Anterior
                </Button>
                <Button
                  variant="ghost"
                  size="sm"
                  disabled={!reconciliation.data.has_more}
                  onClick={() =>
                    setFilters((current) => ({
                      ...current,
                      offset: (current.offset ?? 0) + (current.limit ?? 25),
                    }))
                  }
                >
                  Próxima
                </Button>
              </div>
            </nav>
          )}
        </>
      ) : (
        <>
          <Card className="mb-3">
            <div className="flex flex-wrap items-end gap-2">
              <label className="flex flex-col gap-1">
                <span className="text-[9px] font-semibold tracking-[0.08em] text-fg-3 uppercase">
                  Causa
                </span>
                <select
                  name="causa"
                  autoComplete="off"
                  value={cause}
                  onChange={(event) => setCause(event.target.value)}
                  className="h-8 min-w-[230px] rounded-sm border border-line-strong bg-surface-2 px-2.5 text-xs text-fg outline-none focus:border-accent/60"
                >
                  {CAUSES.map((option) => (
                    <option key={option.value} value={option.value}>{option.label}</option>
                  ))}
                </select>
              </label>
              {conflicts.data && (
                <p className="pb-2 text-2xs text-fg-3">
                  {Object.entries(conflicts.data.por_causa)
                    .map(([key, value]) => `${key.replace(/_/g, ' ')}: ${value}`)
                    .join(' · ')}
                </p>
              )}
            </div>
          </Card>

          {conflicts.isLoading ? (
            <SkeletonRows rows={4} />
          ) : conflicts.isError ? (
            <Card>
              <ErrorState message={conflicts.error.message} onRetry={() => conflicts.refetch()} />
            </Card>
          ) : !conflictItems.length ? (
            <Card>
              <EmptyState
                title="Nenhum conflito com essa causa"
                description="Conflito é divergência entre documentos ou versões, classificada por evidência."
              />
            </Card>
          ) : (
            <div className="grid gap-3">
              {conflictItems.map((group, index) => (
                <ConflictCard key={`${group.contest_id}-${group.field_name}-${index}`} group={group} />
              ))}
            </div>
          )}

          {conflicts.data?.limitacao && (
            <p className="mt-3 text-2xs text-fg-3">{conflicts.data.limitacao}</p>
          )}
        </>
      )}
    </>
  );
}
