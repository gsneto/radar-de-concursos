import { CheckCircle2, FileCheck2, GitCommitHorizontal, ShieldCheck } from 'lucide-react';
import { Link } from 'react-router-dom';
import { GlowCard } from '@/components/21st/glow-card';
import { Badge } from '@/components/ui/badge';
import { integer, shortDate } from '@/lib/format';
import type { Coverage, Portfolio, Timeline } from '@/lib/types';

const EVENT_LABELS: Record<string, string> = {
  document_discovered: 'Documentos descobertos',
  version_recorded: 'Versões SHA-256 gravadas',
  proposal_extracted: 'Propostas extraídas',
  field_reviewed: 'Revisões humanas aplicadas',
  role_reconciled: 'Cargos reconciliados',
  alert_created: 'Alertas gerados',
};

export function ObservatoryHealthBento({
  coverage,
  timeline,
  portfolio,
}: {
  coverage?: Coverage;
  timeline?: Timeline;
  portfolio?: Portfolio;
}) {
  const escopo = coverage?.escopo;
  const cycles = timeline?.ciclos ?? [];
  const latestCycle = cycles.length > 0 ? cycles[cycles.length - 1] : null;
  const eventEntries = Object.entries(timeline?.eventos ?? {}).filter(([, count]) => count > 0);
  const novos = timeline?.novos;

  const siCompatibleCount = (portfolio?.itens ?? []).filter(
    (it) => it.si?.estado === 'explicito' || it.si?.estado === 'categoria_inclui_curso',
  ).length;
  const indigenousCount = (portfolio?.itens ?? []).filter(
    (it) => it.indigenas?.estado === 'explicito_imediato' || it.indigenas?.estado === 'apenas_reserva',
  ).length;

  return (
    <section
      aria-label="Integridade e rastro operacional"
      className="mt-4 grid grid-cols-1 gap-3 lg:grid-cols-3"
    >
      {/* Card 1: Integridade Documental & Evidências Reais */}
      <GlowCard accent="emerald">
        <div className="mb-3 flex items-center justify-between gap-2">
          <span className="inline-flex items-center gap-1.5 text-xs font-semibold tracking-wider text-fg-2 uppercase">
            <ShieldCheck size={14} className="text-ok" /> Integridade Documental
          </span>
          <Badge tone="ok">Verificável</Badge>
        </div>

        <div className="grid grid-cols-2 gap-2.5">
          <div className="rounded-xl border border-line bg-surface-2 p-3">
            <span className="text-[10px] font-semibold tracking-wider text-fg-3 uppercase">
              Propostas com Evidência
            </span>
            <p className="mt-1 font-display text-xl font-bold tabular text-fg">
              {escopo?.propostas !== undefined ? integer(escopo.propostas) : '—'}
            </p>
          </div>
          <div className="rounded-xl border border-line bg-surface-2 p-3">
            <span className="text-[10px] font-semibold tracking-wider text-fg-3 uppercase">
              Revisões Humanas
            </span>
            <p className="mt-1 font-display text-xl font-bold tabular text-fg">
              {escopo?.auditorias_humanas !== undefined ? integer(escopo.auditorias_humanas) : '—'}
            </p>
          </div>
          <div className="rounded-xl border border-line bg-surface-2 p-3">
            <span className="text-[10px] font-semibold tracking-wider text-fg-3 uppercase">
              Cargos Identificados
            </span>
            <p className="mt-1 font-display text-xl font-bold tabular text-fg">
              {escopo?.cargos_identidade !== undefined ? integer(escopo.cargos_identidade) : '—'}
            </p>
          </div>
          <div className="rounded-xl border border-line bg-surface-2 p-3">
            <span className="text-[10px] font-semibold tracking-wider text-fg-3 uppercase">
              Reconciliações
            </span>
            <p className="mt-1 font-display text-xl font-bold tabular text-fg">
              {escopo?.reconciliacoes_cargo !== undefined ? integer(escopo.reconciliacoes_cargo) : '—'}
            </p>
          </div>
        </div>

        <p className="mt-3 text-2xs text-fg-3 leading-relaxed">
          Nenhum campo extraído por automação entra como confirmado sem evidência documental e hash SHA-256.
        </p>
      </GlowCard>

      {/* Card 2: Rastro Real de Ciclos e Eventos */}
      <GlowCard accent="cyan">
        <div className="mb-3 flex items-center justify-between gap-2">
          <span className="inline-flex items-center gap-1.5 text-xs font-semibold tracking-wider text-fg-2 uppercase">
            <GitCommitHorizontal size={14} className="text-info-ink" /> Rastro da Linha do Tempo
          </span>
          <Link to="/historico" className="text-2xs font-medium text-accent hover:underline">
            Ver tudo
          </Link>
        </div>

        {!latestCycle && eventEntries.length === 0 ? (
          <div className="flex flex-1 flex-col items-center justify-center rounded-xl border border-line bg-surface-2/60 p-4 text-center">
            <p className="text-xs font-semibold text-fg-2">Nenhum evento operacional registrado</p>
            <p className="mt-1 text-2xs text-fg-3">
              Os eventos aparecem aqui assim que o monitoramento registra documentos ou revisões.
            </p>
          </div>
        ) : (
          <div className="space-y-2.5">
            {latestCycle && (
              <div className="rounded-xl border border-line bg-surface-2 p-3 text-xs">
                <div className="flex items-center justify-between gap-2">
                  <span className="font-semibold text-fg">
                    Último ciclo: {shortDate(latestCycle.started_at)}
                  </span>
                  <Badge tone={latestCycle.state === 'concluido' ? 'ok' : 'neutral'}>
                    {latestCycle.state}
                  </Badge>
                </div>
                <p className="mt-1 text-2xs text-fg-3">
                  {integer(latestCycle.documents_new ?? 0)} documento(s) novo(s) ·{' '}
                  {integer(latestCycle.versions_new ?? 0)} versão(ões) nova(s)
                </p>
              </div>
            )}

            {novos && (
              <div className="grid grid-cols-2 gap-2 text-2xs">
                <div className="rounded-lg border border-line bg-surface-2/70 px-2.5 py-2">
                  <span className="text-fg-3 block">Novas propostas</span>
                  <strong className="font-mono text-xs text-fg">{integer(novos.propostas ?? 0)}</strong>
                </div>
                <div className="rounded-lg border border-line bg-surface-2/70 px-2.5 py-2">
                  <span className="text-fg-3 block">Novas revisões</span>
                  <strong className="font-mono text-xs text-fg">{integer(novos.revisoes ?? 0)}</strong>
                </div>
              </div>
            )}

            {eventEntries.slice(0, 3).map(([key, value]) => (
              <div key={key} className="flex items-center justify-between text-2xs border-t border-line/60 pt-1.5">
                <span className="text-fg-2 truncate">{EVENT_LABELS[key] ?? key}</span>
                <span className="font-mono font-semibold text-fg tabular">{integer(value)}</span>
              </div>
            ))}
          </div>
        )}
      </GlowCard>

      {/* Card 3: Recorte de Elegibilidade SI & Reserva Indígena na Amostra */}
      <GlowCard accent="amber">
        <div className="mb-3 flex items-center justify-between gap-2">
          <span className="inline-flex items-center gap-1.5 text-xs font-semibold tracking-wider text-fg-2 uppercase">
            <FileCheck2 size={14} className="text-accent" /> Recorte de Domínio (TI & Cotas)
          </span>
          <Link to="/oportunidades" className="text-2xs font-medium text-accent hover:underline">
            Filtrar Radar
          </Link>
        </div>

        <ul className="space-y-2 text-xs">
          <li className="flex items-center justify-between rounded-xl border border-line bg-surface-2 px-3 py-2.5">
            <span className="flex items-center gap-2 text-fg-2">
              <CheckCircle2 size={14} className="text-ok shrink-0" />
              Editais oficiais localizados
            </span>
            <span className="font-mono font-bold text-fg tabular">
              {escopo?.com_edital_oficial !== undefined ? integer(escopo.com_edital_oficial) : '—'}
            </span>
          </li>
          <li className="flex items-center justify-between rounded-xl border border-line bg-surface-2 px-3 py-2.5">
            <span className="text-fg-2">Compatíveis com SI (destaques)</span>
            <span className="font-mono font-bold text-accent-ink tabular">{integer(siCompatibleCount)}</span>
          </li>
          <li className="flex items-center justify-between rounded-xl border border-line bg-surface-2 px-3 py-2.5">
            <span className="text-fg-2">Com reserva indígena identificada</span>
            <span className="font-mono font-bold text-info-ink tabular">{integer(indigenousCount)}</span>
          </li>
        </ul>

        <p className="mt-3 text-2xs text-fg-3 leading-relaxed">
          Vagas imediatas e cadastro de reserva permanecem separados conforme publicado na fonte oficial.
        </p>
      </GlowCard>
    </section>
  );
}
