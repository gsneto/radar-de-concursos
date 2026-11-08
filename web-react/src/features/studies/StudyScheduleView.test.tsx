import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { fireEvent, render, screen } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { StudyScheduleView } from './StudyScheduleView';

function renderSchedule() {
  const client = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  return render(
    <QueryClientProvider client={client}>
      <MemoryRouter initialEntries={['/estudos/cronograma']}>
        <StudyScheduleView />
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

beforeEach(() => {
  vi.unstubAllGlobals();
  localStorage.clear();
});

describe('StudyScheduleView', () => {
  it('renderiza o cabeçalho, dias da semana e blocos de estudo', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn(async (url: string) => {
        if (url.includes('/api/meus-concursos')) {
          return new Response(
            JSON.stringify({
              total: 1,
              itens: [
                {
                  id: 'mc-1',
                  contest_id: 'c-1',
                  contest_label: 'Processo Seletivo ABDI 2026',
                  orgao: 'ABDI',
                  banca: 'FGV',
                  role_name: 'Analista de TI',
                  status: 'ativo',
                },
              ],
            }),
            { status: 200, headers: { 'Content-Type': 'application/json' } },
          );
        }
        if (url.includes('/api/estudos/bancas')) {
          return new Response(
            JSON.stringify({
              bancas: {
                fgv: {
                  id: 'fgv',
                  nome: 'Fundação Getulio Vargas (FGV)',
                  formato: 'Múltipla Escolha',
                  perfil_estilo: 'Enunciados longos em estudos de caso reais.',
                },
              },
            }),
            { status: 200, headers: { 'Content-Type': 'application/json' } },
          );
        }
        if (url.includes('/api/estudos/disciplinas')) {
          return new Response(JSON.stringify([]), {
            status: 200,
            headers: { 'Content-Type': 'application/json' },
          });
        }
        return new Response(JSON.stringify({}), { status: 200 });
      }),
    );

    renderSchedule();

    // Cabeçalho e diretriz da banca
    expect(await screen.findByText('Grade Semanal de Estudos Recomendada')).toBeInTheDocument();
    expect(await screen.findByText(/Diretriz da Banca/i)).toBeInTheDocument();

    // Dias da semana
    expect(screen.getByText('Segunda-feira')).toBeInTheDocument();
    expect(screen.getByText('Terça-feira')).toBeInTheDocument();
    expect(screen.getByText('Quarta-feira')).toBeInTheDocument();
    expect(screen.getByText('Quinta-feira')).toBeInTheDocument();
    expect(screen.getByText('Sexta-feira')).toBeInTheDocument();
    expect(screen.getByText('Sábado')).toBeInTheDocument();
    expect(screen.getByText('Domingo')).toBeInTheDocument();

    // Disciplinas de TI presentes na grade
    expect(screen.getByText('Engenharia de Software & Programação')).toBeInTheDocument();
    expect(screen.getByText('Banco de Dados')).toBeInTheDocument();
  });

  it('permite alternar a carga horária semanal e marcar blocos como concluídos', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn(async () =>
        new Response(
          JSON.stringify({
            total: 0,
            itens: [],
          }),
          { status: 200, headers: { 'Content-Type': 'application/json' } },
        ),
      ),
    );

    renderSchedule();

    // Alterar meta para 30h
    const btn30h = await screen.findByRole('button', { name: '30h' });
    fireEvent.click(btn30h);
    expect(btn30h).toHaveClass('bg-amber-400');

    // Marcar um bloco como concluído
    const checkButtons = screen.getAllByRole('button', { name: /Marcar como concluído/i });
    expect(checkButtons.length).toBeGreaterThan(0);
    fireEvent.click(checkButtons[0]);

    // O primeiro botão agora tem label de concluído
    expect(screen.getByRole('button', { name: /Marcar como não concluído/i })).toBeInTheDocument();
  });
});
