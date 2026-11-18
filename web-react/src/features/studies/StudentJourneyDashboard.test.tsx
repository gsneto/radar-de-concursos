import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { fireEvent, render, screen } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { StudentJourneyDashboard } from './tabs/StudentJourneyDashboard';

function renderDashboard(initialEntry = '/estudos/evolucao') {
  const client = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  return render(
    <QueryClientProvider client={client}>
      <MemoryRouter initialEntries={[initialEntry]}>
        <StudentJourneyDashboard />
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

beforeEach(() => {
  vi.unstubAllGlobals();
  localStorage.clear();
});

describe('StudentJourneyDashboard', () => {
  it('renderiza dashboard de evolução por aula (etapas %) e histórico cronológico filtrável de tudo que o aluno fez', async () => {
    localStorage.setItem(
      'radar:u:usr-dash-1:lesson_stage_progress',
      JSON.stringify({
        'bd-01': {
          resumo: '2026-11-18T10:00:00Z',
          visual: '2026-11-18T10:20:00Z',
        },
      }),
    );
    localStorage.setItem(
      'radar:u:usr-dash-1:student_activity_log',
      JSON.stringify([
        {
          id: 'act-2',
          type: 'etapa_concluida',
          title: 'Concluiu 2. Quadro Digital & Mapa Mental (40%)',
          subtitle: 'Aula 01: Modelagem Conceitual',
          disciplina: 'Banco de Dados',
          lessonId: 'bd-01',
          stage: 'visual',
          pct: 40,
          timestamp: '2026-11-18T10:20:00Z',
        },
        {
          id: 'act-1',
          type: 'flashcard_salvo',
          title: 'Salvou flashcard na fila SM-2: O que exige a 1FN?',
          subtitle: 'Aula 01: Modelagem Conceitual',
          disciplina: 'Banco de Dados',
          lessonId: 'bd-01',
          timestamp: '2026-11-18T10:15:00Z',
        },
      ]),
    );

    vi.stubGlobal(
      'fetch',
      vi.fn(async (url: string) => {
        if (url.includes('/api/auth/me')) {
          return new Response(
            JSON.stringify({
              authenticated: true,
              user: { id: 'usr-dash-1', nome: 'Marina', email: 'm@radar.dev', role: 'student', plan: 'pro', status: 'active' },
            }),
            { status: 200, headers: { 'Content-Type': 'application/json' } },
          );
        }
        if (url.includes('/api/estudos/aulas')) {
          return new Response(
            JSON.stringify({
              aulas: [
                {
                  id: 'bd-01',
                  disciplina: 'Banco de Dados',
                  titulo: 'Aula 01: Modelagem Conceitual',
                  objetivos: ['1FN, 2FN e 3FN'],
                  questoes_count: 3,
                },
                {
                  id: 'redes-01',
                  disciplina: 'Redes de Computadores',
                  titulo: 'Aula 02: Modelo TCP/IP',
                  objetivos: ['Camadas e protocolos'],
                  questoes_count: 2,
                },
              ],
            }),
            { status: 200, headers: { 'Content-Type': 'application/json' } },
          );
        }
        if (url.includes('/api/estudos/painel')) {
          return new Response(
            JSON.stringify({
              total_segundos: 3600,
              semana_segundos: 3600,
              sessoes_concluidas: 1,
              revisoes_pendentes: 0,
              disciplinas: 2,
              conteudo: { topics: { done: 0, total: 0, pct: 0 }, overall: { done: 0, total: 0, pct: 0 } },
              minutos_por_disciplina: [{ disciplina_id: 'd1', nome: 'Banco de Dados', minutos: 60 }],
              revisoes: [],
              sessao_aberta: null,
            }),
            { status: 200, headers: { 'Content-Type': 'application/json' } },
          );
        }
        if (url.includes('/api/estudos/desempenho')) {
          return new Response(
            JSON.stringify({
              geral: { total: 5, respondidas: 5, acertos: 4, erros: 1, brancos: 0, denominator: 5, pct: 80, basis: '4 de 5 questões' },
              por_disciplina: [{ grupo: 'Banco de Dados', total: 5, acertos: 4, erros: 1, brancos: 0, pct: 80 }],
              por_topico: [],
              simulados: [],
            }),
            { status: 200, headers: { 'Content-Type': 'application/json' } },
          );
        }
        if (url.includes('/api/estudos/sessoes')) {
          return new Response(
            JSON.stringify([
              {
                id: 'sess-1',
                modo: 'aula',
                estado: 'concluida',
                segundos_acumulados: 1800,
                iniciada_em: '2026-11-18T09:00:00Z',
                encerrada_em: '2026-11-18T09:30:00Z',
              },
            ]),
            { status: 200, headers: { 'Content-Type': 'application/json' } },
          );
        }
        if (url.includes('/api/estudos/simulados')) {
          return new Response(
            JSON.stringify([
              {
                id: 'sim-1',
                nome: 'Simulado FGV — MPO',
                modo: 'tradicional',
                estado: 'finalizado',
                duracao_segundos: 1200,
                criado_em: '2026-11-18T11:00:00Z',
              },
            ]),
            { status: 200, headers: { 'Content-Type': 'application/json' } },
          );
        }
        return new Response('{}', { status: 200, headers: { 'Content-Type': 'application/json' } });
      }),
    );

    renderDashboard();

    // Mostra aula com 40% das etapas concluídas + histórico completo
    const aulaLabels = await screen.findAllByText('Aula 01: Modelagem Conceitual');
    expect(aulaLabels.length).toBeGreaterThan(0);
    expect(screen.getAllByText('40%').length).toBeGreaterThan(0);
    expect(screen.getByText(/Concluiu 2\. Quadro Digital & Mapa Mental \(40%\)/i)).toBeInTheDocument();
    expect(screen.getByText(/Salvou flashcard na fila SM-2/i)).toBeInTheDocument();
    expect(screen.getByText(/Simulado FGV — MPO/i)).toBeInTheDocument();

    // Filtra apenas Flashcards na linha do tempo
    fireEvent.click(screen.getByRole('button', { name: /^Flashcards$/i }));
    expect(screen.getByText(/Salvou flashcard na fila SM-2/i)).toBeInTheDocument();
    expect(screen.queryByText(/Concluiu 2\. Quadro Digital/i)).not.toBeInTheDocument();
  });

  it('mostra estado vazio honesto quando o estudante ainda não realizou atividades', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn(async (url: string) => {
        if (url.includes('/api/auth/me')) {
          return new Response(
            JSON.stringify({ authenticated: false, user: null }),
            { status: 200, headers: { 'Content-Type': 'application/json' } },
          );
        }
        if (url.includes('/api/estudos/aulas')) {
          return new Response(JSON.stringify({ aulas: [] }), {
            status: 200,
            headers: { 'Content-Type': 'application/json' },
          });
        }
        return new Response('[]', { status: 200, headers: { 'Content-Type': 'application/json' } });
      }),
    );

    renderDashboard();

    expect(await screen.findByText(/Ainda não há atividades registradas/i)).toBeInTheDocument();
  });
});
