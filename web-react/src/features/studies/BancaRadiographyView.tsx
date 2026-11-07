import { useState } from 'react';
import { useBancas } from '@/app/queries';
import { Badge } from '@/components/ui/badge';
import { Card } from '@/components/ui/card';
import { SkeletonRows } from '@/components/ui/states';
import { AlertTriangle, BookOpen, CheckCircle, ShieldAlert, Sparkles } from 'lucide-react';

export function BancaRadiographyView({ onSelectBancaSimulado }: { onSelectBancaSimulado?: (banca: string) => void }) {
  const { data, isLoading } = useBancas();
  const [activeBancaId, setActiveBancaId] = useState<string>('fgv');

  if (isLoading) {
    return <SkeletonRows rows={4} />;
  }

  const bancas = data?.bancas ?? {};
  const activeBanca = bancas[activeBancaId] ?? Object.values(bancas)[0];

  return (
    <div className="space-y-4">
      <Card
        title="Radiografia Comparativa de Bancas Examinadoras"
        subtitle="Entenda como FGV, Cebraspe, Quadrix e IBFC estruturam suas provas, formulam pegadinhas e penalizam chutes."
      >
        {/* Banca Selector Pills */}
        <div className="flex flex-wrap gap-2 border-b border-line pb-3">
          {Object.values(bancas).map((banca) => (
            <button
              key={banca.id}
              type="button"
              onClick={() => setActiveBancaId(banca.id)}
              className={`rounded-md px-3 py-1.5 text-xs font-semibold uppercase tracking-wider transition-colors ${
                activeBanca?.id === banca.id
                  ? 'bg-accent text-white shadow-sm'
                  : 'bg-surface-2 text-fg-3 border border-line hover:text-fg hover:border-line-strong'
              }`}
            >
              {banca.id.toUpperCase()} · {banca.nome.split('(')[0].trim()}
            </button>
          ))}
        </div>

        {activeBanca && (
          <div className="mt-4 space-y-4">
            {/* Header / Summary */}
            <div className="flex flex-wrap items-center justify-between gap-3 rounded-lg border border-line-strong bg-surface-2 p-3">
              <div>
                <h3 className="text-sm font-bold text-fg">{activeBanca.nome}</h3>
                <p className="mt-0.5 text-xs text-fg-3">
                  <span className="font-medium text-fg-2">Formato:</span> {activeBanca.estilo_predominante}
                </p>
              </div>
              <Badge
                tone={
                  activeBanca.id === 'cebraspe'
                    ? 'risk'
                    : activeBanca.id === 'quadrix'
                    ? 'warn'
                    : 'ok'
                }
                className="text-xs py-1 px-2.5"
              >
                {activeBanca.regras_pontuacao}
              </Badge>
            </div>

            {/* Warning Callout for Penalty Rules */}
            {activeBanca.id === 'cebraspe' && (
              <div className="flex items-start gap-2.5 rounded-md border border-risk/40 bg-risk/10 p-3 text-xs text-risk">
                <ShieldAlert size={16} className="mt-0.5 shrink-0" />
                <div>
                  <span className="font-bold">Regra de Ouro do Cebraspe:</span> Erro anula acerto. Se estiver em dúvida genuína sem base de eliminação, deixar o item em branco é a estratégia matematicamente superior para proteger a pontuação líquida.
                </div>
              </div>
            )}

            {/* Grid: Características & Dicas TI */}
            <div className="grid gap-4 md:grid-cols-2">
              <div className="space-y-2 rounded-lg border border-line bg-surface p-3.5">
                <div className="flex items-center gap-1.5 text-xs font-semibold uppercase tracking-wider text-accent">
                  <BookOpen size={14} /> Estilo de Prova & Perfil
                </div>
                <ul className="space-y-1.5 text-xs text-fg-2">
                  {activeBanca.caracteristicas.map((c, i) => (
                    <li key={i} className="flex items-start gap-1.5">
                      <span className="text-accent mt-0.5 font-bold">·</span>
                      <span>{c}</span>
                    </li>
                  ))}
                </ul>
              </div>

              <div className="space-y-2 rounded-lg border border-line bg-surface p-3.5">
                <div className="flex items-center gap-1.5 text-xs font-semibold uppercase tracking-wider text-emerald-400">
                  <Sparkles size={14} /> Foco em Tecnologia da Informação
                </div>
                <ul className="space-y-1.5 text-xs text-fg-2">
                  {activeBanca.dicas_ti.map((d, i) => (
                    <li key={i} className="flex items-start gap-1.5">
                      <CheckCircle size={13} className="text-emerald-400 mt-0.5 shrink-0" />
                      <span>{d}</span>
                    </li>
                  ))}
                </ul>
              </div>
            </div>

            {/* Dicas Gerais & Palavras de Alerta */}
            <div className="grid gap-4 md:grid-cols-2">
              <div className="space-y-2 rounded-lg border border-line bg-surface p-3.5">
                <div className="text-xs font-semibold uppercase tracking-wider text-fg-3">
                  Estratégia de Resolução
                </div>
                <ul className="space-y-1.5 text-xs text-fg-2">
                  {activeBanca.dicas_gerais.map((d, i) => (
                    <li key={i} className="flex items-start gap-1.5">
                      <span className="text-fg-3 mt-0.5">›</span>
                      <span>{d}</span>
                    </li>
                  ))}
                </ul>
              </div>

              <div className="space-y-2 rounded-lg border border-line bg-surface p-3.5">
                <div className="flex items-center gap-1.5 text-xs font-semibold uppercase tracking-wider text-amber-400">
                  <AlertTriangle size={14} /> Termos de Alerta & Pegadinhas
                </div>
                <p className="text-2xs text-fg-3">
                  Expressões que frequentemente tornam o item incorreto ou exigem verificação redobrada:
                </p>
                <div className="flex flex-wrap gap-1.5 pt-1">
                  {activeBanca.palavras_chave_alerta.map((termo, i) => (
                    <span
                      key={i}
                      className="rounded border border-amber-500/30 bg-amber-500/10 px-2 py-0.5 text-2xs font-medium text-amber-300"
                    >
                      {termo}
                    </span>
                  ))}
                </div>
              </div>
            </div>

            {onSelectBancaSimulado && (
              <div className="pt-2">
                <button
                  type="button"
                  onClick={() => onSelectBancaSimulado(activeBanca.id)}
                  className="rounded-md bg-accent px-4 py-2 text-xs font-bold uppercase tracking-wider text-white hover:bg-accent/90 transition-colors"
                >
                  Criar Simulado Específico da {activeBanca.id.toUpperCase()}
                </button>
              </div>
            )}
          </div>
        )}
      </Card>
    </div>
  );
}
