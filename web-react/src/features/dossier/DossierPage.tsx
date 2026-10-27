import { ArrowLeft, ExternalLink, FileText } from 'lucide-react';
import { Link, useParams, useSearchParams } from 'react-router-dom';
import { useContestDetails, useDossier } from '@/app/queries';
import { Badge } from '@/components/ui/badge';
import { LinkButton } from '@/components/ui/button';
import { Card } from '@/components/ui/card';
import { EmptyState, ErrorState, SkeletonRows } from '@/components/ui/states';
import {
  documentTypes,
  extractionLabels,
  fieldLabels,
  indigenousLabels,
  indigenousTones,
  readinessTones,
  siLabels,
  siTones,
} from '@/lib/domain';
import { date, dateTime, integer, relativeDays, safeUrl, truncate } from '@/lib/format';
import type { Dossier, FieldState, Opportunity } from '@/lib/types';

const TABS = [
  ['resumo', 'Resumo'],
  ['cargo', 'Cargo e requisitos'],
  ['vagas', 'Vagas e modalidades'],
  ['prazos', 'Prazos'],
  ['local', 'Localização'],
  ['documentos', 'Documentos'],
  ['evidencias', 'Evidências'],
] as const;

type TabId = (typeof TABS)[number][0];

const locationStates: Record<string, [string, 'ok' | 'accent' | 'warn' | 'risk' | 'unknown' | 'neutral']> = {
  confirmado_documentalmente: ['Confirmado documentalmente', 'ok'],
  extraido_nao_revisado: ['Extraído, não revisado', 'accent'],
  ambiguo: ['Ambíguo', 'warn'],
  em_conflito: ['Em conflito', 'risk'],
  nao_informado: ['Não informado', 'unknown'],
  nao_extraido: ['Não extraído', 'unknown'],
  a_divulgar: ['A divulgar', 'neutral'],
};

function cleanValue(value: unknown): string {
  if (typeof value !== 'string') return String(value);
  const text = value.trim();
  if (text.startsWith('"') && text.endsWith('"')) {
    try {
      return JSON.parse(text);
    } catch {
      return text.slice(1, -1);
    }
  }
  return text;
}

function fieldValues(field: FieldState | null | undefined): string[] {
  return (field?.valores ?? []).map(cleanValue);
}

function fieldStateLabel(field: FieldState | null | undefined): string {
  if (!field) return 'Campo não extraído';
  return (
    {
      nao_extraido: 'Não extraído',
      multiplo_por_cargo: 'Múltiplo por cargo',
      candidato: 'Candidato',
      ambiguo: 'Ambíguo',
      confirmado: 'Confirmado',
    }[field.estado] ?? field.estado.replace(/_/g, ' ')
  );
}

export function DossierPage() {
  const { contestId } = useParams<{ contestId: string }>();
  const [params, setParams] = useSearchParams();
  const scope = params.get('scope');
  const tab = (params.get('tab') as TabId) ?? 'resumo';
  const dossier = useDossier(contestId, scope);
  const details = useContestDetails(contestId);

  const setTab = (next: TabId) => {
    const updated = new URLSearchParams(params);
    if (next === 'resumo') updated.delete('tab');
    else updated.set('tab', next);
    setParams(updated, { replace: true });
  };

  if (dossier.isLoading) {
    return (
      <Card>
        <SkeletonRows rows={8} />
      </Card>
    );
  }

  if (dossier.isError || !dossier.data) {
    return (
      <Card>
        <ErrorState
          title="Dossiê indisponível"
          message={dossier.error?.message ?? 'Concurso não encontrado.'}
          hint="O concurso pode ter sido removido ou o servidor local está indisponível."
          onRetry={() => dossier.refetch()}
        />
      </Card>
    );
  }

  const data = dossier.data;
  const ident = data.identificacao;
  const edital = ident.edital_principal;

  return (
    <>
      <div className="mb-3">
        <Link
          to="/oportunidades"
          className="inline-flex items-center gap-1.5 text-2xs font-medium text-fg-3 transition-colors hover:text-fg"
        >
          <ArrowLeft size={13} /> Voltar aos resultados
        </Link>
      </div>

      <header className="mb-4 rounded-md border border-line bg-[radial-gradient(120%_160%_at_100%_0%,rgb(245_165_36/0.07),transparent_55%)] bg-surface p-4 shadow-panel">
        <div className="flex flex-wrap items-start justify-between gap-4">
          <div className="min-w-0 flex-1">
            <h1 className="font-display text-xl font-semibold tracking-[-0.025em] text-fg">
              {ident.contest_label ?? ident.contest_title ?? 'Concurso'}
            </h1>
            <p className="mt-1 text-sm text-fg-2">
              {ident.role_name ?? 'Cargo ainda não reconciliado — dados do escopo do concurso'}
            </p>
            <div className="mt-2.5 flex flex-wrap items-center gap-x-4 gap-y-1 text-2xs text-fg-3">
              {edital?.issuer && <span>Banca: {edital.issuer}</span>}
              {data.localizacao?.prova?.text && <span>Prova: {data.localizacao.prova.text}</span>}
              <span>{integer(ident.documentos)} documento(s)</span>
              <span>Atualizado em {date(data.generated_at)}</span>
            </div>
            <div className="mt-2.5 flex flex-wrap gap-1">
              <Badge tone={readinessTones[data.prontidao.estado] ?? 'unknown'} dot>
                {data.prontidao.estado_label}
              </Badge>
              {data.conflitos.oportunidade.length > 0 && <Badge tone="risk">Conflito documental</Badge>}
            </div>
          </div>
          <div className="flex flex-wrap items-center gap-2">
            {safeUrl(edital?.official_url) && (
              <a
                href={safeUrl(edital?.official_url)!}
                target="_blank"
                rel="noopener noreferrer"
                className="inline-flex h-9 items-center gap-1.5 rounded-sm border border-line-strong bg-surface-2 px-3 text-xs font-medium text-fg transition-colors hover:bg-surface-3"
              >
                <FileText size={13} /> Documento oficial
              </a>
            )}
            <LinkButton to="/operacao" variant="ghost" size="md">
              Operação
            </LinkButton>
          </div>
        </div>
      </header>

      <div
        role="tablist"
        aria-label="Seções do dossiê"
        className="mb-3 flex gap-1 overflow-x-auto border-b border-line pb-px"
      >
        {TABS.map(([id, text]) => (
          <button
            key={id}
            type="button"
            role="tab"
            aria-selected={tab === id}
            onClick={() => setTab(id)}
            className={
              'relative shrink-0 rounded-t-xs px-3 py-2 text-xs font-medium whitespace-nowrap transition-colors ' +
              (tab === id
                ? 'text-accent after:absolute after:inset-x-2 after:-bottom-px after:h-0.5 after:rounded-full after:bg-accent'
                : 'text-fg-3 hover:bg-white/[0.04] hover:text-fg-2')
            }
          >
            {text}
          </button>
        ))}
      </div>

      <div role="tabpanel" aria-label={TABS.find(([id]) => id === tab)?.[1]}>
        {tab === 'resumo' && <SummaryTab data={data} details={details.data} />}
        {tab === 'cargo' && <CargoTab data={data} />}
        {tab === 'vagas' && <VagasTab data={data} />}
        {tab === 'prazos' && <PrazosTab data={data} />}
        {tab === 'local' && <LocalTab data={data} />}
        {tab === 'documentos' && <DocumentosTab details={details.data} loading={details.isLoading} />}
        {tab === 'evidencias' && <EvidenciasTab details={details.data} loading={details.isLoading} />}
      </div>
    </>
  );
}

function SummaryTab({ data, details }: { data: Dossier; details?: import('@/lib/types').ContestDetails }) {
  const vagas = data.vagas;
  const future = data.prazos.filter((p) => p.estado_temporal === 'futuro').slice(0, 4);

  return (
    <div className="grid gap-3 lg:grid-cols-2">
      <Card title="Próxima ação recomendada" subtitle="A recomendação não confirma nenhum campo.">
        <p className="font-display text-lg font-semibold text-fg">{data.proxima_acao}</p>
        <p className="mt-1 text-xs text-fg-3">{data.prontidao.estado_label}</p>
        {data.prontidao.motivos.map((reason) => (
          <p key={reason} className="mt-1 text-2xs text-fg-3">
            · {reason}
          </p>
        ))}
      </Card>

      <Card title="Números publicados" subtitle="Cada número pertence ao campo de origem.">
        <div className="grid grid-cols-2 gap-2">
          <Tile label="Total publicado" value={fieldValues(vagas.total_publicado).join(' · ') || '—'} hint={fieldStateLabel(vagas.total_publicado)} />
          <Tile label="Vagas imediatas" value={fieldValues(vagas.imediatas).join(' · ') || '—'} hint={fieldStateLabel(vagas.imediatas)} />
          <Tile label="Cadastro de reserva" value={fieldValues(vagas.reserva).join(' · ') || '—'} hint={fieldStateLabel(vagas.reserva)} />
          <Tile
            label="Reserva indígena"
            value={indigenousLabels[vagas.indigenas?.estado ?? ''] ?? 'Não informado'}
            hint={`Âmbito: ${vagas.indigenas?.ambito ?? 'não informado'}`}
          />
        </div>
      </Card>

      <Card title="Lacunas e conflitos" subtitle="O que ainda falta para decidir.">
        {data.lacunas.length === 0 ? (
          <p className="text-xs text-fg-3">Nenhuma lacuna registrada para este recorte.</p>
        ) : (
          <ul className="space-y-1.5">
            {data.lacunas.slice(0, 6).map((gap) => (
              <li key={gap} className="text-xs text-fg-2">
                · {truncate(gap, 130)}
              </li>
            ))}
          </ul>
        )}
        {data.conflitos.oportunidade.length > 0 && (
          <p className="mt-2 text-2xs text-risk">
            {integer(data.conflitos.oportunidade.length)} conflito(s) entre documentos/versões.
          </p>
        )}
      </Card>

      <Card title="Próximos prazos" subtitle="Somente datas futuras com estado de verificação.">
        {!future.length ? (
          <EmptyState
            title="Sem prazo futuro registrado"
            description="Datas passadas permanecem no histórico; datas candidatas não são tratadas como confirmadas."
          />
        ) : (
          <ul className="divide-y divide-line">
            {future.map((item, index) => (
              <li key={`${item.grupo}-${index}`} className="flex items-start justify-between gap-3 py-2 first:pt-0 last:pb-0">
                <div className="min-w-0">
                  <p className="truncate text-xs font-medium text-fg">{item.grupo_label}</p>
                  <p className="mt-0.5 text-2xs text-fg-3">
                    {date(item.valor)} · {item.estado_operacional_label}
                  </p>
                </div>
                <span className="shrink-0 text-2xs font-medium tabular text-fg">
                  {relativeDays(item.dias_restantes)}
                </span>
              </li>
            ))}
          </ul>
        )}
      </Card>

      <Card title="Documento principal" subtitle="A fonte oficial continua sendo a referência final.">
        {!data.identificacao.edital_principal ? (
          <EmptyState
            title="Edital não localizado"
            description="Há documentos do concurso, mas nenhum foi classificado como edital principal."
          />
        ) : (
          <div className="space-y-1">
            <p className="text-xs font-medium text-fg">{data.identificacao.edital_principal.title}</p>
            <p className="text-2xs text-fg-3">
              {documentTypes[data.identificacao.edital_principal.tipo] ?? 'Documento'} ·{' '}
              {integer(data.identificacao.edital_principal.versoes)} versão(ões) ·{' '}
              {integer(data.identificacao.edital_principal.paginas_extraidas)} págs. extraídas
            </p>
            {safeUrl(data.identificacao.edital_principal.official_url) && (
              <a
                href={safeUrl(data.identificacao.edital_principal.official_url)!}
                target="_blank"
                rel="noopener noreferrer"
                className="inline-flex items-center gap-1 text-2xs font-medium text-accent hover:underline"
              >
                Abrir documento <ExternalLink size={11} />
              </a>
            )}
          </div>
        )}
      </Card>

      <Card title="Evidências disponíveis" subtitle="Trechos literais extraídos dos documentos.">
        {details ? (
          <p className="text-xs text-fg-2">
            {integer(details.proposals.length)} proposta(s) · {integer(details.documents.length)}{' '}
            documento(s)
          </p>
        ) : (
          <p className="text-xs text-fg-3">Carregando detalhes documentais…</p>
        )}
        <p className="mt-1.5 text-2xs text-fg-3">{data.limitacao}</p>
      </Card>
    </div>
  );
}

function Tile({ label, value, hint }: { label: string; value: string; hint: string }) {
  return (
    <div className="rounded-sm border border-line bg-surface-2 p-2.5">
      <p className="text-[9px] font-semibold tracking-[0.08em] text-fg-3 uppercase">{label}</p>
      <p className="mt-1 font-display text-base font-semibold text-fg">{value}</p>
      <p className="mt-0.5 text-2xs text-fg-3">{hint}</p>
    </div>
  );
}

function CargoTab({ data }: { data: Dossier }) {
  const formacao = data.formacao;
  const requisito = fieldValues(formacao.requisito);
  const cursos = fieldValues(formacao.cursos_aceitos);
  const si = formacao.si_por_cargo;

  return (
    <div className="grid gap-3 lg:grid-cols-2">
      <Card title="Requisito de formação" subtitle="Texto literal do edital. Não é paráfrase.">
        {!requisito.length ? (
          <EmptyState
            title="Requisito não extraído"
            description="Ausência de extração não prova incompatibilidade; consulte o edital oficial."
          />
        ) : (
          <>
            <Badge tone="neutral">{fieldStateLabel(formacao.requisito)}</Badge>
            <div className="mt-2 space-y-2">
              {requisito.slice(0, 4).map((text, index) => (
                <blockquote
                  key={index}
                  className="rounded-r-xs border-l-2 border-line-strong bg-surface-2 px-2.5 py-2 text-2xs leading-relaxed text-fg-2"
                >
                  {truncate(text, 400)}
                </blockquote>
              ))}
            </div>
            {requisito.length > 4 && (
              <p className="mt-2 text-2xs text-fg-3">+{requisito.length - 4} variação(ões) por cargo.</p>
            )}
          </>
        )}
      </Card>

      <Card title="Sistemas de Informação" subtitle="Compatibilidade calculada, nunca presumida.">
        <Badge tone={siTones[si?.estado ?? ''] ?? 'unknown'}>
          {siLabels[si?.estado ?? ''] ?? 'Informação insuficiente'}
        </Badge>
        {si?.estado_label && <p className="mt-2 text-xs text-fg-2">{si.estado_label}</p>}
        <p className="mt-2 text-2xs text-fg-3">{formacao.nota}</p>
      </Card>

      <Card title="Cursos aceitos" subtitle="Cursos citados no requisito, quando houver.">
        {!cursos.length ? (
          <p className="text-xs text-fg-3">Nenhum curso explicitamente listado.</p>
        ) : (
          <div className="space-y-2">
            {cursos.map((text, index) => (
              <blockquote
                key={index}
                className="rounded-r-xs border-l-2 border-line-strong bg-surface-2 px-2.5 py-2 text-2xs leading-relaxed text-fg-2"
              >
                {truncate(text, 300)}
              </blockquote>
            ))}
          </div>
        )}
      </Card>

      <Card title="O que este dossiê não afirma" subtitle="Limites explícitos do modelo.">
        <p className="text-2xs leading-relaxed text-fg-3">
          Cargo de tecnologia não garante aceitação de Sistemas de Informação. Escolaridade mínima
          não é formação específica. Requisitos adicionais (registro, experiência, habilitação) são
          campos separados e podem não ter sido extraídos.
        </p>
      </Card>
    </div>
  );
}

function VagasTab({ data }: { data: Dossier }) {
  const vagas = data.vagas;
  const ind = vagas.indigenas;

  return (
    <div className="grid gap-3 lg:grid-cols-2">
      {[
        ['Total publicado', vagas.total_publicado, 'Número do edital; não é distribuição por modalidade.'],
        ['Vagas imediatas', vagas.imediatas, 'Quantidade publicada para provimento imediato.'],
        ['Cadastro de reserva', vagas.reserva, 'Não é vaga imediata e não deve ser somado a ela.'],
      ].map(([title, field, hint]) => (
        <Card key={String(title)} title={String(title)} subtitle={String(hint)}>
          <p className="font-display text-lg font-semibold text-fg">
            {fieldValues(field as FieldState).join(' · ') || '—'}
          </p>
          <p className="mt-1 text-2xs text-fg-3">{fieldStateLabel(field as FieldState)}</p>
          {(field as FieldState)?.evidencias?.slice(0, 3).map((evidence) => (
            <blockquote
              key={evidence.proposal_id}
              className="mt-2 rounded-r-xs border-l-2 border-line-strong bg-surface-2 px-2.5 py-1.5 text-2xs text-fg-3"
            >
              {truncate(evidence.quote, 180)}
            </blockquote>
          ))}
        </Card>
      ))}

      <Card title="Reserva indígena" subtitle="Escopo e natureza declarados; nunca derivada de total agregado.">
        <Badge tone={indigenousTones[ind?.estado ?? ''] ?? 'unknown'} dot>
          {indigenousLabels[ind?.estado ?? ''] ?? 'Não informado'}
        </Badge>
        {ind?.estado_label && <p className="mt-2 text-xs text-fg-2">{ind.estado_label}</p>}
        {ind?.nota && <p className="mt-1.5 text-2xs text-fg-3">{ind.nota}</p>}
        {ind?.mencao?.quote && (
          <blockquote className="mt-2 rounded-r-xs border-l-2 border-line-strong bg-surface-2 px-2.5 py-2 text-2xs text-fg-3">
            {truncate(ind.mencao.quote, 240)}
          </blockquote>
        )}
        <div className="mt-2 grid grid-cols-2 gap-2">
          <Tile label="Propostas imediatas" value={integer(ind?.imediata?.length ?? 0)} hint="Leituras, não soma" />
          <Tile label="Propostas de reserva" value={integer(ind?.reserva?.length ?? 0)} hint="Leituras, não soma" />
        </div>
        {ind?.derivado_de_agregado && (
          <p className="mt-2 rounded-sm border border-risk/30 bg-risk-soft px-2 py-1.5 text-2xs text-risk">
            Reserva derivada de total agregado — proibido pelo modelo.
          </p>
        )}
      </Card>

      <Card title="Como ler estes números" subtitle="Regras de integridade aplicadas.">
        <p className="text-2xs leading-relaxed text-fg-3">{vagas.nota}</p>
        <p className="mt-2 text-2xs leading-relaxed text-fg-3">
          Vagas exclusivas, reservas unificadas e cadastro de reserva são categorias distintas. Este
          dossiê não rateia, não soma categorias incompatíveis e não transforma ausência em zero.
        </p>
      </Card>
    </div>
  );
}

function PrazosTab({ data }: { data: Dossier }) {
  const prazos = [...data.prazos].sort((a, b) => (a.prioridade_grupo ?? 99) - (b.prioridade_grupo ?? 99));
  if (!prazos.length) {
    return (
      <Card>
        <EmptyState
          title="Nenhum prazo extraído"
          description="O edital pode não ter datas legíveis ou a extração ainda não cobriu esse trecho."
        />
      </Card>
    );
  }
  return (
    <Card flush>
      <div className="overflow-x-auto">
        <table className="w-full min-w-[720px] border-collapse text-xs">
          <caption className="sr-only">Prazos do concurso</caption>
          <thead>
            <tr className="border-b border-line bg-surface-2">
              {['Evento', 'Data', 'Situação', 'Documento', 'Trecho'].map((text) => (
                <th
                  key={text}
                  scope="col"
                  className="px-3 py-2 text-left text-[9px] font-semibold tracking-[0.08em] text-fg-3 uppercase"
                >
                  {text}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {prazos.map((item, index) => (
              <tr key={`${item.grupo}-${index}`} className="border-b border-line/70 last:border-0">
                <td className="px-3 py-2.5 align-top">
                  <span className="block text-[13px] font-medium text-fg">{item.grupo_label}</span>
                  {item.escopo_rotulo && <span className="text-2xs text-fg-3">{item.escopo_rotulo}</span>}
                </td>
                <td className="px-3 py-2.5 align-top">
                  <span className="block text-[13px] font-medium tabular text-fg">
                    {item.valor ? date(item.valor) : '—'}
                  </span>
                  {item.dias_restantes !== null && (
                    <span className="text-2xs text-fg-3">{relativeDays(item.dias_restantes)}</span>
                  )}
                </td>
                <td className="px-3 py-2.5 align-top">
                  <Badge tone={item.estado_operacional === 'conflito_documental' ? 'risk' : 'neutral'}>
                    {item.urgencia_label}
                  </Badge>
                  <span className="mt-1 block text-2xs text-fg-3">{item.estado_operacional_label}</span>
                </td>
                <td className="px-3 py-2.5 align-top text-2xs text-fg-2">
                  {item.documento ?? 'Não identificado'}
                  {item.pagina ? ` · p. ${item.pagina}` : ''}
                </td>
                <td className="px-3 py-2.5 align-top text-2xs text-fg-3">
                  {truncate(item.trecho, 140) || '—'}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <p className="border-t border-line px-3 py-2 text-2xs text-fg-3">
        Datas candidatas não são prazo confirmado. Uma publicação mais recente não altera todos os
        campos anteriores.
      </p>
    </Card>
  );
}

function LocalTab({ data }: { data: Dossier }) {
  const entries: [string, Opportunity['localizacao']['prova'] | undefined][] = [
    ['Local de prova', data.localizacao?.prova],
    ['Lotação / exercício', data.localizacao?.lotacao],
  ];
  return (
    <div className="grid gap-3 lg:grid-cols-2">
      {entries.map(([title, info]) => {
        const [stateLabel, tone] = locationStates[info?.state ?? ''] ?? ['Não informado', 'unknown'];
        return (
          <Card key={title} title={title} subtitle="Resolvido separadamente; um não substitui o outro.">
            <Badge tone={tone}>{stateLabel}</Badge>
            <p className="mt-2 font-display text-lg font-semibold text-fg">
              {info?.text ?? (info?.municipios?.length ? info.municipios.join(', ') : '—')}
            </p>
            <p className="mt-1 text-2xs text-fg-3">
              {info?.reason ?? 'Sem motivo registrado.'}
              {info?.confidence ? ` · confiança ${info.confidence}` : ''}
            </p>
            {info?.evidence?.quote && (
              <blockquote className="mt-2 rounded-r-xs border-l-2 border-line-strong bg-surface-2 px-2.5 py-2 text-2xs text-fg-3">
                {truncate(info.evidence.quote, 220)}
              </blockquote>
            )}
          </Card>
        );
      })}
      <Card title="Regra aplicada" subtitle="Localização não é inferida.">
        <p className="text-2xs text-fg-3">{data.localizacao?.nota}</p>
      </Card>
    </div>
  );
}

function DocumentosTab({
  details,
  loading,
}: {
  details?: import('@/lib/types').ContestDetails;
  loading: boolean;
}) {
  if (loading) {
    return (
      <Card>
        <SkeletonRows rows={4} />
      </Card>
    );
  }
  if (!details || !details.documents.length) {
    return (
      <Card>
        <EmptyState
          title="Nenhum documento localizado"
          description="O concurso existe na base, mas ainda não tem documento associado."
        />
      </Card>
    );
  }
  return (
    <Card title="Documentos oficiais" subtitle="Documento principal, versões e retificações.">
      <ul className="divide-y divide-line">
        {details.documents.map((document) => (
          <li key={document.id} className="flex items-start gap-3 py-2.5 first:pt-0 last:pb-0">
            <span className="mt-0.5 grid size-8 shrink-0 place-items-center rounded-sm border border-line bg-surface-2 text-fg-3">
              <FileText size={14} />
            </span>
            <div className="min-w-0 flex-1">
              <p className="text-xs font-medium text-fg">{document.title}</p>
              <p className="mt-0.5 text-2xs text-fg-3">
                {documentTypes[document.document_type ?? ''] ?? 'Documento'} ·{' '}
                {document.issuer ?? 'órgão não informado'}
                {document.published_at ? ` · ${date(document.published_at)}` : ''} ·{' '}
                {integer(document.versions.length)} versão(ões)
              </p>
              {document.versions.length > 0 && (
                <details className="mt-1.5">
                  <summary className="cursor-pointer text-2xs text-fg-3 hover:text-fg-2">
                    Versões e estado de extração
                  </summary>
                  <ul className="mt-1 space-y-1">
                    {document.versions.map((version) => (
                      <li key={version.id} className="text-2xs text-fg-3">
                        {dateTime(version.fetched_at)} ·{' '}
                        {extractionLabels[version.extraction_state] ?? version.extraction_state}
                        {version.error_code ? ` · ${version.error_code}` : ''}
                      </li>
                    ))}
                  </ul>
                </details>
              )}
            </div>
            {safeUrl(document.official_url) && (
              <a
                href={safeUrl(document.official_url)!}
                target="_blank"
                rel="noopener noreferrer"
                className="shrink-0 text-2xs font-medium text-accent hover:underline"
              >
                Abrir
              </a>
            )}
          </li>
        ))}
      </ul>
    </Card>
  );
}

function EvidenciasTab({
  details,
  loading,
}: {
  details?: import('@/lib/types').ContestDetails;
  loading: boolean;
}) {
  if (loading) {
    return (
      <Card>
        <SkeletonRows rows={5} />
      </Card>
    );
  }
  if (!details || !details.proposals.length) {
    return (
      <Card>
        <EmptyState
          title="Nenhuma evidência extraída"
          description="O documento pode estar sem camada de texto ou a extração ainda não foi executada."
        />
      </Card>
    );
  }
  return (
    <Card title="Evidências extraídas" subtitle="Trecho literal, página e documento de origem.">
      <ul className="space-y-2">
        {details.proposals.slice(0, 30).map((proposal, index) => (
          <li key={index} className="rounded-sm border border-line bg-surface-2 p-2.5">
            <div className="flex flex-wrap items-center gap-2">
              <Badge tone="neutral">{fieldLabels[proposal.field_name] ?? proposal.field_name}</Badge>
              {proposal.page_number && <span className="text-2xs text-fg-3">p. {proposal.page_number}</span>}
              <span className="ml-auto text-xs font-medium tabular text-fg">
                {proposal.value === null || proposal.value === undefined ? '—' : String(proposal.value)}
              </span>
            </div>
            {proposal.quote && (
              <blockquote className="mt-1.5 border-l-2 border-line-strong pl-2 text-2xs text-fg-3">
                {truncate(proposal.quote, 300)}
              </blockquote>
            )}
          </li>
        ))}
      </ul>
      {details.proposals.length > 30 && (
        <p className="mt-2 text-2xs text-fg-3">
          Mostrando 30 de {details.proposals.length} propostas. A revisão completa fica na Operação.
        </p>
      )}
    </Card>
  );
}

