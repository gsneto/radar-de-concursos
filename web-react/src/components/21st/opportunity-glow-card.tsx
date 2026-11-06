import { Calendar, ChevronRight, GraduationCap, MapPin, Sparkles } from 'lucide-react';
import { Link } from 'react-router-dom';
import { GlowCard, type Accent } from './glow-card';
import { Badge } from '@/components/ui/badge';
import {
  indigenousShort,
  indigenousTones,
  readinessTones,
  siShort,
  siTones,
} from '@/lib/domain';
import { nextOperationalDeadline } from '@/lib/deadlines';
import { relativeDays, shortDate } from '@/lib/format';
import type { Opportunity } from '@/lib/types';

interface OpportunityGlowCardProps {
  item: Opportunity;
}

function urgencyTone(urgencia: string): 'risk' | 'warn' | 'neutral' {
  if (urgencia === 'vencido') return 'neutral';
  if (urgencia === 'ate_7_dias' || urgencia === 'hoje') return 'risk';
  return 'warn';
}

export function OpportunityGlowCard({ item }: OpportunityGlowCardProps) {
  const deadline = nextOperationalDeadline(item.prazos);
  const prova = item.localizacao?.prova;
  const isRegional = prova?.uf === 'BA' || prova?.uf === 'PE';

  let accent: Accent = 'indigo';
  if (item.si?.estado === 'explicito' || item.si?.estado === 'categoria_inclui_curso') {
    accent = 'emerald';
  } else if (deadline && typeof deadline.dias_restantes === 'number' && deadline.dias_restantes <= 7) {
    accent = 'amber';
  } else if (item.indigenas?.estado === 'explicito_imediato' || item.indigenas?.estado === 'apenas_reserva') {
    accent = 'fuchsia';
  } else if (isRegional) {
    accent = 'cyan';
  }

  const params = new URLSearchParams();
  if (item.scope) params.set('scope', item.scope);
  params.set('from', 'oportunidades');
  const dossierHref = `/dossie/${item.contest_id}${params.size ? `?${params}` : ''}`;

  const roleTitle = item.role_name ?? 'Cargo não reconciliado';
  const organTitle = item.contest_label ?? item.competition_id ?? 'Concurso';
  const locationText = prova?.text ?? prova?.uf ?? (prova?.state === 'a_divulgar' ? 'A divulgar' : 'Não informado');

  return (
    <GlowCard accent={accent} className="group flex flex-col justify-between h-full">
      {/* Topo do Card: Órgão e Status */}
      <div>
        <div className="flex items-start justify-between gap-3 mb-2">
          <div className="min-w-0 flex-1">
            <span className="text-[11px] font-medium tracking-wide text-fg-3 uppercase truncate block">
              {organTitle}
            </span>
            <Link
              to={dossierHref}
              className="font-display text-base font-semibold text-fg tracking-tight group-hover:text-white transition-colors line-clamp-1 mt-0.5 block"
            >
              {roleTitle}
            </Link>
          </div>
          {item.prontidao && (
            <Badge tone={readinessTones[item.prontidao.estado] ?? 'unknown'} className="shrink-0 text-[10px]">
              {item.prontidao.estado_label}
            </Badge>
          )}
        </div>

        {/* Localização e Distância */}
        <div className="flex flex-wrap items-center gap-x-3 gap-y-1 text-xs text-fg-3 mb-3.5">
          <span className="inline-flex items-center gap-1">
            <MapPin size={12} className="text-slate-400" />
            {locationText}
          </span>
          {isRegional && (
            <span className="inline-flex items-center gap-1 text-cyan-300 font-mono text-[10px] bg-cyan-950/40 px-1.5 py-0.5 rounded-sm border border-cyan-800/40">
              📍 Região Nordeste / Paulo Afonso
            </span>
          )}
        </div>

        {/* Badges de Formação e Cotas */}
        <div className="flex flex-wrap gap-1.5 mb-4">
          {item.si?.estado && item.si.estado !== 'nao_informado' && item.si.estado !== 'nao_encontrado' && (
            <Badge tone={siTones[item.si.estado] ?? 'neutral'} className="gap-1 text-2xs">
              <GraduationCap size={11} />
              SI: {siShort[item.si.estado] ?? item.si.estado}
            </Badge>
          )}

          {item.indigenas?.estado && item.indigenas.estado !== 'nao_mencionado' && (
            <Badge tone={indigenousTones[item.indigenas.estado] ?? 'neutral'} className="gap-1 text-2xs">
              <Sparkles size={11} />
              {indigenousShort[item.indigenas.estado] ?? item.indigenas.estado}
            </Badge>
          )}
        </div>
      </div>

      {/* Rodapé: Prazos e Ação */}
      <div className="border-t border-line/60 pt-3 mt-auto">
        <div className="flex items-center justify-between gap-2">
          {deadline ? (
            <div className="min-w-0 flex items-center gap-1.5 text-xs">
              <Calendar size={13} className="text-slate-400 shrink-0" />
              <div className="truncate">
                <span className="text-fg-3">{deadline.grupo_label}: </span>
                <span className="font-semibold text-fg">{shortDate(deadline.valor)}</span>
              </div>
              <Badge tone={urgencyTone(deadline.urgencia)} className="text-[10px] ml-1">
                {relativeDays(deadline.dias_restantes)}
              </Badge>
            </div>
          ) : (
            <span className="text-2xs text-fg-3">Sem prazo futuro</span>
          )}

          <Link
            to={dossierHref}
            className="inline-flex items-center gap-0.5 text-xs font-medium text-accent hover:text-accent-hover transition-colors ml-auto group-hover:translate-x-0.5 transform duration-200"
          >
            Dossiê <ChevronRight size={13} />
          </Link>
        </div>
      </div>
    </GlowCard>
  );
}
