import { useState } from 'react';
import { Check, Eye, EyeOff, RotateCcw, Sparkles, Star, Zap } from 'lucide-react';
import type { LessonFlashcard } from '@/lib/types';

interface JottaFlashcardGridProps {
  cards: LessonFlashcard[];
  savedFlashcards: Record<string, boolean>;
  favoriteFlashcards: Record<string, boolean>;
  cardDifficultyRatings: Record<string, string>;
  onSaveCard: (card: LessonFlashcard, ratingLabel?: string) => void;
  onToggleFavorite: (cardId: string) => void;
  showLessonBadge?: boolean;
  onSelectLesson?: (lessonId: string) => void;
}

const COLOR_STYLES: Record<
  string,
  {
    termBox: string;
    termText: string;
    letterBadge: string;
    stemLine: string;
    pillBorder: string;
    pillText: string;
    cardAccent: string;
  }
> = {
  amber: {
    termBox: 'bg-amber-500/20 border-amber-400/50',
    termText: 'text-amber-300',
    letterBadge: 'bg-amber-400 text-slate-950',
    stemLine: 'bg-amber-400',
    pillBorder: 'border-amber-400/60 bg-amber-500/10',
    pillText: 'text-amber-200',
    cardAccent: 'border-t-amber-400',
  },
  sky: {
    termBox: 'bg-sky-500/20 border-sky-400/50',
    termText: 'text-sky-300',
    letterBadge: 'bg-sky-400 text-slate-950',
    stemLine: 'bg-sky-400',
    pillBorder: 'border-sky-400/60 bg-sky-500/10',
    pillText: 'text-sky-200',
    cardAccent: 'border-t-sky-400',
  },
  emerald: {
    termBox: 'bg-emerald-500/20 border-emerald-400/50',
    termText: 'text-emerald-300',
    letterBadge: 'bg-emerald-400 text-slate-950',
    stemLine: 'bg-emerald-400',
    pillBorder: 'border-emerald-400/60 bg-emerald-500/10',
    pillText: 'text-emerald-200',
    cardAccent: 'border-t-emerald-400',
  },
  rose: {
    termBox: 'bg-rose-500/20 border-rose-400/50',
    termText: 'text-rose-300',
    letterBadge: 'bg-rose-400 text-slate-950',
    stemLine: 'bg-rose-400',
    pillBorder: 'border-rose-400/60 bg-rose-500/10',
    pillText: 'text-rose-200',
    cardAccent: 'border-t-rose-400',
  },
};

export function JottaFlashcardGrid({
  cards,
  savedFlashcards,
  favoriteFlashcards,
  cardDifficultyRatings,
  onSaveCard,
  onToggleFavorite,
  showLessonBadge = false,
  onSelectLesson,
}: JottaFlashcardGridProps) {
  // Modo 'visual' (Poster Estilo Jotta visível de imediato) vs 'quiz' (Oculta esquema até clicar)
  const [studyMode, setStudyMode] = useState<'visual' | 'quiz'>('visual');
  const [revealedQuizCards, setRevealedQuizCards] = useState<Record<string, boolean>>({});
  const [interactiveGuesses, setInteractiveGuesses] = useState<Record<string, string>>({});

  const toggleReveal = (id: string) => {
    setRevealedQuizCards((prev) => ({ ...prev, [id]: !prev[id] }));
  };

  return (
    <div className="space-y-5">
      {/* Barra de Controle Clara e Direta */}
      <div className="flex flex-wrap items-center justify-between gap-3 rounded-2xl border border-line-strong bg-surface-2/90 p-4 shadow-sm">
        <div className="space-y-0.5">
          <div className="flex items-center gap-2">
            <span className="inline-flex items-center gap-1.5 rounded-md bg-amber-400 px-2.5 py-0.5 text-xs font-extrabold uppercase tracking-wider text-slate-950">
              <Sparkles size={13} /> Mapas & Flashcards Visuais
            </span>
            <span className="text-xs font-bold text-fg-2">
              {cards.length} {cards.length === 1 ? 'ficha esquematizada' : 'fichas esquematizadas'}
            </span>
          </div>
          <p className="text-xs text-fg-2">
            Fichas visuais estilo <strong>Dica Esquematizada</strong> com gatilhos de letras, contrastes lado a lado e regras de prova.
          </p>
        </div>

        {/* Seletor de Modo: Mapa Visual Aberto vs Modo Pergunta/Teste */}
        <div className="flex items-center gap-1.5 rounded-xl border border-line-strong bg-surface p-1">
          <button
            type="button"
            onClick={() => setStudyMode('visual')}
            className={`flex items-center gap-1.5 rounded-lg px-3 py-1.5 text-xs font-bold transition-all ${
              studyMode === 'visual'
                ? 'bg-amber-400 text-slate-950 shadow-sm'
                : 'text-fg-2 hover:text-fg'
            }`}
          >
            <Eye size={14} /> Modo Mapa Visual (Aberto)
          </button>
          <button
            type="button"
            onClick={() => {
              setStudyMode('quiz');
              setRevealedQuizCards({});
            }}
            className={`flex items-center gap-1.5 rounded-lg px-3 py-1.5 text-xs font-bold transition-all ${
              studyMode === 'quiz'
                ? 'bg-amber-400 text-slate-950 shadow-sm'
                : 'text-fg-2 hover:text-fg'
            }`}
          >
            <EyeOff size={14} /> Modo Teste de Memória
          </button>
        </div>
      </div>

      {/* Grade de Cartões Estilo Jotta */}
      <div className="grid gap-6 xl:grid-cols-2">
        {cards.map((fc, idx) => {
          const schema = fc.esquema_jotta;
          const isSaved = Boolean(savedFlashcards[fc.id]);
          const isFav = Boolean(favoriteFlashcards[fc.id]);
          const rating = cardDifficultyRatings[fc.id];
          const isRevealed = studyMode === 'visual' || Boolean(revealedQuizCards[fc.id]);
          const guess = interactiveGuesses[fc.id];

          const cols = schema?.colunas ?? [
            {
              termo: fc.tag.toUpperCase(),
              destaque_letra: 'CHAVE',
              gatilho: (fc.mnemonico || 'CONCEITO CENTRAL').slice(0, 38).toUpperCase(),
              explicacao: fc.verso,
              cor: 'amber',
            },
          ];

          return (
            <div
              key={fc.id}
              className="flex flex-col justify-between overflow-hidden rounded-2xl border-2 border-line-strong bg-surface shadow-lg transition-all hover:border-amber-400/50"
            >
              {/* TOPO DA FICHA ESTILO JOTTA */}
              <div>
                <div className="flex items-center justify-between border-b-2 border-line bg-surface-2 px-5 py-3">
                  <div className="flex items-center gap-2">
                    <span className="rounded-md border border-amber-400/50 bg-amber-400/15 px-2.5 py-1 text-[11px] font-black uppercase tracking-widest text-amber-300">
                      {schema?.selo || `DICA VISUAL · #${String(idx + 1).padStart(2, '0')}`}
                    </span>
                    <span className="rounded-md bg-surface-3 px-2 py-0.5 text-[11px] font-bold text-fg-2">
                      {fc.tag}
                    </span>
                  </div>

                  <div className="flex items-center gap-2">
                    {showLessonBadge && fc.aula_id && onSelectLesson && (
                      <button
                        type="button"
                        onClick={() => onSelectLesson(fc.aula_id!)}
                        className="rounded-md border border-line-strong bg-surface px-2 py-1 text-[10px] font-bold text-sky-300 hover:border-sky-400"
                      >
                        Abrir Aula
                      </button>
                    )}
                    <button
                      type="button"
                      onClick={() => onToggleFavorite(fc.id)}
                      title="Favoritar ficha"
                      className={`rounded-lg p-1.5 transition-colors ${
                        isFav
                          ? 'bg-amber-400/20 text-amber-400'
                          : 'text-fg-3 hover:bg-surface-3 hover:text-fg'
                      }`}
                    >
                      <Star size={15} className={isFav ? 'fill-amber-400' : ''} />
                    </button>
                  </div>
                </div>

                {/* QUADRO DE TÍTULO / PERGUNTA EM DESTAQUE */}
                <div className="border-b border-line bg-surface-2/40 px-5 py-4">
                  <h4 className="font-display text-base sm:text-lg font-extrabold tracking-tight text-fg leading-snug">
                    {schema?.titulo || fc.frente}
                  </h4>
                  <p className="mt-1 text-xs font-medium text-fg-2">
                    {isRevealed ? schema?.subtitulo || fc.frente : fc.frente}
                  </p>

                  {/* Interação rápida se for V/F ou Lacuna */}
                  {fc.tipo === 'verdadeiro_falso' && !isRevealed && (
                    <div className="mt-3 flex items-center gap-2">
                      {(['V', 'F'] as const).map((opt) => (
                        <button
                          key={opt}
                          type="button"
                          onClick={() => {
                            setInteractiveGuesses((prev) => ({ ...prev, [fc.id]: opt }));
                            setRevealedQuizCards((prev) => ({ ...prev, [fc.id]: true }));
                          }}
                          className="rounded-lg border border-amber-400/40 bg-amber-400/10 px-4 py-1.5 text-xs font-extrabold text-amber-300 hover:bg-amber-400 hover:text-slate-950 transition-all"
                        >
                          {opt === 'V' ? 'Julgar: CERTO (V)' : 'Julgar: ERRADO (F)'}
                        </button>
                      ))}
                    </div>
                  )}
                </div>

                {/* CORPO ESQUEMATIZADO ESTILO JOTTA */}
                {!isRevealed ? (
                  <div className="flex flex-col items-center justify-center p-8 text-center min-h-[230px] bg-surface">
                    <p className="text-sm font-bold text-fg-2 max-w-md">
                      Tente lembrar a regra e os gatilhos visuais antes de revelar a ficha!
                    </p>
                    <button
                      type="button"
                      onClick={() => toggleReveal(fc.id)}
                      className="mt-4 inline-flex items-center gap-2 rounded-xl bg-amber-400 px-5 py-2.5 text-xs font-extrabold uppercase tracking-wider text-slate-950 shadow-md hover:bg-amber-300 transition-all"
                    >
                      <RotateCcw size={14} /> Revelar Esquema Visual
                    </button>
                  </div>
                ) : (
                  <div className="p-5 space-y-4">
                    {guess && fc.resposta_vf && (
                      <div
                        className={`rounded-xl border px-3.5 py-2 text-xs font-bold ${
                          guess === fc.resposta_vf
                            ? 'border-emerald-500/40 bg-emerald-500/15 text-emerald-300'
                            : 'border-rose-500/40 bg-rose-500/15 text-rose-300'
                        }`}
                      >
                        {guess === fc.resposta_vf
                          ? '✓ Você acertou o julgamento!'
                          : `✗ Atenção: O gabarito correto é ${fc.resposta_vf}.`}
                      </div>
                    )}

                    {/* BLOCOS DE CONTRASTE VISUAL COM CONECTOR T-BAR (ESTILO JOTTA) */}
                    <div
                      className={`grid gap-3.5 ${
                        cols.length === 3
                          ? ' sm:grid-cols-3'
                          : cols.length === 2
                          ? 'sm:grid-cols-2'
                          : 'grid-cols-1'
                      }`}
                    >
                      {cols.map((col, cIdx) => {
                        const style = COLOR_STYLES[col.cor] || COLOR_STYLES.amber;
                        return (
                          <div
                            key={`${fc.id}-col-${cIdx}`}
                            className="flex flex-col items-center text-center rounded-xl border border-line-strong bg-surface-2/70 p-3.5"
                          >
                            {/* PALAVRA-CHAVE EM CAIXA ALTA DESTACADA */}
                            <div
                              className={`w-full rounded-xl border-2 px-3 py-2.5 ${style.termBox}`}
                            >
                              <span
                                className={`block font-display text-base sm:text-lg font-black tracking-wide uppercase ${style.termText}`}
                              >
                                {col.termo}
                              </span>
                              <span
                                className={`mt-1 inline-block rounded px-2 py-0.5 text-[10px] font-black uppercase tracking-wider ${style.letterBadge}`}
                              >
                                {col.destaque_letra}
                              </span>
                            </div>

                            {/* HASTE CONECTORA VERTICAL (T-BAR DO JOTTA) */}
                            <div className="flex flex-col items-center my-1" aria-hidden="true">
                              <div className={`h-2.5 w-0.5 ${style.stemLine}`} />
                              <div className={`h-1.5 w-1.5 rotate-45 ${style.stemLine}`} />
                            </div>

                            {/* PÍLULA BORDEADA DE GATILHO DE MEMÓRIA */}
                            <div
                              className={`w-full rounded-lg border-2 px-2.5 py-1.5 text-[11px] font-black uppercase tracking-wide ${style.pillBorder} ${style.pillText}`}
                            >
                              {col.gatilho}
                            </div>

                            {/* EXPLICAÇÃO / EXEMPLO DE APLICAÇÃO */}
                            <p className="mt-2.5 text-xs font-medium text-fg leading-relaxed">
                              {col.explicacao}
                            </p>
                          </div>
                        );
                      })}
                    </div>

                    {/* FAIXA DE CONCLUSÃO / REGRA DE OURO NO RODAPÉ DO ESQUEMA */}
                    <div className="rounded-xl border-2 border-amber-400/40 bg-amber-400/10 px-4 py-3 text-center">
                      <p className="text-xs font-extrabold uppercase tracking-wide text-amber-200 leading-relaxed">
                        ⚡ {schema?.regra_rodape || fc.mnemonico || fc.verso}
                      </p>
                    </div>
                  </div>
                )}
              </div>

              {/* RODAPÉ DE AÇÃO E REPETIÇÃO ESPAÇADA (SM-2) */}
              <div className="flex flex-wrap items-center justify-between gap-2 border-t border-line bg-surface-2 px-5 py-3">
                <div className="flex items-center gap-1.5">
                  <span className="text-[11px] font-bold text-fg-3 mr-1">Domínio:</span>
                  {(
                    [
                      { key: 'Fácil', tone: 'hover:border-emerald-400 hover:text-emerald-300' },
                      { key: 'Médio', tone: 'hover:border-amber-400 hover:text-amber-300' },
                      { key: 'Difícil', tone: 'hover:border-rose-400 hover:text-rose-300' },
                    ] as const
                  ).map((lvl) => (
                    <button
                      key={lvl.key}
                      type="button"
                      onClick={() => onSaveCard(fc, lvl.key)}
                      className={`rounded-lg border px-2.5 py-1 text-[11px] font-bold transition-all ${
                        rating === lvl.key
                          ? 'border-amber-400 bg-amber-400 text-slate-950'
                          : `border-line-strong bg-surface text-fg-2 ${lvl.tone}`
                      }`}
                    >
                      {lvl.key}
                    </button>
                  ))}
                </div>

                <div className="flex items-center gap-2">
                  {studyMode === 'quiz' && isRevealed && (
                    <button
                      type="button"
                      onClick={() => toggleReveal(fc.id)}
                      className="text-xs font-semibold text-fg-3 hover:text-fg"
                    >
                      Ocultar
                    </button>
                  )}
                  <button
                    type="button"
                    disabled={isSaved}
                    onClick={() => onSaveCard(fc)}
                    className={`inline-flex items-center gap-1.5 rounded-lg px-3 py-1.5 text-xs font-bold transition-all ${
                      isSaved
                        ? 'border border-emerald-500/40 bg-emerald-500/15 text-emerald-300'
                        : 'border border-amber-400/50 bg-amber-400/15 text-amber-300 hover:bg-amber-400 hover:text-slate-950'
                    }`}
                  >
                    {isSaved ? (
                      <>
                        <Check size={13} /> Na Revisão SM-2
                      </>
                    ) : (
                      <>
                        <Zap size={13} /> + Revisão SM-2
                      </>
                    )}
                  </button>
                </div>
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}
