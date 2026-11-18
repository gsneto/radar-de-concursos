import { useState } from 'react';
import { ArrowLeft, ArrowRight, ExternalLink, Sparkles, Video } from 'lucide-react';
import { Button } from '@/components/ui/button';
import type { LessonDetail } from '@/lib/types';

export interface SyncedVideoNote {
  id: string;
  chapterTitle: string;
  timestampLabel: string;
  timestampSec: number;
  text: string;
  createdAt: string;
}

interface LessonVideoStageProps {
  lesson: LessonDetail;
  notes: SyncedVideoNote[];
  onMarkChapterCompleted: (chapterId: string) => void;
  onAddNote: (note: SyncedVideoNote) => void;
  onNextStage: () => void;
}

export function LessonVideoStage({
  lesson,
  notes,
  onMarkChapterCompleted,
  onAddNote,
  onNextStage,
}: LessonVideoStageProps) {
  const [selectedVideoIndex, setSelectedVideoIndex] = useState(0);
  const [videoPresentationMode, setVideoPresentationMode] = useState<'video' | 'slides'>('video');
  const [activeSlideIdx, setActiveSlideIdx] = useState(0);
  const [videoStartSec, setVideoStartSec] = useState(0);
  const [activeChapterId, setActiveChapterId] = useState('');
  const [checkpointAnswers, setCheckpointAnswers] = useState<Record<string, number>>({});
  const [noteInput, setNoteInput] = useState('');

  const videos = lesson.videoaulas ?? [];
  const currentVideo = videos[selectedVideoIndex] ?? videos[0];
  const chapters = currentVideo?.capitulos ?? [];
  const slides = currentVideo?.slides_guiados ?? [];
  const currentSlide = slides[activeSlideIdx] ?? slides[0];
  const checkpoints = currentVideo?.perguntas_video ?? [];

  const handleJumpToChapter = (chapterId: string, startSec: number) => {
    setActiveChapterId(chapterId);
    setVideoStartSec(startSec);
    setVideoPresentationMode('video');
    onMarkChapterCompleted(chapterId);
  };

  const handleSaveNote = () => {
    if (!noteInput.trim()) return;
    onAddNote({
      id: `note-${Date.now()}`,
      chapterTitle: 'Nota da Aula',
      timestampLabel: '00:00',
      timestampSec: videoStartSec,
      text: noteInput.trim(),
      createdAt: new Date().toLocaleTimeString('pt-BR', { hour: '2-digit', minute: '2-digit' }),
    });
    setNoteInput('');
  };

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-center justify-between gap-3 rounded-2xl border-l-4 border-l-amber-400 border border-line-strong bg-surface p-5">
        <div>
          <span className="text-xs font-black uppercase tracking-widest text-accent-ink">
            ETAPA 3 DE 5 · VIDEOAULAS VERIFICADAS & SLIDES GUIADOS
          </span>
          <h2 className="mt-1 font-display text-xl font-extrabold text-fg">
            Assista à aula em vídeo ou navegue pelos slides esquematizados
          </h2>
        </div>
        <Button variant="primary" size="sm" onClick={onNextStage} className="gap-1.5 font-extrabold">
          <span>Ir para Etapa 4: Flashcards Visuais</span>
          <ArrowRight size={14} />
        </Button>
      </div>

      {currentVideo && (
        <div className="grid gap-6 lg:grid-cols-[1.5fr_1fr]">
          <div className="space-y-4">
            <div className="overflow-hidden rounded-2xl border-2 border-line-strong bg-surface shadow-lg">
              <div className="flex flex-wrap items-center justify-between gap-2 border-b border-line bg-surface-2 px-4 py-3">
                <div className="flex items-center gap-2">
                  <button
                    type="button"
                    onClick={() => setVideoPresentationMode('video')}
                    className={`flex items-center gap-1.5 rounded-lg px-3.5 py-1.5 text-xs font-extrabold transition-all ${
                      videoPresentationMode === 'video'
                        ? 'bg-amber-400 text-slate-950'
                        : 'text-fg-2 hover:text-fg'
                    }`}
                  >
                    <Video size={14} /> Player de Vídeo (YouTube)
                  </button>
                  <button
                    type="button"
                    onClick={() => setVideoPresentationMode('slides')}
                    className={`flex items-center gap-1.5 rounded-lg px-3.5 py-1.5 text-xs font-extrabold transition-all ${
                      videoPresentationMode === 'slides'
                        ? 'bg-amber-400 text-slate-950'
                        : 'text-fg-2 hover:text-fg'
                    }`}
                  >
                    <Sparkles size={14} /> Slides da Aula ({slides.length})
                  </button>
                </div>

                <a
                  href={`https://www.youtube.com/watch?v=${currentVideo.youtube_id}`}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="inline-flex items-center gap-1.5 rounded-lg border border-line-strong bg-surface px-3 py-1.5 text-xs font-bold text-accent-ink hover:border-amber-400"
                >
                  <span>Abrir no YouTube</span>
                  <ExternalLink size={12} />
                </a>
              </div>

              {videoPresentationMode === 'video' ? (
                <div className="relative aspect-video w-full bg-black">
                  <iframe
                    key={`${currentVideo.youtube_id}-${videoStartSec}`}
                    className="w-full h-full"
                    src={`https://www.youtube.com/embed/${currentVideo.youtube_id}?rel=0&modestbranding=1${
                      videoStartSec > 0 ? `&start=${videoStartSec}&autoplay=1` : ''
                    }`}
                    title={currentVideo.titulo}
                    allow="accelerometer; autoplay; clipboard-write; encrypted-media; gyroscope; picture-in-picture"
                    allowFullScreen
                  />
                </div>
              ) : (
                <div className="aspect-video w-full bg-surface p-8 flex flex-col justify-between">
                  <div className="flex items-center justify-between">
                    <span className="rounded-md bg-amber-400 px-3 py-1 text-xs font-black uppercase text-slate-950">
                      {currentSlide?.tag || 'SLIDE DIDÁTICO'}
                    </span>
                    <span className="text-xs font-bold text-fg-2">
                      Slide {activeSlideIdx + 1} de {slides.length}
                    </span>
                  </div>

                  <div className="my-auto space-y-4">
                    <h3 className="font-display text-2xl font-extrabold text-fg">{currentSlide?.titulo}</h3>
                    <p className="text-base text-fg-2 leading-relaxed">{currentSlide?.conteudo}</p>
                    {currentSlide?.destaque && (
                      <div className="rounded-xl border border-amber-400/40 bg-amber-400/10 p-4 text-sm font-bold text-accent-ink">
                        💡 {currentSlide.destaque}
                      </div>
                    )}
                  </div>

                  <div className="flex items-center justify-between pt-4 border-t border-line">
                    <Button
                      variant="secondary"
                      size="sm"
                      disabled={activeSlideIdx === 0}
                      onClick={() => setActiveSlideIdx((i) => Math.max(0, i - 1))}
                    >
                      <ArrowLeft size={14} /> Anterior
                    </Button>
                    <Button
                      variant="primary"
                      size="sm"
                      disabled={activeSlideIdx >= slides.length - 1}
                      onClick={() => setActiveSlideIdx((i) => Math.min(slides.length - 1, i + 1))}
                    >
                      Próximo Slide <ArrowRight size={14} />
                    </Button>
                  </div>
                </div>
              )}

              <div className="p-4 bg-surface-2 border-t border-line">
                <h4 className="font-display text-base font-extrabold text-fg">{currentVideo.titulo}</h4>
                <p className="text-xs text-fg-2 mt-0.5">
                  Canal: <strong>{currentVideo.canal}</strong> · Duração: {currentVideo.duracao}
                </p>
              </div>
            </div>

            {checkpoints.map((cp) => {
              const ans = checkpointAnswers[cp.id];
              const answered = ans !== undefined;
              return (
                <div key={cp.id} className="rounded-2xl border border-line-strong bg-surface p-5 space-y-3">
                  <span className="text-xs font-black uppercase tracking-wider text-accent-ink">
                    PERGUNTA DE FIXAÇÃO DO VÍDEO ({cp.momento_label})
                  </span>
                  <p className="text-sm font-bold text-fg">{cp.pergunta}</p>
                  <div className="grid gap-2 sm:grid-cols-2">
                    {cp.alternativas.map((alt, aIdx) => {
                      const isCorr = aIdx === cp.correta_idx;
                      const isSel = ans === aIdx;
                      return (
                        <button
                          key={aIdx}
                          type="button"
                          disabled={answered}
                          onClick={() => setCheckpointAnswers((prev) => ({ ...prev, [cp.id]: aIdx }))}
                          className={`text-left rounded-xl border p-3 text-xs font-medium transition-all ${
                            !answered
                              ? 'border-line-strong bg-surface-2 hover:border-amber-400 text-fg'
                              : isCorr
                                ? 'border-emerald-500/50 bg-emerald-500/15 text-ok-ink font-bold'
                                : isSel
                                  ? 'border-rose-500/50 bg-rose-500/15 text-risk-ink'
                                  : 'border-line bg-surface-2/40 text-fg-3'
                          }`}
                        >
                          {alt}
                        </button>
                      );
                    })}
                  </div>
                </div>
              );
            })}
          </div>

          <div className="space-y-4">
            <div className="rounded-2xl border border-line-strong bg-surface p-5 space-y-3">
              <h4 className="font-display text-base font-extrabold text-fg">Vídeos & Capítulos desta Aula</h4>
              <div className="space-y-2.5">
                {videos.map((vid, idx) => {
                  const isSel = idx === selectedVideoIndex;
                  return (
                    <div key={idx} className="space-y-2">
                      <button
                        type="button"
                        onClick={() => {
                          setSelectedVideoIndex(idx);
                          setVideoStartSec(0);
                          setActiveSlideIdx(0);
                        }}
                        className={`w-full text-left rounded-xl border p-3.5 transition-all ${
                          isSel
                            ? 'border-amber-400 bg-amber-400/15'
                            : 'border-line-strong bg-surface-2 hover:border-amber-400/40'
                        }`}
                      >
                        <div className="flex items-center gap-2.5">
                          <span
                            className={`flex size-7 shrink-0 items-center justify-center rounded-lg text-xs font-black ${
                              isSel ? 'bg-amber-400 text-slate-950' : 'bg-surface text-fg-2'
                            }`}
                          >
                            {idx + 1}
                          </span>
                          <div className="min-w-0">
                            <p className="text-xs font-extrabold text-fg truncate">{vid.titulo}</p>
                            <p className="text-[11px] text-fg-2">
                              {vid.canal} · {vid.duracao}
                            </p>
                          </div>
                        </div>
                      </button>

                      {isSel && chapters.length > 0 && (
                        <div className="pl-3 border-l-2 border-amber-400/40 space-y-1.5">
                          {chapters.map((cap) => (
                            <button
                              key={cap.id}
                              type="button"
                              onClick={() => handleJumpToChapter(cap.id, cap.tempo_seg)}
                              className={`w-full text-left rounded-lg border px-3 py-2 text-xs transition-all flex items-center justify-between ${
                                activeChapterId === cap.id
                                  ? 'border-amber-400 bg-amber-400/10 text-fg font-bold'
                                  : 'border-line bg-surface-2/60 text-fg-2 hover:text-fg'
                              }`}
                            >
                              <span className="truncate">{cap.titulo}</span>
                              <span className="font-mono text-[11px] text-accent-ink shrink-0 ml-2">
                                {cap.tempo_label}
                              </span>
                            </button>
                          ))}
                        </div>
                      )}
                    </div>
                  );
                })}
              </div>
            </div>

            <div className="rounded-2xl border border-line-strong bg-surface p-5 space-y-3">
              <h4 className="font-display text-base font-extrabold text-fg">Suas Anotações nesta Aula</h4>
              <div className="flex gap-2">
                <input
                  type="text"
                  value={noteInput}
                  onChange={(e) => setNoteInput(e.target.value)}
                  placeholder="Anotar ponto importante..."
                  className="flex-1 rounded-xl border border-line-strong bg-surface-2 px-3 py-2 text-xs text-fg"
                />
                <Button variant="primary" size="sm" onClick={handleSaveNote}>
                  Salvar
                </Button>
              </div>
              {notes.length > 0 && (
                <div className="space-y-2 pt-1">
                  {notes.map((n) => (
                    <div key={n.id} className="rounded-xl border border-line bg-surface-2 p-3 text-xs text-fg">
                      {n.text}
                    </div>
                  ))}
                </div>
              )}
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
