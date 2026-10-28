import { useMemo, useState } from 'react';
import { Link } from 'react-router-dom';
import { useDecideProposal, useReviewGroups, type ReviewState } from '@/app/queries';
import { PageHeader } from '@/components/layout/page-header';
import { Badge, type Tone } from '@/components/ui/badge';
import { Button, LinkButton } from '@/components/ui/button';
import { Card } from '@/components/ui/card';
import { EmptyState, ErrorState, SkeletonRows } from '@/components/ui/states';
import { integer, truncate } from '@/lib/format';
import type { ReviewGroup, ReviewProposal } from '@/lib/types';

const REVIEWER_KEY = 'radar.reviewer';

const TABS: { id: ReviewState; label: string; description: string }[] = [
  {
    id: 'prontos',
    label: 'Prontos',
    description:
      'Linhas pendentes, sem conflito e com a soma publicada fechando. A soma coerente não prova a interpretação: cada campo continua exigindo decisão.',
  },
  {
    id: 'aberto',
    label: 'Com pendência',
    description: 'Todas as linhas com campo pendente, inclusive as divergentes e em conflito.',
  },
  { id: 'decidido', label: 'Decididas', description: 'Linhas com todos os campos já decididos.' },
];

const STATE_LABELS: Record<string, string> = {
  pendente: 'Pendente',
  validado: 'Validado',
  rejeitado: 'Rejeitado',
  adiado: 'Adiado',
  ambiguo: 'Ambíguo',
  nova_extracao: 'Nova extração',
  corrigido: 'Corrigido',
  selecionado: 'Valor vigente',
};

const stateTone = (state: string): Tone =>
  state === 'validado' || state === 'corrigido'
    ? 'ok'
    : state === 'rejeitado'
      ? 'risk'
      : state === 'pendente'
        ? 'warn'
        : 'neutral';

function readReviewer(): string {
  try {
    return localStorage.getItem(REVIEWER_KEY) ?? '';
  } catch {
    return '';
  }
}

function formatValue(value: unknown): string {
  if (value === null || value === undefined || value === '') return 'Não informado';
  if (typeof value === 'number') return value.toLocaleString('pt-BR');
  if (typeof value === 'boolean') return value ? 'Sim' : 'Não';
  if (typeof value === 'object') return JSON.stringify(value);
  return String(value);
}

function ValidationBadge({ group }: { group: ReviewGroup }) {
  const validation = group.validacao;
  if (!validation) return <Badge tone="neutral">sem quadro</Badge>;
  if (validation.estado === 'consistente') return <Badge tone="ok">soma confere</Badge>;
  if (validation.estado === 'divergente') {
    return (
      <Badge tone="risk">
        divergente: publicado {formatValue(validation.publicado)} ≠ soma{' '}
        {formatValue(validation.soma)}
      </Badge>
    );
  }
  return <Badge tone="neutral">{validation.estado}</Badge>;
}

function ProposalRow({
  proposal,
  group,
  reviewer,
  reason,
}: {
  proposal: ReviewProposal;
  group: ReviewGroup;
  reviewer: string;
  reason: string;
}) {
  const decide = useDecideProposal();
  const pending = proposal.state === 'pendente';
  const canDecide = Boolean(reviewer.trim() && reason.trim()) && pending;

  const submit = (decision: 'validado' | 'rejeitado' | 'adiado' | 'ambiguo') => {
    decide.mutate({
      proposalId: proposal.proposal_id,
      decision,
      reviewer: reviewer.trim(),
      reason: reason.trim(),
      evidenceSha256: proposal.evidence_sha256,
      scopeSnapshot: proposal.scope_snapshot,
    });
  };

  return (
    <li className="border-t border-line/70 px-4 py-3 first:border-t-0">
      <div className="flex flex-wrap items-start justify-between gap-2">
        <div className="min-w-0">
          <p className="text-xs font-medium text-fg">{proposal.field_label}</p>
          <p className="mt-0.5 text-[15px] font-semibold tabular text-fg">
            {formatValue(proposal.value)}
          </p>
          {proposal.consequencia && (
            <p className="mt-1 max-w-[64ch] text-2xs text-fg-3">{proposal.consequencia}</p>
          )}
        </div>
        <Badge tone={stateTone(proposal.state)}>
          {STATE_LABELS[proposal.state] ?? proposal.state}
        </Badge>
      </div>

      {proposal.ambiguity_reason && (
        <p className="mt-1.5 text-2xs text-fg-3">Rótulo: {proposal.ambiguity_reason}</p>
      )}

      {pending && (
        <div className="mt-2 flex flex-wrap gap-1.5">
          <Button
            size="sm"
            variant="primary"
            disabled={!canDecide || decide.isPending}
            onClick={() => submit('validado')}
            aria-label={`Validar ${proposal.field_label} do grupo ${group.scope}`}
          >
            Validar
          </Button>
          <Button
            size="sm"
            variant="danger"
            disabled={!canDecide || decide.isPending}
            onClick={() => submit('rejeitado')}
          >
            Rejeitar
          </Button>
          <Button
            size="sm"
            variant="ghost"
            disabled={!canDecide || decide.isPending}
            onClick={() => submit('ambiguo')}
          >
            Ambíguo
          </Button>
          <Button
            size="sm"
            variant="ghost"
            disabled={!canDecide || decide.isPending}
            onClick={() => submit('adiado')}
          >
            Adiar
          </Button>
        </div>
      )}

      {decide.isError && (
        <p role="alert" className="mt-1.5 text-2xs text-risk">
          {decide.error.message}
        </p>
      )}
      {decide.isSuccess && (
        <p role="status" className="mt-1.5 text-2xs text-ok">
          {decide.data?.duplicada ? 'Decisão já registrada (idempotente).' : 'Decisão registrada.'}
        </p>
      )}
    </li>
  );
}

function GroupCard({
  group,
  reviewer,
  reason,
  onReason,
}: {
  group: ReviewGroup;
  reviewer: string;
  reason: string;
  onReason: (value: string) => void;
}) {
  const open = group.propostas.filter((item) => item.state === 'pendente').length;
  const quote = group.propostas[0]?.evidence.quote ?? group.contexto?.trecho ?? null;

  return (
    <Card flush as="article">
      <header className="border-b border-line px-4 py-3">
        <div className="flex flex-wrap items-start justify-between gap-2">
          <div className="min-w-0">
            <p className="truncate text-[13px] font-medium text-fg">
              {group.scope.replace(/^label:/, '') || 'Escopo do concurso'}
            </p>
            <p className="mt-0.5 truncate text-2xs text-fg-3">
              {group.competition_id ?? group.contest_id.slice(0, 8)}
              {group.document_title ? ` · ${group.document_title}` : ''}
              {group.page_number ? ` · p. ${group.page_number}` : ''}
              {group.issuer ? ` · ${group.issuer}` : ''}
            </p>
          </div>
          <div className="flex flex-wrap items-center gap-1.5">
            <ValidationBadge group={group} />
            {group.conflito && <Badge tone="risk">conflito</Badge>}
            {group.identidade === 'pendente' && <Badge tone="warn">cargo pendente</Badge>}
            <Badge tone="neutral">{integer(open)} pendente(s)</Badge>
          </div>
        </div>

        {quote && (
          <blockquote className="mt-2 border-l-2 border-accent/40 pl-2.5 text-2xs leading-relaxed text-fg-2">
            “{truncate(quote, 260)}”
          </blockquote>
        )}
        <p className="mt-1.5 text-2xs text-fg-3">{group.proxima_acao}</p>
      </header>

      <div className="border-b border-line bg-surface-2/40 px-4 py-2">
        <label className="flex flex-col gap-1">
          <span className="text-[9px] font-semibold tracking-[0.08em] text-fg-3 uppercase">
            Justificativa desta linha
          </span>
          <input
            type="text"
            name="justificativa"
            autoComplete="off"
            value={reason}
            onChange={(event) => onReason(event.target.value)}
            placeholder="O que você conferiu no documento…"
            className="h-8 w-full rounded-sm border border-line-strong bg-surface-2 px-2.5 text-xs text-fg outline-none placeholder:text-fg-3 focus:border-accent/60"
          />
        </label>
      </div>

      <ul>
        {group.propostas.map((proposal) => (
          <ProposalRow
            key={proposal.proposal_id}
            proposal={proposal}
            group={group}
            reviewer={reviewer}
            reason={reason}
          />
        ))}
      </ul>

      <footer className="flex flex-wrap items-center justify-between gap-2 border-t border-line px-4 py-2 text-2xs text-fg-3">
        <span>
          {group.propostas[0]?.extraction_method ?? 'extração'} · prioridade{' '}
          <span className="tabular">{integer(group.prioridade)}</span>
        </span>
        <Link
          to={`/dossie/${group.contest_id}${group.scope ? `?scope=${encodeURIComponent(group.scope)}` : ''}`}
          className="font-medium text-accent hover:underline"
        >
          Abrir dossiê
        </Link>
      </footer>
    </Card>
  );
}

export function ReviewPage() {
  const [state, setState] = useState<ReviewState>('prontos');
  const [reviewer, setReviewer] = useState(readReviewer);
  const [reasons, setReasons] = useState<Record<string, string>>({});
  const query = useReviewGroups(state, 20);
  const data = query.data;
  const active = TABS.find((tab) => tab.id === state) ?? TABS[0];

  const updateReviewer = (value: string) => {
    setReviewer(value);
    try {
      localStorage.setItem(REVIEWER_KEY, value);
    } catch {
      /* preferência só nesta sessão */
    }
  };

  const resumo = data?.resumo;
  const groups = useMemo(() => data?.itens ?? [], [data]);

  return (
    <>
      <PageHeader
        eyebrow="Trabalho"
        title="Revisão"
        description="Confira o campo contra o trecho do documento e decida. Cada decisão é registrada com autor, justificativa e impressão da evidência; nada é aprovado em massa."
        meta={
          resumo ? (
            <span>
              {integer(resumo.linhas_prontas)} linha(s) pronta(s) ·{' '}
              {integer(resumo.propostas_pendentes)} campo(s) pendente(s) ·{' '}
              {integer(resumo.decisoes_registradas)} decisão(ões)
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
              onChange={(event) => updateReviewer(event.target.value)}
              placeholder="Seu nome, registrado em cada decisão"
              className="h-9 w-full rounded-sm border border-line-strong bg-surface-2 px-2.5 text-xs text-fg outline-none placeholder:text-fg-3 focus:border-accent/60"
            />
          </label>
          {!reviewer.trim() && (
            <p className="pb-2 text-2xs text-warn">
              Sem responsável, as decisões ficam bloqueadas.
            </p>
          )}
        </div>
      </Card>

      <div role="tablist" aria-label="Situação da revisão" className="mb-3 flex flex-wrap gap-1 border-b border-line pb-px">
        {TABS.map((tab) => {
          const selected = tab.id === state;
          return (
            <button
              key={tab.id}
              type="button"
              role="tab"
              aria-selected={selected}
              onClick={() => setState(tab.id)}
              className={
                'rounded-t-xs px-3 py-2 text-xs font-medium transition-colors ' +
                (selected
                  ? 'text-accent after:relative after:-bottom-2 after:block after:h-0.5 after:rounded-full after:bg-accent'
                  : 'text-fg-3 hover:text-fg-2')
              }
            >
              {tab.label}
            </button>
          );
        })}
      </div>

      <p className="mb-3 max-w-[80ch] text-2xs text-fg-3">{active.description}</p>

      {query.isLoading ? (
        <SkeletonRows rows={5} />
      ) : query.isError ? (
        <Card>
          <ErrorState message={query.error.message} onRetry={() => query.refetch()} />
        </Card>
      ) : !groups.length ? (
        <Card>
          <EmptyState
            title={
              state === 'prontos'
                ? 'Nenhuma linha pronta para conferir'
                : state === 'decidido'
                  ? 'Nenhuma linha decidida ainda'
                  : 'Nenhuma linha pendente'
            }
            description="Linhas prontas são as pendentes, sem conflito e com a soma publicada fechando. Use as abas para ver as demais."
            action={
              <LinkButton to="/operacao" size="sm" variant="ghost">
                Ver painéis técnicos
              </LinkButton>
            }
          />
        </Card>
      ) : (
        <div className="grid gap-3">
          {groups.map((group) => (
            <GroupCard
              key={group.linha_id}
              group={group}
              reviewer={reviewer}
              reason={reasons[group.linha_id] ?? ''}
              onReason={(value) =>
                setReasons((current) => ({ ...current, [group.linha_id]: value }))
              }
            />
          ))}
        </div>
      )}

      {data?.limitacao && <p className="mt-3 text-2xs text-fg-3">{data.limitacao}</p>}
    </>
  );
}
