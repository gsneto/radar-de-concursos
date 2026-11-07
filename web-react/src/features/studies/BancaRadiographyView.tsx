import { useState } from 'react';
import { useBancas } from '@/app/queries';
import { GlowCard, type Accent } from '@/components/21st/glow-card';
import { SkeletonRows } from '@/components/ui/states';
import {
  AlertTriangle,
  Award,
  BookOpen,
  CheckCircle2,
  Clock,
  Flame,
  Layers,
  Search,
  ShieldAlert,
  ShieldCheck,
  Sparkles,
  Swords,
  Target,
  Zap,
} from 'lucide-react';
import type { BancaProfile } from '@/lib/types';

const CATEGORIES = [
  { id: 'all', label: 'Todas as Bancas', icon: Layers },
  { id: 'federal', label: 'Federais & Nacionais', icon: Flame },
  { id: 'tribunais', label: 'Tribunais & Elite', icon: Award },
  { id: 'conselhos', label: 'Conselhos & Autarquias', icon: Target },
  { id: 'regional', label: 'Municipais & Regionais', icon: BookOpen },
] as const;

// Paleta de gradientes para os avatares das bancas
const BANCA_THEMES: Record<string, { bg: string; text: string; border: string; glow: Accent }> = {
  fgv: { bg: 'from-amber-500/20 to-orange-600/30', text: 'text-amber-400', border: 'border-amber-500/30', glow: 'amber' },
  cebraspe: { bg: 'from-rose-500/20 to-red-700/30', text: 'text-rose-400', border: 'border-rose-500/30', glow: 'fuchsia' },
  fcc: { bg: 'from-violet-500/20 to-purple-700/30', text: 'text-violet-400', border: 'border-violet-500/30', glow: 'indigo' },
  cesgranrio: { bg: 'from-cyan-500/20 to-blue-700/30', text: 'text-cyan-400', border: 'border-cyan-500/30', glow: 'cyan' },
  vunesp: { bg: 'from-emerald-500/20 to-teal-700/30', text: 'text-emerald-400', border: 'border-emerald-500/30', glow: 'emerald' },
  esaf: { bg: 'from-amber-600/20 to-yellow-800/30', text: 'text-amber-300', border: 'border-amber-600/30', glow: 'amber' },
  quadrix: { bg: 'from-blue-500/20 to-indigo-700/30', text: 'text-blue-400', border: 'border-blue-500/30', glow: 'indigo' },
  ibfc: { bg: 'from-teal-500/20 to-emerald-700/30', text: 'text-teal-400', border: 'border-teal-500/30', glow: 'emerald' },
  fepese: { bg: 'from-sky-500/20 to-indigo-700/30', text: 'text-sky-400', border: 'border-sky-500/30', glow: 'cyan' },
  fundatec: { bg: 'from-fuchsia-500/20 to-pink-700/30', text: 'text-fuchsia-400', border: 'border-fuchsia-500/30', glow: 'fuchsia' },
  ibam: { bg: 'from-lime-500/20 to-emerald-700/30', text: 'text-lime-400', border: 'border-lime-500/30', glow: 'emerald' },
  idib: { bg: 'from-orange-500/20 to-amber-700/30', text: 'text-orange-400', border: 'border-orange-500/30', glow: 'amber' },
  consesp: { bg: 'from-slate-500/20 to-zinc-700/30', text: 'text-zinc-300', border: 'border-zinc-500/30', glow: 'indigo' },
  legalle: { bg: 'from-green-500/20 to-emerald-800/30', text: 'text-green-400', border: 'border-green-500/30', glow: 'emerald' },
  consulpam: { bg: 'from-yellow-500/20 to-amber-700/30', text: 'text-yellow-400', border: 'border-yellow-500/30', glow: 'amber' },
  comissao_propria: { bg: 'from-purple-500/20 to-violet-800/30', text: 'text-purple-400', border: 'border-purple-500/30', glow: 'indigo' },
};

export function BancaRadiographyView({
  onSelectBancaSimulado,
}: {
  onSelectBancaSimulado?: (banca: string) => void;
}) {
  const { data, isLoading } = useBancas();
  const [activeBancaId, setActiveBancaId] = useState<string>('fgv');
  const [compareBancaId, setCompareBancaId] = useState<string>('cebraspe');
  const [isComparing, setIsComparing] = useState<boolean>(false);
  const [selectedCategory, setSelectedCategory] = useState<string>('all');
  const [searchTerm, setSearchTerm] = useState<string>('');

  if (isLoading) {
    return <SkeletonRows rows={5} />;
  }

  const bancas = data?.bancas ?? {};
  const bancaList = Object.values(bancas);

  // Filtragem combinada por categoria e busca
  const filteredBancas = bancaList.filter((b) => {
    const matchesCategory =
      selectedCategory === 'all' ||
      b.categoria === selectedCategory ||
      (selectedCategory === 'federal' && (b.id === 'fgv' || b.id === 'cebraspe' || b.id === 'cesgranrio' || b.id === 'esaf')) ||
      (selectedCategory === 'tribunais' && (b.id === 'fcc' || b.id === 'vunesp' || b.id === 'fepese' || b.id === 'comissao_propria')) ||
      (selectedCategory === 'conselhos' && (b.id === 'quadrix' || b.id === 'ibfc' || b.id === 'idib')) ||
      (selectedCategory === 'regional' && (b.id === 'fundatec' || b.id === 'ibam' || b.id === 'consesp' || b.id === 'legalle' || b.id === 'consulpam'));

    const query = searchTerm.toLowerCase().trim();
    const matchesSearch =
      !query ||
      b.nome.toLowerCase().includes(query) ||
      b.id.toLowerCase().includes(query) ||
      (b.top_disciplinas_ti && b.top_disciplinas_ti.some((t) => t.toLowerCase().includes(query)));

    return matchesCategory && matchesSearch;
  });

  const activeBanca: BancaProfile = bancas[activeBancaId] ?? filteredBancas[0] ?? bancaList[0];
  const compareBanca: BancaProfile = bancas[compareBancaId] ?? (activeBancaId === 'fgv' ? bancas['cebraspe'] : bancas['fgv']);
  const activeTheme = BANCA_THEMES[activeBanca?.id] ?? BANCA_THEMES['fgv'];

  return (
    <div className="space-y-6">
      {/* 1. Header Hero com Posicionamento de Alto Valor */}
      <div className="relative overflow-hidden rounded-2xl border border-line bg-gradient-to-br from-surface to-surface-2 p-6 shadow-xl">
        <div className="absolute right-0 top-0 -mr-16 -mt-16 h-64 w-64 rounded-full bg-accent/10 blur-3xl pointer-events-none" />
        <div className="relative z-10 flex flex-col md:flex-row md:items-center justify-between gap-4">
          <div>
            <div className="inline-flex items-center gap-1.5 rounded-full border border-amber-400/30 bg-amber-400/10 px-3 py-1 text-2xs font-bold uppercase tracking-wider text-amber-300">
              <Sparkles size={12} /> Inteligência Estratégica de Prova
            </div>
            <h2 className="mt-2 font-display text-2xl font-bold tracking-tight text-fg sm:text-3xl">
              Radiografia Comparativa de Bancas Examinadoras
            </h2>
            <p className="mt-1 text-xs text-fg-3 max-w-2xl leading-relaxed">
              Descubra os padrões de cobrança, a taxa real de pegadinhas e as métricas de tempo de 16 grandes organizadoras.
              Chegue na prova sabendo exatamente como a banca pensa.
            </p>
          </div>

          <div className="flex items-center gap-2 shrink-0">
            <button
              type="button"
              onClick={() => setIsComparing(!isComparing)}
              className={`flex items-center gap-1.5 rounded-xl border px-3.5 py-2 text-xs font-semibold transition-all ${
                isComparing
                  ? 'border-accent bg-accent/15 text-accent shadow-sm'
                  : 'border-line bg-surface-2 text-fg-2 hover:border-line-strong hover:text-fg'
              }`}
            >
              <Swords size={15} />
              {isComparing ? 'Fechar Comparador' : 'Modo Duelo (VS)'}
            </button>

            {onSelectBancaSimulado && (
              <button
                type="button"
                onClick={() => onSelectBancaSimulado(activeBanca.id)}
                className="flex items-center gap-2 rounded-xl bg-accent px-4 py-2 text-xs font-bold uppercase tracking-wider text-white shadow-lg shadow-accent/20 hover:bg-accent/90 transition-all hover:scale-[1.02] active:scale-[0.98]"
              >
                <Zap size={14} /> Simulado {activeBanca.id.toUpperCase()}
              </button>
            )}
          </div>
        </div>

        {/* Barra de Filtros por Categoria & Busca */}
        <div className="mt-6 flex flex-col sm:flex-row items-stretch sm:items-center justify-between gap-3 border-t border-line/60 pt-4">
          <div className="flex flex-wrap gap-1.5">
            {CATEGORIES.map((cat) => {
              const Icon = cat.icon;
              const isSelected = selectedCategory === cat.id;
              return (
                <button
                  key={cat.id}
                  type="button"
                  onClick={() => setSelectedCategory(cat.id)}
                  className={`flex items-center gap-1.5 rounded-lg px-2.5 py-1 text-2xs font-semibold tracking-wide transition-colors ${
                    isSelected
                      ? 'bg-fg text-surface shadow-xs font-bold'
                      : 'bg-surface-2/60 text-fg-3 border border-line/60 hover:text-fg hover:border-line'
                  }`}
                >
                  <Icon size={12} />
                  {cat.label}
                </button>
              );
            })}
          </div>

          <div className="relative w-full sm:w-60">
            <Search size={13} className="absolute left-2.5 top-1/2 -translate-y-1/2 text-fg-3" />
            <input
              type="text"
              placeholder="Buscar por sigla ou assunto..."
              value={searchTerm}
              onChange={(e) => setSearchTerm(e.target.value)}
              className="w-full rounded-lg border border-line bg-surface-2/80 pl-8 pr-3 py-1.5 text-xs text-fg placeholder:text-fg-3 focus:border-accent focus:outline-none"
            />
          </div>
        </div>
      </div>

      {/* 2. Grid Interativo de Cards das Bancas (Visual SaaS Moderno) */}
      <div>
        <div className="mb-2 flex items-center justify-between text-2xs text-fg-3 px-1">
          <span>Selecione a banca para carregar o DNA de prova:</span>
          <span><strong>{filteredBancas.length}</strong> organizadoras filtradas</span>
        </div>

        <div className="grid grid-cols-2 sm:grid-cols-4 lg:grid-cols-8 gap-2.5">
          {filteredBancas.map((banca) => {
            const isSelected = activeBanca.id === banca.id;
            const theme = BANCA_THEMES[banca.id] ?? BANCA_THEMES['fgv'];
            const difficulty = banca.dificuldade ?? 8.0;

            return (
              <button
                key={banca.id}
                type="button"
                onClick={() => {
                  setActiveBancaId(banca.id);
                  if (isComparing && compareBancaId === banca.id) {
                    setCompareBancaId(activeBancaId);
                  }
                }}
                className={`group relative flex flex-col justify-between rounded-xl border p-2.5 text-left transition-all hover:scale-[1.02] ${
                  isSelected
                    ? `border-accent bg-surface-2 shadow-md shadow-accent/10 ring-1 ring-accent`
                    : 'border-line/70 bg-surface/80 hover:border-line-strong hover:bg-surface-2/50'
                }`}
              >
                <div>
                  <div className="flex items-center justify-between gap-1 mb-1.5">
                    <span
                      className={`inline-flex items-center justify-center h-6 px-1.5 rounded-md text-[10px] font-black uppercase tracking-wider bg-gradient-to-br ${theme.bg} ${theme.text} border ${theme.border}`}
                    >
                      {banca.id.replace('_', ' ').slice(0, 6)}
                    </span>
                    <span className="text-[10px] font-bold text-amber-400/90">
                      ★ {difficulty.toFixed(1)}
                    </span>
                  </div>

                  <h4 className="text-xs font-semibold text-fg truncate group-hover:text-amber-300 transition-colors">
                    {banca.nome.split('(')[0].trim()}
                  </h4>
                </div>

                <div className="mt-2 pt-1 border-t border-line/40 flex items-center justify-between text-[10px] text-fg-3">
                  <span className="truncate max-w-[70px]">
                    {banca.estilo_predominante?.includes('Certo') ? 'C/E' : 'M. Escolha'}
                  </span>
                  {banca.id === 'cebraspe' && (
                    <span className="text-rose-400 font-bold" title="Erro anula acerto">
                      -1pt
                    </span>
                  )}
                </div>
              </button>
            );
          })}
        </div>
      </div>

      {/* 3. MODO COMPRADOR (DUELO DE BANCAS LADO A LADO) */}
      {isComparing ? (
        <div className="space-y-4">
          <div className="flex items-center justify-between rounded-xl border border-line bg-surface-2/80 p-3">
            <div className="flex items-center gap-2">
              <Swords className="text-accent" size={18} />
              <span className="text-xs font-bold text-fg uppercase tracking-wider">
                Duelo Direto: {activeBanca.nome.split('(')[0]} VS {compareBanca.nome.split('(')[0]}
              </span>
            </div>

            <div className="flex items-center gap-2">
              <span className="text-2xs text-fg-3">Comparar com:</span>
              <select
                value={compareBancaId}
                onChange={(e) => setCompareBancaId(e.target.value)}
                className="rounded-md border border-line bg-surface px-2.5 py-1 text-xs text-fg focus:border-accent focus:outline-none"
              >
                {bancaList
                  .filter((b) => b.id !== activeBanca.id)
                  .map((b) => (
                    <option key={b.id} value={b.id}>
                      {b.nome}
                    </option>
                  ))}
              </select>
            </div>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <BancaDetailedCard banca={activeBanca} onSelectSimulado={onSelectBancaSimulado} isVersus />
            <BancaDetailedCard banca={compareBanca} onSelectSimulado={onSelectBancaSimulado} isVersus />
          </div>
        </div>
      ) : (
        /* 4. VISÃO DETALHADA E BENTO DASHBOARD DA BANCA ATIVA */
        <BancaDetailedCard
          banca={activeBanca}
          onSelectSimulado={onSelectBancaSimulado}
          theme={activeTheme}
        />
      )}
    </div>
  );
}

function BancaDetailedCard({
  banca,
  onSelectSimulado,
  theme,
  isVersus = false,
}: {
  banca: BancaProfile;
  onSelectSimulado?: (banca: string) => void;
  theme?: { bg: string; text: string; border: string; glow: string };
  isVersus?: boolean;
}) {
  const currentTheme = theme ?? BANCA_THEMES[banca.id] ?? BANCA_THEMES['fgv'];
  const difficulty = banca.dificuldade ?? 8.0;
  const trapsIndex = banca.indice_pegadinhas ?? 65;
  const breakdown = banca.perfil_cobranca ?? { interpretacao: 40, doutrina_jurisprudencia: 30, lei_seca: 30 };
  const pace = banca.tempo_medio_questao ?? '2 min (Equilibrado)';
  const penalty = banca.fator_chute ?? banca.regras_pontuacao;
  const isCebraspeStyle = banca.id === 'cebraspe' || (penalty && penalty.includes('Anula'));

  return (
    <GlowCard accent={isCebraspeStyle ? 'fuchsia' : 'amber'} className="p-6 space-y-6">
      {/* Top Header do Perfil */}
      <div className="flex flex-col sm:flex-row sm:items-start justify-between gap-4 border-b border-line pb-5">
        <div className="flex items-start gap-3.5">
          <div
            className={`flex h-12 w-12 shrink-0 items-center justify-center rounded-xl bg-gradient-to-br ${currentTheme.bg} border ${currentTheme.border} text-lg font-black uppercase ${currentTheme.text} shadow-inner`}
          >
            {banca.id.slice(0, 3).toUpperCase()}
          </div>

          <div>
            <div className="flex flex-wrap items-center gap-2">
              <h3 className="font-display text-lg sm:text-xl font-bold text-fg tracking-tight">
                {banca.nome}
              </h3>
              {banca.categoria_label && (
                <span className="rounded-full bg-surface-2 px-2.5 py-0.5 text-2xs font-semibold text-fg-3 border border-line">
                  {banca.categoria_label}
                </span>
              )}
            </div>

            <p className="mt-1 text-xs text-fg-3">
              <span className="font-semibold text-fg-2">Formato Principal:</span> {banca.estilo_predominante}
            </p>
          </div>
        </div>

        {/* Fator de Chute / Risco Badge */}
        <div className="shrink-0 flex sm:flex-col items-center sm:items-end justify-between gap-1.5">
          <span className="text-2xs uppercase tracking-wider text-fg-3 font-semibold">Política de Chute</span>
          <div
            className={`inline-flex items-center gap-1.5 px-3 py-1 rounded-full text-xs font-bold ${
              isCebraspeStyle
                ? 'bg-rose-500/10 text-rose-400 border border-rose-500/30'
                : 'bg-emerald-500/10 text-emerald-400 border border-emerald-500/30'
            }`}
          >
            {isCebraspeStyle ? <ShieldAlert size={13} /> : <ShieldCheck size={13} />}
            <span>{penalty}</span>
          </div>
        </div>
      </div>

      {/* Radar de Métricas Visuais (DNA da Prova) */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-3">
        {/* KPI 1: Dificuldade */}
        <div className="rounded-xl border border-line/60 bg-surface-2/40 p-3">
          <div className="flex items-center justify-between text-2xs text-fg-3 font-semibold uppercase tracking-wider mb-1">
            <span>Dificuldade Geral</span>
            <span className="text-amber-400 font-bold">{difficulty.toFixed(1)} / 10</span>
          </div>
          <div className="h-2 w-full rounded-full bg-surface-2 overflow-hidden">
            <div
              className="h-full rounded-full bg-gradient-to-r from-amber-500 to-rose-500 transition-all duration-500"
              style={{ width: `${(difficulty / 10) * 100}%` }}
            />
          </div>
          <p className="mt-1.5 text-2xs text-fg-3">
            {difficulty >= 9.0 ? 'Exigência extrema e nota de corte disputada' : difficulty >= 7.5 ? 'Nível intermediário-alto' : 'Conceitual direto'}
          </p>
        </div>

        {/* KPI 2: Pegadinhas */}
        <div className="rounded-xl border border-line/60 bg-surface-2/40 p-3">
          <div className="flex items-center justify-between text-2xs text-fg-3 font-semibold uppercase tracking-wider mb-1">
            <span>Índice de Pegadinhas</span>
            <span className={trapsIndex > 70 ? 'text-rose-400 font-bold' : 'text-emerald-400 font-bold'}>
              {trapsIndex}%
            </span>
          </div>
          <div className="h-2 w-full rounded-full bg-surface-2 overflow-hidden">
            <div
              className={`h-full rounded-full transition-all duration-500 ${
                trapsIndex > 70 ? 'bg-gradient-to-r from-orange-500 to-rose-600' : 'bg-gradient-to-r from-teal-500 to-emerald-500'
              }`}
              style={{ width: `${trapsIndex}%` }}
            />
          </div>
          <p className="mt-1.5 text-2xs text-fg-3">
            {trapsIndex > 70 ? 'Cuidado máximo com sutilezas semânticas' : 'Enunciados transparentes e literais'}
          </p>
        </div>

        {/* KPI 3: Ritmo da Prova */}
        <div className="rounded-xl border border-line/60 bg-surface-2/40 p-3">
          <div className="flex items-center gap-1.5 text-2xs text-fg-3 font-semibold uppercase tracking-wider mb-1">
            <Clock size={12} className="text-cyan-400" />
            <span>Gestão de Tempo</span>
          </div>
          <span className="text-xs font-bold text-fg block truncate">{pace}</span>
          <p className="mt-1 text-2xs text-fg-3">
            {pace.includes('Longos') || pace.includes('Denso')
              ? 'Pule textos longos na 1ª rodada'
              : 'Resolução dinâmica sem perda de ritmo'}
          </p>
        </div>

        {/* KPI 4: Composição de Prova */}
        <div className="rounded-xl border border-line/60 bg-surface-2/40 p-3">
          <div className="flex items-center justify-between text-2xs text-fg-3 font-semibold uppercase tracking-wider mb-1">
            <span>Perfil de Cobrança</span>
          </div>
          <div className="flex h-2 w-full rounded-full overflow-hidden bg-surface-2">
            <div style={{ width: `${breakdown.interpretacao}%` }} className="bg-amber-400" title={`Interpretação: ${breakdown.interpretacao}%`} />
            <div style={{ width: `${breakdown.doutrina_jurisprudencia}%` }} className="bg-indigo-400" title={`Doutrina/Juris: ${breakdown.doutrina_jurisprudencia}%`} />
            <div style={{ width: `${breakdown.lei_seca}%` }} className="bg-emerald-400" title={`Lei Seca: ${breakdown.lei_seca}%`} />
          </div>
          <div className="mt-1.5 flex items-center justify-between text-[10px] text-fg-3">
            <span className="text-amber-300 font-medium">Interp: {breakdown.interpretacao}%</span>
            <span className="text-indigo-300 font-medium">Dout: {breakdown.doutrina_jurisprudencia}%</span>
            <span className="text-emerald-300 font-medium">Lei: {breakdown.lei_seca}%</span>
          </div>
        </div>
      </div>

      {/* Bento Grid: TI, Pegadinhas e Estratégia de Prova */}
      <div className={`grid gap-4 ${isVersus ? 'grid-cols-1' : 'grid-cols-1 lg:grid-cols-3'}`}>
        {/* Card 1: Foco em TI & Sistemas de Informação */}
        <div className="rounded-xl border border-line/70 bg-surface-2/30 p-4 space-y-3">
          <div className="flex items-center gap-2 text-xs font-bold uppercase tracking-wider text-emerald-400">
            <Sparkles size={15} />
            <span>Foco em TI & Sistemas de Informação</span>
          </div>

          {banca.top_disciplinas_ti && banca.top_disciplinas_ti.length > 0 && (
            <div className="flex flex-wrap gap-1.5">
              {banca.top_disciplinas_ti.map((topic, i) => (
                <span
                  key={i}
                  className="rounded-md border border-emerald-500/20 bg-emerald-500/10 px-2 py-0.5 text-2xs font-semibold text-emerald-300"
                >
                  {topic}
                </span>
              ))}
            </div>
          )}

          <ul className="space-y-2 text-xs text-fg-2 pt-1">
            {banca.dicas_ti.slice(0, 3).map((dica, i) => (
              <li key={i} className="flex items-start gap-2">
                <CheckCircle2 size={14} className="mt-0.5 shrink-0 text-emerald-400" />
                <span className="leading-snug">{dica}</span>
              </li>
            ))}
          </ul>
        </div>

        {/* Card 2: Armadilhas Recorrentes & Expressões de Alerta */}
        <div className="rounded-xl border border-line/70 bg-surface-2/30 p-4 space-y-3">
          <div className="flex items-center gap-2 text-xs font-bold uppercase tracking-wider text-amber-400">
            <AlertTriangle size={15} />
            <span>Termos de Alerta & Gatilhos</span>
          </div>

          <p className="text-2xs text-fg-3">
            Expressões frequentes na banca que frequentemente tornam o item incorreto ou exigem dupla checagem:
          </p>

          <div className="flex flex-wrap gap-1.5 pt-1">
            {banca.palavras_chave_alerta.map((termo, i) => (
              <span
                key={i}
                className="rounded-md border border-amber-500/30 bg-amber-500/10 px-2.5 py-1 text-2xs font-bold text-amber-300"
              >
                {termo}
              </span>
            ))}
          </div>

          <div className="rounded-lg bg-surface-2/60 border border-line/50 p-2.5 text-2xs text-fg-3">
            💡 <strong>Regra prática:</strong> Quando encontrar um desses termos, procure a exceção antes de marcar a assertiva.
          </div>
        </div>

        {/* Card 3: Estratégia de Prova Recomendada */}
        <div className="rounded-xl border border-line/70 bg-surface-2/30 p-4 space-y-3">
          <div className="flex items-center gap-2 text-xs font-bold uppercase tracking-wider text-cyan-400">
            <Target size={15} />
            <span>Tática de Guerra no Dia da Prova</span>
          </div>

          <ul className="space-y-2.5 text-xs text-fg-2">
            {banca.dicas_gerais.map((dica, i) => (
              <li key={i} className="flex items-start gap-2.5">
                <span className="flex h-4 w-4 shrink-0 items-center justify-center rounded-full bg-cyan-400/10 text-cyan-400 border border-cyan-400/30 text-[10px] font-bold">
                  {i + 1}
                </span>
                <span className="leading-snug">{dica}</span>
              </li>
            ))}
            <li className="flex items-start gap-2.5">
              <span className="flex h-4 w-4 shrink-0 items-center justify-center rounded-full bg-cyan-400/10 text-cyan-400 border border-cyan-400/30 text-[10px] font-bold">
                ✓
              </span>
              <span className="leading-snug text-fg-3">
                Preencha o gabarito com 30 minutos de margem de segurança.
              </span>
            </li>
          </ul>

          {onSelectSimulado && (
            <div className="pt-2">
              <button
                type="button"
                onClick={() => onSelectSimulado(banca.id)}
                className="w-full flex items-center justify-center gap-2 rounded-lg bg-accent/20 border border-accent/40 px-3 py-2 text-xs font-bold uppercase tracking-wider text-amber-300 hover:bg-accent hover:text-white transition-all shadow-xs"
              >
                <Zap size={14} /> Fazer Simulado Focado na {banca.id.toUpperCase()}
              </button>
            </div>
          )}
        </div>
      </div>
    </GlowCard>
  );
}
