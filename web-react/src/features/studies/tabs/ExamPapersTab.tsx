import { useState } from 'react';
import { useQueryClient } from '@tanstack/react-query';
import { useNavigate, useSearchParams } from 'react-router-dom';
import {
  Building2,
  ExternalLink,
  FileText,
  Play,
  Plus,
  Search,
  Sparkles,
} from 'lucide-react';
import { keys, useExamPapers, useImportExamPaper, type Exam } from '@/app/queries';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { ModalDialog } from '@/components/ui/dialog';
import { EmptyState, SkeletonRows } from '@/components/ui/states';
import { api } from '@/lib/api';
import { readWorkspaceMode } from '@/lib/auth';
import { cn } from '@/lib/cn';
import type { ExamPaperItem } from '@/lib/types';

const CAREERS = [
  { id: '', label: 'Todas as Áreas', core: false },
  { id: 'ti', label: 'TI & Sistemas de Informação', core: true },
  { id: 'administrativa', label: 'Administrativa', core: false },
  { id: 'fiscal', label: 'Fiscal & Controle', core: false },
  { id: 'tribunais', label: 'Tribunais', core: false },
  { id: 'policial', label: 'Policial', core: false },
  { id: 'educacao', label: 'Educação & IFs', core: false },
] as const;

export function ExamPapersTab() {
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const [searchParams, setSearchParams] = useSearchParams();
  const bancaParam = searchParams.get('banca') ?? '';
  const [carreira, setCarreira] = useState<string>('');
  const [searchDraft, setSearchDraft] = useState<string>(searchParams.get('q') ?? '');
  const [appliedQuery, setAppliedQuery] = useState<string>(searchParams.get('q') ?? '');
  const [startingId, setStartingId] = useState<string | null>(null);
  const [actionError, setActionError] = useState<string | null>(null);
  const [importOpen, setImportOpen] = useState(false);

  const isAdmin = readWorkspaceMode() === 'admin';
  const papersQuery = useExamPapers({
    carreira: carreira || undefined,
    banca: bancaParam || undefined,
    q: appliedQuery || undefined,
  });

  const handleStartExam = async (paper: ExamPaperItem) => {
    if (!paper.simulado_tag || startingId) return;
    setStartingId(paper.id);
    setActionError(null);
    try {
      const created = await api.post<Exam>('/api/estudos/simulados', {
        nome: `${paper.banca_nome} ${paper.ano} — ${paper.orgao}`,
        limit: Math.max(1, Math.min(20, paper.questoes_count || 10)),
        exclude_answered: false,
        tags: [paper.simulado_tag],
      });
      await queryClient.invalidateQueries({ queryKey: keys.exams() });
      navigate(`/estudos/simulados?simulado=${encodeURIComponent(created.id)}`);
    } catch (err) {
      setActionError(err instanceof Error ? err.message : 'Não foi possível iniciar o simulado desta prova.');
    } finally {
      setStartingId(null);
    }
  };

  const items = papersQuery.data?.itens ?? [];
  const countsByCareer = papersQuery.data?.por_carreira ?? {};

  return (
    <div className="space-y-4">
      {/* Cabeçalho estilo PCI Provas + Atalhos */}
      <div className="rounded-2xl border border-line bg-surface p-5 shadow-xs space-y-4">
        <div className="flex flex-col md:flex-row md:items-center justify-between gap-3">
          <div>
            <div className="inline-flex items-center gap-1.5 rounded-full border border-emerald-500/30 bg-emerald-500/10 px-2.5 py-0.5 text-2xs font-bold uppercase tracking-wider text-ok-ink">
              <Sparkles size={11} /> Núcleo Profundo em TI + Acervo Multi-Carreira
            </div>
            <h2 className="mt-1.5 font-display text-xl font-bold text-fg">
              Provas Anteriores & Cadernos Oficiais
            </h2>
            <p className="mt-0.5 text-xs text-fg-3">
              Consulte provas oficiais por cargo, ano, órgão e organizadora ou gere um simulado imediato das questões catalogadas.
            </p>
          </div>

          <div className="flex flex-wrap items-center gap-2 shrink-0">
            <Button
              variant="ghost"
              size="sm"
              onClick={() => navigate('/estudos/bancas?modo=diretorio')}
            >
              <Building2 size={13} /> Organizadoras (348)
            </Button>
            {isAdmin && (
              <Button variant="primary" size="sm" onClick={() => setImportOpen(true)}>
                <Plus size={13} /> Importar Prova Oficial
              </Button>
            )}
          </div>
        </div>

        {/* Barra de Pesquisa centralizada estilo PCI */}
        <form
          className="flex flex-col sm:flex-row gap-2"
          onSubmit={(e) => {
            e.preventDefault();
            setAppliedQuery(searchDraft.trim());
          }}
        >
          <div className="relative flex-1">
            <Search size={14} className="absolute left-3 top-1/2 -translate-y-1/2 text-fg-3" />
            <input
              type="search"
              aria-label="Pesquisar provas por cargo, órgão ou banca"
              value={searchDraft}
              onChange={(e) => setSearchDraft(e.target.value)}
              placeholder="Ex: Analista de Sistemas, FGV, TCE/SP, Dataprev, UNIVASF..."
              className="h-9 w-full rounded-lg border border-line-strong bg-surface-2 pl-9 pr-3 text-xs text-fg placeholder:text-fg-3 focus:border-accent focus:outline-none"
            />
          </div>
          <Button type="submit" variant="primary" size="sm">
            <Search size={13} /> Pesquisar
          </Button>
          {(appliedQuery || bancaParam || carreira) && (
            <Button
              type="button"
              variant="ghost"
              size="sm"
              onClick={() => {
                setSearchDraft('');
                setAppliedQuery('');
                setCarreira('');
                const next = new URLSearchParams(searchParams);
                next.delete('banca');
                next.delete('q');
                setSearchParams(next, { replace: true });
              }}
            >
              Limpar
            </Button>
          )}
        </form>

        {/* Pílulas de Carreira */}
        <div className="flex flex-wrap items-center gap-1.5 border-t border-line/60 pt-3">
          {CAREERS.map((item) => {
            const count = item.id ? (countsByCareer[item.id] ?? 0) : (papersQuery.data?.total ?? 0);
            const active = carreira === item.id;
            return (
              <button
                key={item.id || 'all'}
                type="button"
                onClick={() => setCarreira(item.id)}
                className={cn(
                  'inline-flex items-center gap-1.5 rounded-lg px-2.5 py-1 text-2xs font-semibold border transition-colors',
                  active
                    ? item.core
                      ? 'border-emerald-500/50 bg-emerald-500/15 text-ok-ink font-bold'
                      : 'border-accent/50 bg-accent/15 text-accent-ink font-bold'
                    : 'border-line/70 bg-surface-2/50 text-fg-2 hover:text-fg',
                )}
              >
                {item.core && <Sparkles size={11} className="text-ok-ink" />}
                <span>{item.label}</span>
                <span className="rounded bg-surface px-1.5 py-0.2 font-mono text-[10px] text-fg-3">
                  {count}
                </span>
              </button>
            );
          })}
        </div>
      </div>

      {actionError && (
        <div role="alert" className="rounded-lg border border-rose-500/30 bg-rose-500/10 p-3 text-xs text-risk-ink">
          {actionError}
        </div>
      )}

      {/* Tabela Limpa Estilo PCI Concursos */}
      <div className="overflow-hidden rounded-2xl border border-line bg-surface shadow-xs">
        {papersQuery.isLoading ? (
          <div className="p-4">
            <SkeletonRows rows={6} />
          </div>
        ) : items.length === 0 ? (
          <div className="p-6">
            <EmptyState
              title="Nenhuma prova encontrada com esses filtros"
              description="Limpe a busca ou alterne a carreira para visualizar todo o acervo oficial."
            />
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-left border-collapse">
              <thead>
                <tr className="border-b border-line bg-surface-2/70 text-[11px] font-bold uppercase tracking-wider text-fg-3">
                  <th className="py-2.5 px-4">Prova / Cargo</th>
                  <th className="py-2.5 px-3 w-20">Ano</th>
                  <th className="py-2.5 px-3">Órgão</th>
                  <th className="py-2.5 px-3">Organizadora</th>
                  <th className="py-2.5 px-4 text-right">Caderno & Simulação</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-line/70 text-xs">
                {items.map((paper) => (
                  <tr key={paper.id} className="hover:bg-surface-2/40 transition-colors">
                    <td className="py-3 px-4">
                      <div className="flex items-start gap-2.5">
                        <FileText size={15} className="mt-0.5 shrink-0 text-accent-ink" />
                        <div>
                          <p className="font-semibold text-fg leading-snug">{paper.titulo}</p>
                          <div className="mt-1 flex flex-wrap items-center gap-1.5">
                            <Badge tone={paper.carreira === 'ti' ? 'ok' : 'neutral'}>
                              {paper.carreira_label}
                            </Badge>
                            {paper.questoes_count > 0 ? (
                              <span className="text-[11px] font-medium text-ok-ink">
                                {paper.questoes_count} questões prontas
                              </span>
                            ) : (
                              <span className="text-[11px] text-fg-3">
                                Catálogo em expansão
                              </span>
                            )}
                          </div>
                        </div>
                      </div>
                    </td>
                    <td className="py-3 px-3 font-mono font-semibold text-fg-2">{paper.ano}</td>
                    <td className="py-3 px-3 text-fg-2">{paper.orgao}</td>
                    <td className="py-3 px-3">
                      <button
                        type="button"
                        onClick={() => {
                          const next = new URLSearchParams(searchParams);
                          next.set('banca', paper.banca_slug);
                          setSearchParams(next, { replace: true });
                        }}
                        className="font-semibold text-accent-ink hover:underline"
                      >
                        {paper.banca_nome}
                      </button>
                    </td>
                    <td className="py-3 px-4">
                      <div className="flex items-center justify-end gap-2">
                        {paper.edital_ou_prova_url && (
                          <a
                            href={paper.edital_ou_prova_url}
                            target="_blank"
                            rel="noreferrer"
                            className="inline-flex items-center gap-1 rounded-md border border-line bg-surface-2 px-2.5 py-1 text-[11px] font-medium text-fg-2 hover:text-fg"
                          >
                            Fonte Oficial <ExternalLink size={11} />
                          </a>
                        )}
                        {paper.questoes_count > 0 && paper.simulado_tag && (
                          <Button
                            size="sm"
                            variant="primary"
                            disabled={startingId === paper.id}
                            onClick={() => handleStartExam(paper)}
                          >
                            <Play size={12} />
                            {startingId === paper.id ? 'Abrindo...' : 'Simular Prova'}
                          </Button>
                        )}
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>

      <ImportExamPaperModal open={importOpen} onOpenChange={setImportOpen} />
    </div>
  );
}

function ImportExamPaperModal({
  open,
  onOpenChange,
}: {
  open: boolean;
  onOpenChange: (open: boolean) => void;
}) {
  const importMutation = useImportExamPaper();
  const [titulo, setTitulo] = useState('');
  const [orgao, setOrgao] = useState('');
  const [banca, setBanca] = useState('FGV');
  const [ano, setAno] = useState('2025');
  const [carreira, setCarreira] = useState('ti');
  const [url, setUrl] = useState('');
  const [textoProva, setTextoProva] = useState('');
  const [textoGabarito, setTextoGabarito] = useState('');

  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    await importMutation.mutateAsync({
      titulo,
      cargo: titulo,
      orgao,
      banca,
      ano: Number(ano) || 2025,
      carreira,
      edital_ou_prova_url: url || undefined,
      texto_prova: textoProva || undefined,
      texto_gabarito: textoGabarito || undefined,
    });
    setTitulo('');
    setOrgao('');
    setTextoProva('');
    setTextoGabarito('');
    onOpenChange(false);
  };

  return (
    <ModalDialog
      open={open}
      onOpenChange={onOpenChange}
      title="Importar Prova Oficial & Extrair Questões"
      description="Cadastre o link oficial e cole o texto da prova + gabarito para extração automática."
    >
      <form onSubmit={submit} className="space-y-3 text-xs">
        <label className="block space-y-1">
          <span className="font-semibold text-fg-2">Cargo / Título da Prova</span>
          <input
            required
            value={titulo}
            onChange={(e) => setTitulo(e.target.value)}
            className="w-full rounded border border-line-strong bg-surface-2 px-2.5 py-1.5 text-fg"
          />
        </label>
        <div className="grid grid-cols-3 gap-2">
          <label className="block space-y-1">
            <span className="font-semibold text-fg-2">Órgão</span>
            <input
              required
              value={orgao}
              onChange={(e) => setOrgao(e.target.value)}
              className="w-full rounded border border-line-strong bg-surface-2 px-2.5 py-1.5 text-fg"
            />
          </label>
          <label className="block space-y-1">
            <span className="font-semibold text-fg-2">Banca</span>
            <input
              required
              value={banca}
              onChange={(e) => setBanca(e.target.value)}
              className="w-full rounded border border-line-strong bg-surface-2 px-2.5 py-1.5 text-fg"
            />
          </label>
          <label className="block space-y-1">
            <span className="font-semibold text-fg-2">Ano</span>
            <input
              type="number"
              value={ano}
              onChange={(e) => setAno(e.target.value)}
              className="w-full rounded border border-line-strong bg-surface-2 px-2.5 py-1.5 text-fg"
            />
          </label>
        </div>
        <div className="grid grid-cols-2 gap-2">
          <label className="block space-y-1">
            <span className="font-semibold text-fg-2">Carreira</span>
            <select
              value={carreira}
              onChange={(e) => setCarreira(e.target.value)}
              className="w-full rounded border border-line-strong bg-surface-2 px-2.5 py-1.5 text-fg"
            >
              {CAREERS.filter((c) => c.id).map((c) => (
                <option key={c.id} value={c.id}>
                  {c.label}
                </option>
              ))}
            </select>
          </label>
          <label className="block space-y-1">
            <span className="font-semibold text-fg-2">URL Oficial (opcional)</span>
            <input
              value={url}
              onChange={(e) => setUrl(e.target.value)}
              placeholder="https://..."
              className="w-full rounded border border-line-strong bg-surface-2 px-2.5 py-1.5 text-fg"
            />
          </label>
        </div>
        <label className="block space-y-1">
          <span className="font-semibold text-fg-2">Texto das Questões Numeradas (opcional)</span>
          <textarea
            rows={4}
            value={textoProva}
            onChange={(e) => setTextoProva(e.target.value)}
            placeholder="1. Enunciado...&#10;A) ...&#10;B) ..."
            className="w-full rounded border border-line-strong bg-surface-2 p-2 text-fg"
          />
        </label>
        <label className="block space-y-1">
          <span className="font-semibold text-fg-2">Gabarito Oficial (ex: 1-C 2-D)</span>
          <input
            value={textoGabarito}
            onChange={(e) => setTextoGabarito(e.target.value)}
            className="w-full rounded border border-line-strong bg-surface-2 px-2.5 py-1.5 text-fg"
          />
        </label>
        {importMutation.isError && (
          <p role="alert" className="text-risk-ink">
            {(importMutation.error as Error).message}
          </p>
        )}
        <div className="flex justify-end gap-2 pt-2">
          <Button type="button" variant="ghost" size="sm" onClick={() => onOpenChange(false)}>
            Cancelar
          </Button>
          <Button type="submit" variant="primary" size="sm" disabled={importMutation.isPending}>
            {importMutation.isPending ? 'Importando...' : 'Salvar & Extrair'}
          </Button>
        </div>
      </form>
    </ModalDialog>
  );
}
