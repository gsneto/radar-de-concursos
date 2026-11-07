import {
  Award,
  BookOpen,
  Building2,
  Calendar,
  CheckCircle2,
  Compass,
  DollarSign,
  Target,
  Trash2,
} from 'lucide-react';
import { Link } from 'react-router-dom';
import { useMyContests, useToggleMyContest } from '@/app/queries';
import { GlowCard } from '@/components/21st/glow-card';
import { PageHeader } from '@/components/layout/page-header';
import { LinkButton } from '@/components/ui/button';
import { Card } from '@/components/ui/card';
import { ErrorState, SkeletonCards } from '@/components/ui/states';
import { shortDate } from '@/lib/format';
import type { MyContest } from '@/lib/types';

export function MyContestsPage() {
  const query = useMyContests();
  const toggleMutation = useToggleMyContest();

  if (query.isLoading) {
    return (
      <>
        <PageHeader
          eyebrow="Painel Pessoal"
          title="Meus Concursos"
          description="Acompanhamento focado dos concursos e cargos que você escolheu prestar."
        />
        <SkeletonCards count={3} />
      </>
    );
  }

  if (query.isError) {
    return (
      <>
        <PageHeader
          eyebrow="Painel Pessoal"
          title="Meus Concursos"
          description="Acompanhamento focado dos concursos e cargos que você escolheu prestar."
        />
        <Card>
          <ErrorState
            message="Não foi possível carregar seus concursos selecionados."
            onRetry={() => query.refetch()}
          />
        </Card>
      </>
    );
  }

  const items = query.data?.itens ?? [];

  return (
    <>
      <PageHeader
        eyebrow="Painel Pessoal de Foco"
        title="Meus Concursos"
        description="Seus concursos selecionados para foco total: prazos críticos, remuneração e direcionamento de estudos."
        actions={
          items.length > 0 ? (
            <LinkButton to="/oportunidades" variant="primary" size="sm" className="gap-1.5">
              <Compass size={14} /> Buscar Mais no Radar
            </LinkButton>
          ) : null
        }
      />

      {items.length === 0 ? (
        /* Estado Inicial Vazio Acolhedor & Direcionado */
        <div className="relative overflow-hidden rounded-xl border border-line/80 bg-surface/80 p-8 sm:p-12 text-center backdrop-blur-sm shadow-xl">
          {/* Fundo decorativo sutil */}
          <div
            aria-hidden="true"
            className="pointer-events-none absolute inset-0 -z-10 bg-[radial-gradient(ellipse_at_top,_var(--tw-gradient-stops))] from-amber-500/10 via-transparent to-transparent opacity-80"
          />

          <div className="mx-auto flex h-16 w-16 items-center justify-center rounded-2xl bg-amber-400/10 border border-amber-400/20 text-amber-400 mb-5 shadow-inner">
            <Target size={32} />
          </div>

          <h2 className="font-display text-2xl font-bold tracking-tight text-fg sm:text-3xl max-w-lg mx-auto">
            Seu Painel de Foco está Vazio
          </h2>

          <p className="mt-3 text-sm text-fg-3 max-w-md mx-auto leading-relaxed">
            O Radar do GSN Concursos varre continuamente os órgãos oficiais para encontrar as melhores oportunidades para você.
            Selecione os certames que você vai prestar para acompanhar os prazos e ativar o seu plano de estudos.
          </p>

          <div className="mt-7 flex flex-wrap items-center justify-center gap-3">
            <LinkButton to="/oportunidades" variant="primary" size="md" className="gap-2 shadow-lg shadow-amber-500/10">
              <Compass size={16} /> Buscar Concursos no Radar
            </LinkButton>
          </div>

          {/* Destaques do que o painel oferece */}
          <div className="mt-12 grid grid-cols-1 sm:grid-cols-3 gap-4 border-t border-line/60 pt-8 text-left max-w-3xl mx-auto">
            <div className="flex items-start gap-3">
              <div className="p-2 rounded-lg bg-surface-2 border border-line text-emerald-400 shrink-0">
                <DollarSign size={16} />
              </div>
              <div>
                <h3 className="text-xs font-semibold text-fg">Remuneração & Vagas</h3>
                <p className="text-2xs text-fg-3 mt-0.5">Informações salariais confirmadas diretamente do edital oficial.</p>
              </div>
            </div>

            <div className="flex items-start gap-3">
              <div className="p-2 rounded-lg bg-surface-2 border border-line text-cyan-400 shrink-0">
                <Calendar size={16} />
              </div>
              <div>
                <h3 className="text-xs font-semibold text-fg">Prazos e Provas</h3>
                <p className="text-2xs text-fg-3 mt-0.5">Contagem regressiva para início/fim das inscrições e aplicação da prova.</p>
              </div>
            </div>

            <div className="flex items-start gap-3">
              <div className="p-2 rounded-lg bg-surface-2 border border-line text-fuchsia-400 shrink-0">
                <BookOpen size={16} />
              </div>
              <div>
                <h3 className="text-xs font-semibold text-fg">Edital Verticalizado</h3>
                <p className="text-2xs text-fg-3 mt-0.5">Disciplinas e tópicos de cada prova para você estudar no próprio GSN.</p>
              </div>
            </div>
          </div>
        </div>
      ) : (
        /* Lista de Concursos Foco Selecionados */
        <div className="space-y-4">
          <div className="flex items-center justify-between text-xs text-fg-3 px-1">
            <span>
              Acompanhando <strong className="text-fg font-medium">{items.length}</strong>{' '}
              {items.length === 1 ? 'concurso prioritário' : 'concursos prioritários'}
            </span>
          </div>

          <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
            {items.map((item) => (
              <MyContestCard
                key={item.id}
                item={item}
                onRemove={() =>
                  toggleMutation.mutate({
                    contestId: item.contest_id,
                    roleId: item.role_id,
                    isSelected: true,
                  })
                }
              />
            ))}
          </div>
        </div>
      )}
    </>
  );
}

function MyContestCard({
  item,
  onRemove,
}: {
  item: MyContest;
  onRemove: () => void;
}) {
  const organTitle = item.orgao || item.contest_label || item.competition_id || 'Concurso Oficial';
  const boardName = item.banca || 'Banca Oficial';
  const roleTitle = item.role_name || 'Cargos de Nível Superior & Técnico';
  const studyHref = `/estudos?concurso=${encodeURIComponent(item.contest_id)}`;
  const dossierHref = `/dossie/${encodeURIComponent(item.contest_id)}`;

  return (
    <GlowCard accent="amber" className="flex flex-col justify-between h-full group p-5">
      <div>
        {/* Cabeçalho do Card: Instituição e Banca */}
        <div className="flex items-start justify-between gap-3 mb-3">
          <div className="min-w-0 flex-1 space-y-1">
            <div className="flex flex-wrap items-center gap-2">
              <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-[11px] font-semibold bg-amber-400/10 text-amber-400 border border-amber-400/20">
                <Award size={12} />
                {boardName}
              </span>
              {item.si_compativel && (
                <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-[11px] font-medium bg-emerald-500/10 text-emerald-400 border border-emerald-500/20">
                  <CheckCircle2 size={12} />
                  Bacharelado em SI Compatível
                </span>
              )}
            </div>

            <div className="flex items-center gap-1.5 text-xs font-semibold text-fg-2 pt-0.5">
              <Building2 size={13} className="text-fg-3 shrink-0" />
              <span className="truncate">{organTitle}</span>
            </div>
          </div>

          <button
            type="button"
            onClick={onRemove}
            title="Remover do meu Painel de Foco"
            aria-label="Remover do meu Painel de Foco"
            className="p-1.5 rounded-md border border-line bg-surface-2/60 text-fg-3 hover:text-rose-400 hover:border-rose-400/40 transition-colors shrink-0"
          >
            <Trash2 size={14} />
          </button>
        </div>

        {/* Cargo e Especialidade em destaque */}
        <div className="mt-2 mb-3">
          <Link
            to={dossierHref}
            className="font-display text-lg font-bold text-fg tracking-tight group-hover:text-amber-300 transition-colors line-clamp-1 block"
          >
            {roleTitle}
          </Link>
          {item.role_specialty && (
            <p className="text-xs text-fg-3 mt-0.5">
              Área: <span className="text-fg-2 font-medium">{item.role_specialty}</span>
            </p>
          )}
        </div>

        {/* Informações de Oportunidade: Salário, Vagas, Prazos */}
        <div className="grid grid-cols-2 sm:grid-cols-3 gap-2.5 my-3.5 p-3 rounded-lg bg-surface-2/40 border border-line/60 text-xs">
          <div>
            <span className="text-fg-3 block text-2xs uppercase tracking-wider">Remuneração</span>
            <span className="font-semibold text-emerald-400 text-sm">
              {item.remuneracao ? String(item.remuneracao).replace(/^"|"$/g, '') : 'Edital Oficial'}
            </span>
          </div>

          <div>
            <span className="text-fg-3 block text-2xs uppercase tracking-wider">Vagas</span>
            <span className="font-semibold text-fg text-sm">
              {typeof item.vagas === 'number' ? `${item.vagas} vaga(s)` : 'Edital'}
            </span>
          </div>

          <div className="col-span-2 sm:col-span-1">
            <span className="text-fg-3 block text-2xs uppercase tracking-wider">
              {item.proximo_prazo?.label || 'Próximo Prazo'}
            </span>
            <span className="font-medium text-amber-300">
              {item.proximo_prazo?.data ? shortDate(item.proximo_prazo.data) : 'Edital aberto'}
            </span>
          </div>
        </div>
      </div>

      {/* Ações: Estudar e Dossiê */}
      <div className="border-t border-line/60 pt-3.5 mt-2 flex items-center justify-between gap-3">
        <Link
          to={dossierHref}
          className="text-xs font-medium text-fg-3 hover:text-fg transition-colors"
        >
          Ver Dossiê Completo
        </Link>

        <LinkButton
          to={studyHref}
          variant="primary"
          size="sm"
          className="gap-1.5 font-semibold shadow-xs"
        >
          <BookOpen size={14} /> Estudar para este Concurso
        </LinkButton>
      </div>
    </GlowCard>
  );
}
