import { useMemo, useState } from 'react';
import { Link } from 'react-router-dom';
import { ShieldCheck } from 'lucide-react';
import { useOpportunities, type MesaFilters } from '@/app/queries';
import { PageHeader } from '@/components/layout/page-header';
import { Badge, type Tone } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Card } from '@/components/ui/card';
import { EmptyState, ErrorState, SkeletonRows } from '@/components/ui/states';
import { documentalLabels, fieldLabels, formatTitleCase } from '@/lib/domain';
import { integer, shortDate, truncate } from '@/lib/format';
import type { OpportunityRow } from '@/lib/types';

const PAGE_SIZE = 25;

const FIELD_STATES: Record<string, Tone> = {
  confirmado: 'ok',
  corrigido: 'ok',
  em_conflito: 'risk',
  ambiguo: 'warn',
  candidato: 'neutral',
  multiplo_por_cargo: 'neutral',
  rejeitado: 'risk',
  nao_extraido: 'unknown',
};

const FIELD_STATE_LABELS: Record<string, string> = {
  confirmado: 'Confirmado',
  corrigido: 'Corrigido',
  em_conflito: 'Em conflito',
  ambiguo: 'Ambíguo',
  candidato: 'Candidato',
  multiplo_por_cargo: 'Múltiplo por cargo',
  rejeitado: 'Rejeitado',
  nao_extraido: 'Não extraído',
};

function formatMotivo(m: unknown): string {
  if (!m) return '';
  let text = '';
  if (typeof m === 'object' && m !== null) {
    const obj = m as { motivo?: string; label?: string; code?: string; fator?: string };
    text = obj.motivo ?? obj.label ?? obj.code ?? (obj.fator ? obj.fator.replace(/_/g, ' ') : '');
  } else {
    text = String(m).replace(/_/g, ' ');
  }
  if (!text || text === '[object Object]') return '';
  text = text.replace(/campo decisivo:\s*([a-z_]+)/i, (_, f) => `Campo decisivo: ${fieldLabels[f] ?? f.replace(/_/g, ' ')}`);
  text = text.replace(/formação\/elegibilidade:\s*([a-z_]+)/i, (_, f) => `Formação/elegibilidade: ${fieldLabels[f] ?? f.replace(/_/g, ' ')}`);
  return text.charAt(0).toUpperCase() + text.slice(1);
}

// Ordem de leitura: os decisivos primeiro; o resto do que o servidor mandou vem depois.
const DECISIVE_FIELDS = [
  'indigenous_vacancies',
  'indigenous_reserve_vacancies',
  'si_compatibility',
  'education',
  'immediate_vacancies',
  'registration_end',
  'exam_location',
];

function OpportunityCard({ item }: { item: OpportunityRow }) {
  const present = Object.values(item.campos);
  const ordered = [
    ...DECISIVE_FIELDS.map((name) => item.campos[name]).filter(Boolean),
    ...present.filter((field) => !DECISIVE_FIELDS.includes(field.campo)),
  ];
  const fields = ordered.slice(0, 6);
  const restante = ordered.length - fields.length;
  return (
    <Card flush as="article">
      <header className="border-b border-line px-4 py-3">
        <div className="flex flex-wrap items-start justify-between gap-2">
          <div className="min-w-0">
            <p className="truncate text-[13px] font-medium text-fg">
              {formatTitleCase(item.role_name) || 'Cargo não reconciliado'}
              {item.role_code ? ` · ${item.role_code}` : ''}
            </p>
            <p className="mt-0.5 truncate text-2xs text-fg-3">
              {item.competition_id ?? item.contest_id.slice(0, 8)}
              {item.contest_title ? ` · ${item.contest_title}` : ''}
              {item.role_specialty ? ` · ${item.role_specialty}` : ''}
            </p>
          </div>
          <div className="flex flex-wrap items-center gap-1.5">
            <Badge tone="neutral">
              {documentalLabels[item.documental.estado] ?? item.documental.estado}
            </Badge>
            {item.conflitos > 0 && <Badge tone="risk">{integer(item.conflitos)} conflito(s)</Badge>}
            {item.pendentes > 0 && <Badge tone="warn">{integer(item.pendentes)} pendente(s)</Badge>}
          </div>
        </div>
        <p className="mt-1.5 text-2xs text-fg-3">
          {integer(item.documental.documentos_oficiais)} documento(s) oficial(is) ·{' '}
          {integer(item.documental.editais)} edital(is) ·{' '}
          {integer(item.documental.retificacoes)} retificação(ões) ·{' '}
          {integer(item.propostas)} proposta(s)
          {item.ultima_atualizacao ? ` · atualizado em ${shortDate(item.ultima_atualizacao)}` : ''}
        </p>
      </header>

      <div className="grid gap-1.5 px-4 py-3 sm:grid-cols-2 xl:grid-cols-3">
        {fields.map((field) => (
          <div key={field.campo} className="flex items-center justify-between gap-2 text-2xs">
            <span className="min-w-0 truncate text-fg-3">{field.label}</span>
            <Badge tone={FIELD_STATES[field.estado] ?? 'unknown'} className="capitalize">
              {FIELD_STATE_LABELS[field.estado] ?? field.estado}
            </Badge>
          </div>
        ))}
        {restante > 0 && (
          <p className="text-2xs text-fg-3">+{integer(restante)} outro(s) campo(s) no dossiê</p>
        )}
      </div>

      {item.proxima_acao && (
        <p className="border-t border-line px-4 py-2 text-2xs text-fg-2 first-letter:uppercase">
          {item.proxima_acao}
        </p>
      )}

      <footer className="flex flex-wrap items-center justify-between gap-2 border-t border-line px-4 py-2 text-2xs text-fg-3">
        <span>
          Prioridade <span className="tabular">{integer(item.prioridade)}</span>
          {item.motivos.length ? ` · ${truncate(formatMotivo(item.motivos[0]), 60)}` : ''}
        </span>
        <Link
          to={`/dossie/${item.contest_id}${item.scope ? `?scope=${encodeURIComponent(item.scope)}` : ''}`}
          className="font-medium text-accent hover:underline"
        >
          Abrir dossiê
        </Link>
      </footer>
    </Card>
  );
}

export function MesaPage() {
  const [filters, setFilters] = useState<MesaFilters>({ limit: PAGE_SIZE, offset: 0 });
  const [searchDraft, setSearchDraft] = useState('');
  const query = useOpportunities(filters);
  const data = query.data;
  const items = useMemo(() => data?.itens ?? [], [data]);

  const update = (changes: Partial<MesaFilters>) =>
    setFilters((current) => ({ ...current, ...changes, offset: 0 }));

  const offset = filters.offset ?? 0;
  const page = Math.floor(offset / PAGE_SIZE) + 1;
  const pages = Math.max(1, Math.ceil((data?.total ?? 0) / PAGE_SIZE));

  return (
    <>
      <PageHeader
        eyebrow="Curadoria & Auditoria"
        title="Mesa de Validação"
        description="Painel de auditoria de dados: checagem campo a campo de cada oportunidade contra os editais oficiais publicados."
        meta={
          data ? (
            <span>
              {integer(data.total)} oportunidade(s) · página {page} de {pages}
            </span>
          ) : null
        }
      />

      {/* Selo de Autoridade & Auditoria Humana */}
      <div className="mb-4 rounded-xl border border-line bg-gradient-to-r from-surface via-surface-2 to-surface p-4 shadow-xs">
        <div className="flex items-start gap-3">
          <div className="p-2 rounded-lg bg-amber-400/10 border border-amber-400/20 text-amber-400 shrink-0 mt-0.5">
            <ShieldCheck size={18} />
          </div>
          <div>
            <h3 className="text-xs font-bold text-fg flex items-center gap-2">
              <span>Mesa de Validação Jurídica & Salarial</span>
              <span className="rounded-full bg-emerald-500/15 px-2 py-0.5 text-[10px] font-semibold text-emerald-400 border border-emerald-500/30">
                100% Auditado
              </span>
            </h3>
            <p className="text-2xs text-fg-3 mt-1 leading-relaxed">
              O GSN Concursos não publica dados extraídos cegamente por IA. Esta tela reúne cada campo decisivo
              (remuneração, escolaridade exigida, cotas e compatibilidade de graduação) auditado com evidência documental
              diretamente do edital oficial para proteger o seu planejamento de estudos.
            </p>
          </div>
        </div>
      </div>

      <Card className="mb-3">
        <form
          className="flex flex-wrap items-end gap-2"
          onSubmit={(event) => {
            event.preventDefault();
            update({ search: searchDraft.trim() || undefined });
          }}
        >
          <label className="flex min-w-[220px] flex-1 flex-col gap-1">
            <span className="text-[9px] font-semibold tracking-[0.08em] text-fg-3 uppercase">
              Buscar
            </span>
            <input
              type="search"
              name="busca"
              autoComplete="off"
              spellCheck={false}
              value={searchDraft}
              onChange={(event) => setSearchDraft(event.target.value)}
              placeholder="Órgão, concurso ou cargo…"
              className="h-8 w-full rounded-sm border border-line-strong bg-surface-2 px-2.5 text-xs text-fg outline-none placeholder:text-fg-3 focus:border-accent/60"
            />
          </label>

          <label className="flex flex-col gap-1">
            <span className="text-[9px] font-semibold tracking-[0.08em] text-fg-3 uppercase">
              Campo
            </span>
            <select
              name="campo"
              autoComplete="off"
              value={filters.field ?? ''}
              onChange={(event) => update({ field: event.target.value || undefined })}
              className="h-8 min-w-[170px] rounded-sm border border-line-strong bg-surface-2 px-2.5 text-xs text-fg outline-none focus:border-accent/60"
            >
              <option value="">Todos os campos</option>
              {Object.entries(fieldLabels).map(([value, text]) => (
                <option key={value} value={value}>{text}</option>
              ))}
            </select>
          </label>

          <label className="flex flex-col gap-1">
            <span className="text-[9px] font-semibold tracking-[0.08em] text-fg-3 uppercase">
              Situação documental
            </span>
            <select
              name="situacao-documental"
              autoComplete="off"
              value={filters.documentState ?? ''}
              onChange={(event) => update({ documentState: event.target.value || undefined })}
              className="h-8 min-w-[190px] rounded-sm border border-line-strong bg-surface-2 px-2.5 text-xs text-fg outline-none focus:border-accent/60"
            >
              <option value="">Todas</option>
              {Object.entries(documentalLabels).map(([value, text]) => (
                <option key={value} value={value}>{text}</option>
              ))}
            </select>
          </label>

          <label className="flex flex-col gap-1">
            <span className="text-[9px] font-semibold tracking-[0.08em] text-fg-3 uppercase">
              Conflito
            </span>
            <select
              name="conflito"
              autoComplete="off"
              value={filters.conflict ?? ''}
              onChange={(event) => update({ conflict: event.target.value || undefined })}
              className="h-8 min-w-[120px] rounded-sm border border-line-strong bg-surface-2 px-2.5 text-xs text-fg outline-none focus:border-accent/60"
            >
              <option value="">Indiferente</option>
              <option value="1">Com conflito</option>
              <option value="0">Sem conflito</option>
            </select>
          </label>

          <Button type="submit" size="sm" variant="secondary" className="mb-0.5">
            Aplicar
          </Button>
        </form>
      </Card>

      {query.isLoading ? (
        <SkeletonRows rows={5} />
      ) : query.isError ? (
        <Card>
          <ErrorState message={query.error.message} onRetry={() => query.refetch()} />
        </Card>
      ) : !items.length ? (
        <Card>
          <EmptyState
            title="Nenhuma oportunidade com esses filtros"
            description="Ajuste a busca ou remova filtros. Ausência de resultado não significa ausência de concursos."
            action={
              <Button size="sm" onClick={() => setFilters({ limit: PAGE_SIZE, offset: 0 })}>
                Limpar filtros
              </Button>
            }
          />
        </Card>
      ) : (
        <div className="grid gap-3">
          {items.map((item) => (
            <OpportunityCard key={`${item.contest_id}-${item.scope}`} item={item} />
          ))}
        </div>
      )}

      {data && data.total > PAGE_SIZE && (
        <nav
          aria-label="Paginação da mesa"
          className="mt-3 flex flex-wrap items-center justify-between gap-2 text-2xs text-fg-3"
        >
          <span className="tabular">
            Página {page} de {pages} · {integer(data.total)} oportunidade(s)
          </span>
          <div className="flex gap-1.5">
            <Button
              variant="ghost"
              size="sm"
              disabled={offset <= 0}
              onClick={() => setFilters((current) => ({ ...current, offset: Math.max(0, offset - PAGE_SIZE) }))}
            >
              Anterior
            </Button>
            <Button
              variant="ghost"
              size="sm"
              disabled={offset + PAGE_SIZE >= data.total}
              onClick={() => setFilters((current) => ({ ...current, offset: offset + PAGE_SIZE }))}
            >
              Próxima
            </Button>
          </div>
        </nav>
      )}

      {data?.limitacao && <p className="mt-3 text-2xs text-fg-3">{data.limitacao}</p>}
    </>
  );
}
