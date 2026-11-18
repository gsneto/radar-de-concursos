import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { StudiesPage } from './StudiesPage';

function renderPage(initialEntry = '/estudos') {
  const client = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  return render(
    <QueryClientProvider client={client}>
      <MemoryRouter initialEntries={[initialEntry]}>
        <StudiesPage />
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

beforeEach(() => {
  vi.unstubAllGlobals();
});

describe('StudiesPage', () => {
  it('renderiza indicadores de estudo, abas acessíveis e estados vazios honestos', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn(async (url: string) => {
        if (url.startsWith('/api/estudos/painel')) {
          return new Response(
            JSON.stringify({
              total_segundos: 5400,
              semana_segundos: 1800,
              sessoes_concluidas: 3,
              revisoes_pendentes: 0,
              disciplinas: 1,
              conteudo: {
                topics: { done: 0, total: 0, pct: 0 },
                overall: { done: 0, total: 0, pct: 0 },
              },
              minutos_por_disciplina: [{ disciplina_id: 'd1', nome: 'Banco de Dados', minutos: 90 }],
              revisoes: [],
              sessao_aberta: null,
            }),
            { status: 200, headers: { 'Content-Type': 'application/json' } },
          );
        }
        if (url.startsWith('/api/estudos/sessoes')) {
          return new Response(JSON.stringify([]), {
            status: 200,
            headers: { 'Content-Type': 'application/json' },
          });
        }
        if (url.startsWith('/api/estudos/revisoes')) {
          return new Response(JSON.stringify([]), {
            status: 200,
            headers: { 'Content-Type': 'application/json' },
          });
        }
        if (url.startsWith('/api/estudos/disciplinas')) {
          return new Response(
            JSON.stringify([{ id: 'd1', nome: 'Banco de Dados', peso: 1 }]),
            { status: 200, headers: { 'Content-Type': 'application/json' } },
          );
        }
        if (url.startsWith('/api/estudos/desempenho')) {
          return new Response(
            JSON.stringify({
              geral: { respondidas: 10, corretas: 8, pct: 80, basis: '8 de 10 questões' },
              por_disciplina: [],
              por_topico: [],
            }),
            { status: 200, headers: { 'Content-Type': 'application/json' } },
          );
        }
        if (url.startsWith('/api/estudos/flashcards/estatisticas')) {
          return new Response(
            JSON.stringify({ ativos: 5, vencidos: 1, novos: 2, basis: '5 ativos' }),
            { status: 200, headers: { 'Content-Type': 'application/json' } },
          );
        }
        return new Response('[]', { status: 200, headers: { 'Content-Type': 'application/json' } });
      }),
    );

    renderPage();

    expect(await screen.findByRole('region', { name: 'Indicadores de estudo' })).toBeInTheDocument();
    expect(screen.getByRole('tablist', { name: 'Seções de estudos' })).toBeInTheDocument();
    expect(screen.getAllByText('Banco de Dados').length).toBeGreaterThan(0);
    expect(screen.getByText('Nenhum tópico cadastrado')).toBeInTheDocument();

    // Navegar entre abas
    const questoesTab = screen.getByRole('tab', { name: 'Questões' });
    fireEvent.click(questoesTab);
    expect(questoesTab).toHaveAttribute('aria-selected', 'true');
  });

  it('exibe estado de erro quando o painel de estudos falha', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn(async () =>
        new Response(JSON.stringify({ error: 'Falha ao carregar estudos' }), {
          status: 500,
          headers: { 'Content-Type': 'application/json' },
        }),
      ),
    );

    renderPage();

    expect(await screen.findByText(/Falha ao carregar estudos/i)).toBeInTheDocument();
  });

  it('salva flashcard visual sem gravar literal undefined quando mnemônico está ausente', async () => {
    const savedBodies: Array<{ verso?: string }> = [];
    vi.stubGlobal(
      'fetch',
      vi.fn(async (url: string, init?: RequestInit) => {
        if (url.includes('/api/estudos/flashcards') && init?.method === 'POST') {
          savedBodies.push(JSON.parse(String(init.body)));
          return new Response(JSON.stringify({ ok: true }), {
            status: 200,
            headers: { 'Content-Type': 'application/json' },
          });
        }
        if (url.includes('/api/estudos/flashcards/estatisticas')) {
          return new Response(
            JSON.stringify({ ativos: 0, arquivados: 0, novos: 0, pendentes: 0, revisoes: 0, acertos: 0, pct_acerto: null, basis: '0 ativos' }),
            { status: 200, headers: { 'Content-Type': 'application/json' } },
          );
        }
        if (url.includes('/api/estudos/flashcards/visuais')) {
          return new Response(
            JSON.stringify({
              flashcards: [
                {
                  id: 'fc-sem-mnem',
                  frente: 'Conceito ACID',
                  verso: 'Atomicidade, Consistência, Isolamento e Durabilidade.',
                  tag: 'Transações',
                },
              ],
            }),
            { status: 200, headers: { 'Content-Type': 'application/json' } },
          );
        }
        if (url.includes('/api/estudos/flashcards')) {
          return new Response(
            JSON.stringify({ vencidos: [], novos: [], futuros: [] }),
            { status: 200, headers: { 'Content-Type': 'application/json' } },
          );
        }
        return new Response('{}', { status: 200, headers: { 'Content-Type': 'application/json' } });
      }),
    );

    renderPage('/estudos/flashcards');

    const saveBtn = await screen.findByRole('button', { name: /\+ SM-2/i }, { timeout: 4000 });
    fireEvent.click(saveBtn);

    await waitFor(() => {
      expect(savedBodies.length).toBe(1);
    });
    expect(savedBodies[0].verso).toBe('Atomicidade, Consistência, Isolamento e Durabilidade.');
    expect(savedBodies[0].verso).not.toContain('undefined');
  });

  it('exibe tabela estilo PCI de Provas Anteriores (/estudos/provas) com foco em TI e áreas em expansão', async () => {
    const createdExams: unknown[] = [];
    vi.stubGlobal(
      'fetch',
      vi.fn(async (url: string, init?: RequestInit) => {
        if (url.includes('/api/estudos/provas')) {
          return new Response(
            JSON.stringify({
              total: 2,
              por_carreira: { ti: 1, fiscal: 1 },
              itens: [
                {
                  id: 'prova-fgv-mpo-2024-ti',
                  titulo: 'Analista de Planejamento e Orçamento - Tecnologia da Informação',
                  cargo: 'Analista de Planejamento e Orçamento (TI)',
                  orgao: 'MPO',
                  banca_slug: 'fgv',
                  banca_nome: 'FGV',
                  ano: 2024,
                  nivel: 'superior',
                  carreira: 'ti',
                  carreira_label: 'TI & Sistemas de Informação',
                  edital_ou_prova_url: 'https://conhecimento.fgv.br/concursos/mpo24',
                  gabarito_url: 'https://conhecimento.fgv.br/concursos/mpo24',
                  questoes_count: 4,
                  simulado_tag: 'orgao:mpo',
                },
                {
                  id: 'prova-fgv-sefaz-fiscal',
                  titulo: 'Auditor Fiscal da Receita Estadual',
                  cargo: 'Auditor Fiscal',
                  orgao: 'SEFAZ/MG',
                  banca_slug: 'fgv',
                  banca_nome: 'FGV',
                  ano: 2023,
                  nivel: 'superior',
                  carreira: 'fiscal',
                  carreira_label: 'Fiscal & Controle',
                  edital_ou_prova_url: 'https://conhecimento.fgv.br/concursos/',
                  gabarito_url: null,
                  questoes_count: 0,
                  simulado_tag: null,
                },
              ],
            }),
            { status: 200, headers: { 'Content-Type': 'application/json' } },
          );
        }
        if (url.includes('/api/estudos/simulados') && init?.method === 'POST') {
          createdExams.push(JSON.parse(String(init.body)));
          return new Response(
            JSON.stringify({
              id: 'sim-mpo-1',
              nome: 'Prova FGV 2024 — MPO',
              modo: 'tradicional',
              estado: 'em_andamento',
              duracao_segundos: null,
            }),
            { status: 200, headers: { 'Content-Type': 'application/json' } },
          );
        }
        return new Response('[]', { status: 200, headers: { 'Content-Type': 'application/json' } });
      }),
    );

    renderPage('/estudos/provas');

    expect(
      await screen.findByText('Analista de Planejamento e Orçamento - Tecnologia da Informação'),
    ).toBeInTheDocument();
    expect(screen.getByText('MPO')).toBeInTheDocument();
    expect(screen.getByText('Auditor Fiscal da Receita Estadual')).toBeInTheDocument();

    const simBtn = screen.getByRole('button', { name: /Simular Prova/i });
    fireEvent.click(simBtn);

    await waitFor(() => {
      expect(createdExams.length).toBe(1);
    });
    expect(createdExams[0]).toMatchObject({ tags: ['orgao:mpo'] });
  });

  it('exibe índice de Simulados por Disciplina estilo PCI em 1 clique (/estudos/simulados)', async () => {
    const createdSubjectExams: unknown[] = [];
    vi.stubGlobal(
      'fetch',
      vi.fn(async (url: string, init?: RequestInit) => {
        if (url.includes('/api/estudos/questoes')) {
          return new Response(
            JSON.stringify([
              { id: 'q1', enunciado: 'Q1', disciplina: 'Banco de Dados' },
              { id: 'q2', enunciado: 'Q2', disciplina: 'Banco de Dados' },
              { id: 'q3', enunciado: 'Q3', disciplina: 'Redes de Computadores' },
            ]),
            { status: 200, headers: { 'Content-Type': 'application/json' } },
          );
        }
        if (url.includes('/api/estudos/desempenho')) {
          return new Response(
            JSON.stringify({
              geral: { total: 0, respondidas: 0, acertos: 0, erros: 0, brancos: 0, denominator: 0, pct: null, basis: '' },
              por_disciplina: [{ grupo: 'Banco de Dados', total: 2, acertos: 2, erros: 0, brancos: 0, pct: 100 }],
              por_topico: [],
              simulados: [],
            }),
            { status: 200, headers: { 'Content-Type': 'application/json' } },
          );
        }
        if (url.includes('/api/estudos/simulados') && init?.method === 'POST') {
          createdSubjectExams.push(JSON.parse(String(init.body)));
          return new Response(
            JSON.stringify({
              id: 'sim-bd-1',
              nome: 'Simulado — Banco de Dados',
              modo: 'tradicional',
              estado: 'em_andamento',
              duracao_segundos: null,
            }),
            { status: 200, headers: { 'Content-Type': 'application/json' } },
          );
        }
        if (url.includes('/api/estudos/simulados/sim-bd-1/questoes')) {
          return new Response(JSON.stringify({ questoes: [] }), {
            status: 200,
            headers: { 'Content-Type': 'application/json' },
          });
        }
        return new Response('[]', { status: 200, headers: { 'Content-Type': 'application/json' } });
      }),
    );

    renderPage('/estudos/simulados');

    expect(await screen.findByText('Simulados por Disciplina')).toBeInTheDocument();
    expect(await screen.findByText('2 questões')).toBeInTheDocument();

    const startBdBtn = screen.getByRole('button', { name: /Iniciar simulado de Banco de Dados/i });
    fireEvent.click(startBdBtn);

    await waitFor(() => {
      expect(createdSubjectExams.length).toBe(1);
    });
    expect(createdSubjectExams[0]).toMatchObject({ disciplina: 'Banco de Dados' });
  });
});
