import { useState } from 'react';
import {
  Check,
  ChevronLeft,
  ChevronRight,
  Download,
  Eye,
  EyeOff,
  Image as ImageIcon,
  Maximize2,
  RotateCcw,
  Sparkles,
  Star,
  X,
  Zap,
} from 'lucide-react';
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
  // 'imagem' (Flashcard em Imagem criada por IA - Padrão) | 'visual' (Esquema HTML) | 'quiz' (Teste de Memória)
  const [studyMode, setStudyMode] = useState<'imagem' | 'visual' | 'quiz'>('imagem');
  const [revealedQuizCards, setRevealedQuizCards] = useState<Record<string, boolean>>({});
  const [interactiveGuesses, setInteractiveGuesses] = useState<Record<string, string>>({});
  const [lightboxIndex, setLightboxIndex] = useState<number | null>(null);

  const toggleReveal = (id: string) => {
    setRevealedQuizCards((prev) => ({ ...prev, [id]: !prev[id] }));
  };

  const getCardImageUrl = (fc: LessonFlashcard) => {
    return fc.imagem_url || `/flashcards/${fc.id}.svg`;
  };

  const activeLightboxCard = lightboxIndex !== null ? cards[lightboxIndex] : null;

  return (
    <div className="space-y-5">
      {/* Barra de Controle Clara e Direta */}
      <div className="flex flex-wrap items-center justify-between gap-3 rounded-2xl border border-line-strong bg-surface-2/90 p-4 shadow-sm">
        <div className="space-y-0.5">
          <div className="flex items-center gap-2">
            <span className="inline-flex items-center gap-1.5 rounded-md bg-amber-400 px-2.5 py-0.5 text-xs font-extrabold uppercase tracking-wider text-slate-950">
              <Sparkles size={13} /> Flashcards em Imagem (IA)
            </span>
            <span className="text-xs font-bold text-fg-2">
              {cards.length} {cards.length === 1 ? 'ficha ilustrada' : 'fichas ilustradas'}
            </span>
          </div>
          <p className="text-xs text-fg-2">
            Fichas ilustradas por IA no estilo <strong>Sketchnote / Flashcards do Jotta</strong>. Clique em qualquer imagem para ampliar em tela cheia ou baixar.
          </p>
        </div>

        {/* Seletor de Modo: Flashcards em Imagem IA vs Esquema Interativo vs Modo Teste */}
        <div className="flex flex-wrap items-center gap-1.5 rounded-xl border border-line-strong bg-surface p-1">
          <button
            type="button"
            onClick={() => setStudyMode('imagem')}
            className={`flex items-center gap-1.5 rounded-lg px-3 py-1.5 text-xs font-bold transition-all ${
              studyMode === 'imagem'
                ? 'bg-amber-400 text-slate-950 shadow-sm'
                : 'text-fg-2 hover:text-fg'
            }`}
          >
            <ImageIcon size={14} /> Flashcards em Imagem (IA)
          </button>
          <button
            type="button"
            onClick={() => setStudyMode('visual')}
            className={`flex items-center gap-1.5 rounded-lg px-3 py-1.5 text-xs font-bold transition-all ${
              studyMode === 'visual'
                ? 'bg-amber-400 text-slate-950 shadow-sm'
                : 'text-fg-2 hover:text-fg'
            }`}
          >
            <Eye size={14} /> Esquema Interativo
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
      <div className="grid gap-6 md:grid-cols-2 xl:grid-cols-3">
        {cards.map((fc, idx) => {
          const schema = fc.esquema_jotta;
          const isSaved = Boolean(savedFlashcards[fc.id]);
          const isFav = Boolean(favoriteFlashcards[fc.id]);
          const rating = cardDifficultyRatings[fc.id];
          const isRevealed = studyMode !== 'quiz' || Boolean(revealedQuizCards[fc.id]);
          const guess = interactiveGuesses[fc.id];
          const imgUrl = getCardImageUrl(fc);

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
              className="flex flex-col justify-between overflow-hidden rounded-2xl border-2 border-line-strong bg-surface shadow-lg transition-all hover:border-amber-400/60"
            >
              {/* TOPO DA FICHA */}
              <div>
                <div className="flex items-center justify-between border-b-2 border-line bg-surface-2 px-4 py-2.5">
                  <div className="flex items-center gap-1.5 min-w-0">
                    <span className="inline-flex items-center gap-1 rounded-md border border-amber-400/50 bg-amber-400/15 px-2 py-0.5 text-[10px] font-black uppercase tracking-wider text-amber-300 shrink-0">
                      <Sparkles size={11} /> IA
                    </span>
                    <span className="truncate rounded-md bg-surface-3 px-2 py-0.5 text-[11px] font-bold text-fg-2">
                      {fc.tag}
                    </span>
                  </div>

                  <div className="flex items-center gap-1.5 shrink-0">
                    {showLessonBadge && fc.aula_id && onSelectLesson && (
                      <button
                        type="button"
                        onClick={() => onSelectLesson(fc.aula_id!)}
                        className="rounded-md border border-line-strong bg-surface px-2 py-1 text-[10px] font-bold text-sky-300 hover:border-sky-400"
                      >
                        Abrir Aula
                      </button>
                    )}
                    <a
                      href={imgUrl}
                      download={`${fc.id}.${imgUrl.endsWith('.jpg') ? 'jpg' : 'svg'}`}
                      title="Baixar imagem do flashcard"
                      className="rounded-lg p-1.5 text-fg-3 hover:bg-surface-3 hover:text-fg transition-colors"
                    >
                      <Download size={14} />
                    </a>
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
                      <Star size={14} className={isFav ? 'fill-amber-400' : ''} />
                    </button>
                  </div>
                </div>

                {/* TÍTULO COMPACTO */}
                <div className="border-b border-line bg-surface-2/40 px-4 py-3">
                  <h4 className="font-display text-sm sm:text-base font-extrabold tracking-tight text-fg leading-snug">
                    {schema?.titulo || fc.frente}
                  </h4>
                  {studyMode === 'quiz' && !isRevealed && (
                    <p className="mt-1 text-xs font-medium text-fg-2">{fc.frente}</p>
                  )}
                </div>

                {/* CORPO DA FICHA: MODO IMAGEM IA vs MODO TESTE vs MODO ESQUEMA */}
                {!isRevealed ? (
                  <div className="flex flex-col items-center justify-center p-8 text-center min-h-[300px] bg-surface">
                    <p className="text-sm font-bold text-fg-2 max-w-xs">
                      Tente responder mentalmente antes de revelar o Flashcard em Imagem!
                    </p>
                    {fc.tipo === 'verdadeiro_falso' && (
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
                            {opt === 'V' ? 'CERTO (V)' : 'ERRADO (F)'}
                          </button>
                        ))}
                      </div>
                    )}
                    <button
                      type="button"
                      onClick={() => toggleReveal(fc.id)}
                      className="mt-4 inline-flex items-center gap-2 rounded-xl bg-amber-400 px-5 py-2.5 text-xs font-extrabold uppercase tracking-wider text-slate-950 shadow-md hover:bg-amber-300 transition-all"
                    >
                      <RotateCcw size={14} /> Revelar Flashcard em Imagem (IA)
                    </button>
                  </div>
                ) : studyMode === 'imagem' || studyMode === 'quiz' ? (
                  <div className="p-3 bg-surface-2/30">
                    {guess && fc.resposta_vf && (
                      <div
                        className={`mb-2.5 rounded-xl border px-3 py-2 text-xs font-bold ${
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

                    {/* PÔSTER DE IMAGEM GERADA POR IA */}
                    <div
                      onClick={() => setLightboxIndex(idx)}
                      role="button"
                      tabIndex={0}
                      onKeyDown={(e) => {
                        if (e.key === 'Enter' || e.key === ' ') setLightboxIndex(idx);
                      }}
                      className="group relative cursor-zoom-in overflow-hidden rounded-xl border-2 border-amber-950/20 bg-[#FAF6EC] shadow-md transition-transform duration-200 hover:scale-[1.01]"
                    >
                      <img
                        src={imgUrl}
                        alt={schema?.titulo || fc.frente}
                        loading="lazy"
                        className="w-full h-auto object-contain block select-none"
                      />
                      <div className="pointer-events-none absolute inset-x-0 bottom-0 flex items-center justify-between bg-gradient-to-t from-slate-950/85 via-slate-950/40 to-transparent px-3.5 py-2.5 opacity-0 transition-opacity duration-200 group-hover:opacity-100">
                        <span className="text-[11px] font-bold text-white flex items-center gap-1.5">
                          <Maximize2 size={13} className="text-amber-400" /> Clique para ampliar em tela cheia
                        </span>
                        <span className="rounded bg-amber-400 px-2 py-0.5 text-[10px] font-black uppercase text-slate-950">
                          Zoom HD
                        </span>
                      </div>
                    </div>
                  </div>
                ) : (
                  /* MODO ESQUEMA HTML INTERATIVO */
                  <div className="p-4 space-y-3.5">
                    <div className="grid gap-3">
                      {cols.map((col, cIdx) => {
                        const style = COLOR_STYLES[col.cor] || COLOR_STYLES.amber;
                        return (
                          <div
                            key={`${fc.id}-col-${cIdx}`}
                            className="flex flex-col items-center text-center rounded-xl border border-line-strong bg-surface-2/70 p-3"
                          >
                            <div className={`w-full rounded-xl border-2 px-3 py-2 ${style.termBox}`}>
                              <span
                                className={`block font-display text-sm sm:text-base font-black tracking-wide uppercase ${style.termText}`}
                              >
                                {col.termo}
                              </span>
                              <span
                                className={`mt-1 inline-block rounded px-2 py-0.5 text-[10px] font-black uppercase tracking-wider ${style.letterBadge}`}
                              >
                                {col.destaque_letra}
                              </span>
                            </div>
                            <div className="flex flex-col items-center my-1" aria-hidden="true">
                              <div className={`h-2 w-0.5 ${style.stemLine}`} />
                              <div className={`h-1.5 w-1.5 rotate-45 ${style.stemLine}`} />
                            </div>
                            <div
                              className={`w-full rounded-lg border-2 px-2.5 py-1 text-[11px] font-black uppercase tracking-wide ${style.pillBorder} ${style.pillText}`}
                            >
                              {col.gatilho}
                            </div>
                            <p className="mt-2 text-xs font-medium text-fg leading-relaxed">
                              {col.explicacao}
                            </p>
                          </div>
                        );
                      })}
                    </div>

                    <div className="rounded-xl border-2 border-amber-400/40 bg-amber-400/10 px-3.5 py-2.5 text-center">
                      <p className="text-xs font-extrabold uppercase tracking-wide text-amber-200 leading-relaxed">
                        ⚡ {schema?.regra_rodape || fc.mnemonico || fc.verso}
                      </p>
                    </div>
                  </div>
                )}
              </div>

              {/* RODAPÉ DE AÇÃO E REPETIÇÃO ESPAÇADA (SM-2) */}
              <div className="flex flex-wrap items-center justify-between gap-2 border-t border-line bg-surface-2 px-4 py-2.5">
                <div className="flex items-center gap-1">
                  <span className="text-[10px] font-bold text-fg-3 mr-0.5">Domínio:</span>
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
                      className={`rounded-lg border px-2 py-1 text-[10px] font-bold transition-all ${
                        rating === lvl.key
                          ? 'border-amber-400 bg-amber-400 text-slate-950'
                          : `border-line-strong bg-surface text-fg-2 ${lvl.tone}`
                      }`}
                    >
                      {lvl.key}
                    </button>
                  ))}
                </div>

                <div className="flex items-center gap-1.5">
                  <button
                    type="button"
                    onClick={() => setLightboxIndex(idx)}
                    title="Ampliar imagem"
                    className="inline-flex items-center gap-1 rounded-lg border border-line-strong bg-surface px-2.5 py-1 text-[11px] font-bold text-fg-2 hover:border-amber-400 hover:text-fg"
                  >
                    <Maximize2 size={12} /> Ampliar
                  </button>
                  <button
                    type="button"
                    disabled={isSaved}
                    onClick={() => onSaveCard(fc)}
                    className={`inline-flex items-center gap-1 rounded-lg px-2.5 py-1 text-[11px] font-bold transition-all ${
                      isSaved
                        ? 'border border-emerald-500/40 bg-emerald-500/15 text-emerald-300'
                        : 'border border-amber-400/50 bg-amber-400/15 text-amber-300 hover:bg-amber-400 hover:text-slate-950'
                    }`}
                  >
                    {isSaved ? (
                      <>
                        <Check size={12} /> Salvo
                      </>
                    ) : (
                      <>
                        <Zap size={12} /> + SM-2
                      </>
                    )}
                  </button>
                </div>
              </div>
            </div>
          );
        })}
      </div>

      {/* LIGHTBOX MODAL EM TELA CHEIA PARA ESTUDO E DOWNLOAD DA IMAGEM IA */}
      {activeLightboxCard && lightboxIndex !== null && (
        <div
          role="dialog"
          aria-modal="true"
          aria-label="Visualização ampliada do Flashcard em Imagem"
          className="fixed inset-0 z-50 flex items-center justify-center bg-slate-950/90 p-4 backdrop-blur-md"
          onClick={() => setLightboxIndex(null)}
        >
          <div
            className="relative flex max-h-[94vh] w-full max-w-3xl flex-col overflow-hidden rounded-2xl border-2 border-line-strong bg-surface shadow-2xl"
            onClick={(e) => e.stopPropagation()}
          >
            {/* Header do Modal */}
            <div className="flex items-center justify-between border-b border-line bg-surface-2 px-5 py-3">
              <div className="min-w-0">
                <span className="text-[10px] font-black uppercase tracking-widest text-amber-400">
                  Flashcard em Imagem IA · {lightboxIndex + 1} de {cards.length}
                </span>
                <h3 className="truncate text-sm sm:text-base font-extrabold text-fg">
                  {activeLightboxCard.esquema_jotta?.titulo || activeLightboxCard.frente}
                </h3>
              </div>

              <div className="flex items-center gap-2 shrink-0">
                <a
                  href={getCardImageUrl(activeLightboxCard)}
                  download={`${activeLightboxCard.id}.${
                    getCardImageUrl(activeLightboxCard).endsWith('.jpg') ? 'jpg' : 'svg'
                  }`}
                  className="inline-flex items-center gap-1.5 rounded-xl bg-amber-400 px-3.5 py-1.5 text-xs font-extrabold text-slate-950 hover:bg-amber-300 transition-colors"
                >
                  <Download size={14} /> Baixar Imagem
                </a>
                <button
                  type="button"
                  onClick={() => setLightboxIndex(null)}
                  className="rounded-xl border border-line-strong bg-surface p-2 text-fg-2 hover:text-fg"
                >
                  <X size={16} />
                </button>
              </div>
            </div>

            {/* Imagem Ampliada */}
            <div className="flex-1 overflow-y-auto bg-slate-950/60 p-4 flex items-center justify-center">
              <img
                src={getCardImageUrl(activeLightboxCard)}
                alt={activeLightboxCard.frente}
                className="max-h-[75vh] w-auto rounded-xl border border-line shadow-xl object-contain bg-[#FAF6EC]"
              />
            </div>

            {/* Navegação Anterior / Próximo no Modal */}
            <div className="flex items-center justify-between border-t border-line bg-surface-2 px-5 py-3">
              <button
                type="button"
                disabled={lightboxIndex <= 0}
                onClick={() => setLightboxIndex((i) => (i !== null && i > 0 ? i - 1 : i))}
                className="inline-flex items-center gap-1.5 rounded-xl border border-line-strong bg-surface px-3.5 py-1.5 text-xs font-bold text-fg hover:border-amber-400 disabled:opacity-30 disabled:pointer-events-none"
              >
                <ChevronLeft size={15} /> Flashcard Anterior
              </button>

              <p className="hidden sm:block text-xs font-semibold text-fg-2 truncate max-w-sm">
                💡 {activeLightboxCard.mnemonico}
              </p>

              <button
                type="button"
                disabled={lightboxIndex >= cards.length - 1}
                onClick={() =>
                  setLightboxIndex((i) => (i !== null && i < cards.length - 1 ? i + 1 : i))
                }
                className="inline-flex items-center gap-1.5 rounded-xl border border-line-strong bg-surface px-3.5 py-1.5 text-xs font-bold text-fg hover:border-amber-400 disabled:opacity-30 disabled:pointer-events-none"
              >
                Próximo Flashcard <ChevronRight size={15} />
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
