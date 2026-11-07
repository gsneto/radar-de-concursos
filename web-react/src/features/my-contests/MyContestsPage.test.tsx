import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { render, screen, waitFor } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { MyContestsPage } from './MyContestsPage';

function renderPage() {
  const client = new QueryClient({
    defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
  });
  return render(
    <QueryClientProvider client={client}>
      <MemoryRouter>
        <MyContestsPage />
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

beforeEach(() => {
  localStorage.clear();
  vi.unstubAllGlobals();
});

describe('MyContestsPage', () => {
  it('renderiza o estado vazio com CTA quando não há concursos selecionados', async () => {
    const fetchMock = vi.fn(async (url: string) => {
      if (url === '/api/meus-concursos') {
        return new Response(JSON.stringify({ total: 0, itens: [] }), {
          status: 200,
          headers: { 'Content-Type': 'application/json' },
        });
      }
      return new Response('{}', { status: 200 });
    });
    vi.stubGlobal('fetch', fetchMock);

    renderPage();

    await waitFor(() => {
      expect(screen.getByText('Seu Painel de Foco está Vazio')).toBeInTheDocument();
    });

    const cta = screen.getByRole('link', { name: /Buscar Concursos no Radar/i });
    expect(cta).toBeInTheDocument();
    expect(cta).toHaveAttribute('href', '/oportunidades');
  });

  it('renderiza os cartões dos concursos foco quando existem seleções', async () => {
    const fetchMock = vi.fn(async (url: string) => {
      if (url === '/api/meus-concursos') {
        return new Response(
          JSON.stringify({
            total: 1,
            itens: [
              {
                id: 'my-1',
                contest_id: 'contest-abdi',
                role_id: 'role-ti',
                contest_label: 'Processo Seletivo ABDI 2026',
                orgao: 'Agência Brasileira de Desenvolvimento Industrial – ABDI',
                banca: 'FGV Conhecimento',
                si_compativel: true,
                competition_id: 'psabdi',
                role_name: 'Analista de Produtividade e Inovação (TI)',
                role_specialty: 'Engenharia de Software',
                remuneracao: 'R$ 16.034,70',
                vagas: 5,
                proximo_prazo: { campo: 'inscricao_inicio', label: 'Início das Inscrições', data: '2026-12-03' },
                selected_at: '2026-11-06T12:00:00Z',
                status: 'ativo',
                notes: 'Foco principal de TI',
              },
            ],
          }),
          { status: 200, headers: { 'Content-Type': 'application/json' } },
        );
      }
      return new Response('{}', { status: 200 });
    });
    vi.stubGlobal('fetch', fetchMock);

    renderPage();

    await waitFor(() => {
      expect(screen.getByText('Agência Brasileira de Desenvolvimento Industrial – ABDI')).toBeInTheDocument();
      expect(screen.getByText('FGV Conhecimento')).toBeInTheDocument();
      expect(screen.getByText('Bacharelado em SI Compatível')).toBeInTheDocument();
      expect(screen.getByText('Analista de Produtividade e Inovação (TI)')).toBeInTheDocument();
      expect(screen.getByText('R$ 16.034,70')).toBeInTheDocument();
      expect(screen.getByText('5 vaga(s)')).toBeInTheDocument();
    });

    const studyLink = screen.getByRole('link', { name: /Estudar para este Concurso/i });
    expect(studyLink).toBeInTheDocument();
    expect(studyLink).toHaveAttribute('href', '/estudos?concurso=contest-abdi');
  });
});
