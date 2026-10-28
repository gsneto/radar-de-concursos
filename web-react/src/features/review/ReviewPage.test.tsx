import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { ReviewPage } from './ReviewPage';

const group = {
  linha_id: 'linha-1',
  contest_id: 'c1',
  competition_id: 'quadrix-3049',
  document_id: 'd1',
  document_title: 'Edital nº 1',
  tipo_documental: 'edital_abertura',
  issuer: 'Quadrix',
  official_url: 'https://x/edital.pdf',
  version_id: 'v1',
  page_number: 9,
  scope: 'label:Juiz Substituto',
  scopes: ['label:Juiz Substituto'],
  identidade: 'pendente',
  prioridade: 7,
  estado: 'pendente',
  estados: ['pendente'],
  pendentes: 2,
  conflito: false,
  contexto: { tipo: 'colunas', trecho: 'Juiz Substituto 4 0 0 0 0 0 0 4' },
  validacao: {
    tipo: 'colunas',
    publicado: 4,
    soma: 4,
    diferenca: 0,
    estado: 'consistente',
    regra: 'AC+PcD+PP+PI+PQ+PPIQ+PI/PQ = Total',
  },
  rotulo_divergente: null,
  proxima_acao: 'revisar campo a campo (cada decisão é independente)',
  propostas: [
    {
      proposal_id: 'p-1',
      field_name: 'immediate_vacancies',
      field_label: 'Vagas imediatas (total publicado)',
      value: 4,
      state: 'pendente',
      last_decision: null,
      selected: false,
      consequencia: 'Total publicado da linha.',
      historico: [],
      ambiguity_reason: 'cargo do documento não reconciliado: Juiz Substituto',
      extraction_method: 'quadro-colunas-pdf',
      evidence_sha256: 'abc123',
      scope_snapshot: ['p-1', 'p-2'],
      evidence: {
        quote: 'Juiz Substituto 4 0 0 0 0 0 0 4',
        page_number: 9,
        version_id: 'v1',
        start_offset: 0,
        end_offset: 34,
        document_id: 'd1',
      },
    },
    {
      proposal_id: 'p-2',
      field_name: 'indigenous_vacancies',
      field_label: 'Indígenas (coluna exclusiva)',
      value: 0,
      state: 'validado',
      last_decision: 'validado',
      selected: true,
      consequencia: null,
      historico: [],
      ambiguity_reason: null,
      extraction_method: 'quadro-colunas-pdf',
      evidence_sha256: 'def456',
      scope_snapshot: ['p-1', 'p-2'],
      evidence: {
        quote: 'Juiz Substituto 4 0 0 0 0 0 0 4',
        page_number: 9,
        version_id: 'v1',
        start_offset: 0,
        end_offset: 34,
        document_id: 'd1',
      },
    },
  ],
};

function renderPage() {
  const client = new QueryClient({
    defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
  });
  return render(
    <QueryClientProvider client={client}>
      <MemoryRouter>
        <ReviewPage />
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

function mockFetch() {
  const fetchMock = vi.fn(async (url: string, init?: RequestInit) => {
    void init;
    if (url.startsWith('/api/revisao/grupos')) {
      return new Response(
        JSON.stringify({
          version: 'review_groups_v1',
          generated_at: '2026-10-28T00:00:00+00:00',
          total: 1,
          limit: 20,
          offset: 0,
          has_more: false,
          filtros: {},
          resumo: {
            linhas: 1,
            linhas_prontas: 1,
            linhas_divergentes: 0,
            propostas: 2,
            propostas_pendentes: 1,
            com_conflito: 0,
            decisoes_registradas: 1,
          },
          itens: [group],
          limitacao: 'Grupo é contexto de navegação, não decisão conjunta.',
        }),
        { status: 200, headers: { 'Content-Type': 'application/json' } },
      );
    }
    if (url.startsWith('/api/revisao/proposta/')) {
      return new Response(JSON.stringify({ decision: 'validado' }), {
        status: 200,
        headers: { 'Content-Type': 'application/json' },
      });
    }
    return new Response('{}', { status: 200 });
  });
  vi.stubGlobal('fetch', fetchMock);
  return fetchMock;
}

beforeEach(() => {
  localStorage.clear();
  vi.unstubAllGlobals();
});

describe('página de Revisão', () => {
  it('mostra o trecho, a validação e o valor do campo', async () => {
    mockFetch();
    renderPage();
    expect(await screen.findByText('Vagas imediatas (total publicado)')).toBeInTheDocument();
    expect(screen.getByText('soma confere')).toBeInTheDocument();
    expect(screen.getByText(/Juiz Substituto 4 0 0 0 0 0 0 4/)).toBeInTheDocument();
  });

  it('bloqueia a decisão sem responsável e sem justificativa', async () => {
    mockFetch();
    renderPage();
    const validar = await screen.findByRole('button', { name: /validar vagas imediatas/i });
    expect(validar).toBeDisabled();

    fireEvent.change(screen.getByPlaceholderText(/seu nome/i), { target: { value: 'anton' } });
    expect(validar).toBeDisabled();

    fireEvent.change(screen.getByPlaceholderText(/o que você conferiu/i), {
      target: { value: 'total confere com o quadro' },
    });
    expect(validar).toBeEnabled();
  });

  it('envia decisão com autor, justificativa, hash e snapshot do escopo', async () => {
    const fetchMock = mockFetch();
    renderPage();
    fireEvent.change(await screen.findByPlaceholderText(/seu nome/i), {
      target: { value: 'anton' },
    });
    fireEvent.change(screen.getByPlaceholderText(/o que você conferiu/i), {
      target: { value: 'total confere com o quadro' },
    });
    fireEvent.click(screen.getByRole('button', { name: /validar vagas imediatas/i }));

    await waitFor(() => {
      const call = fetchMock.mock.calls.find(([url]) =>
        String(url).startsWith('/api/revisao/proposta/'),
      );
      expect(call).toBeTruthy();
    });

    const [url, init] = fetchMock.mock.calls.find(([callUrl]) =>
      String(callUrl).startsWith('/api/revisao/proposta/'),
    )!;
    expect(url).toBe('/api/revisao/proposta/p-1');
    const body = JSON.parse(String((init as RequestInit).body));
    expect(body).toMatchObject({
      decision: 'validado',
      reviewer: 'anton',
      reason: 'total confere com o quadro',
      origin: 'interface',
      evidence_sha256: 'abc123',
      scope_snapshot: ['p-1', 'p-2'],
    });
  });

  it('não oferece decisão para campo já decidido', async () => {
    mockFetch();
    renderPage();
    await screen.findByText('Vagas imediatas (total publicado)');
    expect(
      screen.queryByRole('button', { name: /validar indígenas/i }),
    ).toBeNull();
  });

  it('lembra o responsável entre visitas', async () => {
    localStorage.setItem('radar.reviewer', 'anton');
    mockFetch();
    renderPage();
    expect(await screen.findByDisplayValue('anton')).toBeInTheDocument();
  });
});
