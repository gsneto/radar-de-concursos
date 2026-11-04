import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { fireEvent, render, screen } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { OverviewPage } from './OverviewPage';

function renderPage() {
  const client = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  return render(
    <QueryClientProvider client={client}>
      <MemoryRouter>
        <OverviewPage />
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

const sampleOpportunity = {
  contest_id: 'c-tjpe',
  competition_id: 'tjpe26',
  contest_label: 'TJ-PE 2026',
  role_id: 'r-1',
  role_name: 'Analista Judiciário - Sistemas de Informação',
  scope: 'role:r-1',
  ultima_atualizacao: '2026-11-04T12:00:00Z',
  prontidao: {
    estado: 'candidatos_prontos_para_revisao',
    estado_label: 'Pronto para revisão',
    motivos: ['Campos extraídos com evidência'],
  },
  si: { estado: 'explicito', motivo: 'Cita Sistemas de Informação' },
  indigenas: { estado: 'explicito_imediato', quantidade: 2 },
  localizacao: {
    prova: { text: 'Recife/PE', uf: 'PE', state: 'extraido_nao_revisado' },
    lotacao: { text: 'Recife/PE', uf: 'PE', state: 'extraido_nao_revisado' },
  },
  prazos: [
    {
      contest_id: 'c-tjpe',
      grupo: 'inscricao_fim',
      grupo_label: 'Fim das inscrições',
      valor: '2026-11-15',
      dias_restantes: 11,
      urgencia: 'ate_30_dias',
      urgencia_label: 'Em até 30 dias',
      estado_temporal: 'futuro',
      estado_operacional: 'revalidado_na_fonte',
      estado_operacional_label: 'Revalidado na fonte',
      documento: 'Edital de abertura',
      pagina: 3,
    },
  ],
};

beforeEach(() => {
  vi.unstubAllGlobals();
});

describe('OverviewPage', () => {
  it('renderiza indicadores, oportunidades prioritárias, prazos próximos e funil de cobertura', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn(async (url: string) => {
        if (url.startsWith('/api/carteira')) {
          return new Response(
            JSON.stringify({
              total: 1,
              referencia: { hoje_local: '2026-11-04', fuso: 'America/Recife' },
              por_urgencia: { ate_30_dias: 1, ate_7_dias: 0, vencido: 2 },
              por_prontidao: { candidatos_prontos_para_revisao: 1 },
              itens: [sampleOpportunity],
            }),
            { status: 200, headers: { 'Content-Type': 'application/json' } },
          );
        }
        if (url.startsWith('/api/cobertura/resumo')) {
          return new Response(
            JSON.stringify({
              escopo: { concursos: 843, com_documento: 843, com_edital_analisado: 66 },
              funil: [
                { etapa: 'concursos', quantidade: 843, de: 843 },
                { etapa: 'com_propostas', quantidade: 61, de: 843 },
              ],
              causas: { apenas_agregador: 703 },
            }),
            { status: 200, headers: { 'Content-Type': 'application/json' } },
          );
        }
        if (url.startsWith('/api/linha-do-tempo')) {
          return new Response(
            JSON.stringify({
              ciclos: [
                {
                  id: 'cyc-1',
                  started_at: '2026-11-04T10:00:00Z',
                  state: 'concluido',
                  versions_new: 4,
                  documents_new: 2,
                },
              ],
            }),
            { status: 200, headers: { 'Content-Type': 'application/json' } },
          );
        }
        if (url.startsWith('/api/estudos/painel')) {
          return new Response(
            JSON.stringify({
              total_segundos: 3600,
              semana_segundos: 1800,
              sessoes_concluidas: 2,
              revisoes_pendentes: 1,
              disciplinas: 1,
              conteudo: { topics: { done: 2, total: 5, pct: 40 }, overall: { done: 2, total: 5, pct: 40 } },
              minutos_por_disciplina: [],
              revisoes: [],
              sessao_aberta: null,
            }),
            { status: 200, headers: { 'Content-Type': 'application/json' } },
          );
        }
        if (url.startsWith('/api/prazos/calendario')) {
          return new Response(
            JSON.stringify({
              total: 1,
              referencia: { hoje_local: '2026-11-04', fuso: 'America/Recife' },
              por_urgencia: { ate_30_dias: 1 },
              itens: sampleOpportunity.prazos,
            }),
            { status: 200, headers: { 'Content-Type': 'application/json' } },
          );
        }
        return new Response('{}', { status: 200 });
      }),
    );

    renderPage();

    expect(await screen.findByText('TJ-PE 2026')).toBeInTheDocument();
    expect(screen.getByText(/Analista Judiciário - Sistemas de Informação/)).toBeInTheDocument();
    expect(screen.getByText('Fim das inscrições')).toBeInTheDocument();
    expect(screen.getByRole('region', { name: 'Indicadores' })).toBeInTheDocument();
    expect(screen.getByText('Apenas agregador')).toBeInTheDocument();
  });

  it('exibe estados vazios honestos quando não há itens na carteira ou ciclos', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn(async () =>
        new Response(
          JSON.stringify({
            total: 0,
            referencia: { hoje_local: '2026-11-04', fuso: 'America/Recife' },
            por_urgencia: {},
            por_prontidao: {},
            itens: [],
            ciclos: [],
            funil: [],
            causas: {},
            total_segundos: 0,
            sessoes_concluidas: 0,
            revisoes_pendentes: 0,
            disciplinas: 0,
          }),
          { status: 200, headers: { 'Content-Type': 'application/json' } },
        ),
      ),
    );

    renderPage();

    expect(await screen.findByText('Nenhuma oportunidade na carteira')).toBeInTheDocument();
    expect(screen.getByText('Nenhum ciclo registrado')).toBeInTheDocument();
    expect(screen.getByText('Sem dados de cobertura')).toBeInTheDocument();
    expect(screen.getByText('Seu estudo começa aqui')).toBeInTheDocument();
  });

  it('exibe estado de erro e permite tentar novamente quando a API falha', async () => {
    const fetchMock = vi.fn(async (url: string) => {
      if (url.startsWith('/api/carteira')) {
        return new Response(JSON.stringify({ error: 'Banco indisponível' }), {
          status: 503,
          headers: { 'Content-Type': 'application/json' },
        });
      }
      return new Response('{}', { status: 200, headers: { 'Content-Type': 'application/json' } });
    });
    vi.stubGlobal('fetch', fetchMock);

    renderPage();

    expect(await screen.findByText(/Banco indisponível/i)).toBeInTheDocument();
    const retryBtn = screen.getByRole('button', { name: /tentar novamente/i });
    fireEvent.click(retryBtn);
    expect(fetchMock).toHaveBeenCalled();
  });
});
