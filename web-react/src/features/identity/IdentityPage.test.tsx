import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { IdentityPage } from './IdentityPage';

const reconciliation = {
  version: 'role_identity_v1',
  generated_at: '2026-10-29T00:00:00+00:00',
  total: 1,
  limit: 25,
  offset: 0,
  has_more: false,
  limitacao: 'Ordenação por utilidade estrutural.',
  itens: [
    {
      contest_id: 'c1',
      label: 'PROFESSOR PII - EDUCAÇÃO FÍSICA',
      nature: 'abreviacao',
      nature_label: 'Abreviação de cargo',
      normalized: 'professor pii educacao fisica',
      proposals: 12,
      fields: ['immediate_vacancies'],
      documents: [{ document_id: 'd1', title: 'Edital' }],
      pages: [3, 4],
      first_evidence: {
        document_id: 'd1',
        document_title: 'Edital',
        tipo_documental: 'edital_abertura',
        published_at: '2026-01-10',
        page_number: 3,
        quote: 'PROFESSOR PII - EDUCAÇÃO FÍSICA',
        version_id: 'v1',
        proposal_id: 'p1',
      },
      suggestions: [
        {
          role_id: 'role-1',
          role_name: 'PROFESSOR PII - EDUCAÇÃO FÍSICA',
          specialty: null,
          code: null,
          state: 'exata',
          pontuacao: 40,
          fatores: [{ fator: 'nome_identico', pontos: 40, motivo: 'nome idêntico' }],
        },
      ],
      cargo_count: 1,
      decision: null,
      state: 'exata',
    },
  ],
};

const conflicts = {
  version: 'conflict_review_v1',
  generated_at: '2026-10-29T00:00:00+00:00',
  total: 1,
  por_causa: { escopo_diferente: 1 },
  por_prioridade: { 3: 1 },
  limit: 20,
  offset: 0,
  has_more: false,
  limitacao: 'Classificação por evidência.',
  itens: [
    {
      contest_id: 'c1',
      scope: 'label:Cargo A',
      field_name: 'education',
      cause: 'escopo_diferente',
      cause_label: 'Escopo diferente',
      motivos: ['trechos descrevem cargos distintos'],
      prioridade: 3,
      proxima_acao: 'separar por cargo antes de comparar',
      valores_distintos: 2,
      propostas: [
        {
          proposal_id: 'p1',
          value: 'Superior em Direito',
          state: 'pendente',
          document_id: 'd1',
          document_title: 'Edital',
          tipo_documental: 'edital_abertura',
          published_at: '2026-01-10',
          version_id: 'v1',
          page_number: 4,
          quote: 'Superior em Direito',
          extraction_method: 'requisito-inline',
        },
      ],
      documentos: [],
      vigente_candidato: null,
      vigente_documento: null,
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
        <IdentityPage />
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

function mockFetch() {
  const fetchMock = vi.fn(async (url: string, init?: RequestInit) => {
    void init;
    const body =
      url.startsWith('/api/reconciliacao') ? reconciliation : conflicts;
    return new Response(JSON.stringify(body), {
      status: 200,
      headers: { 'Content-Type': 'application/json' },
    });
  });
  vi.stubGlobal('fetch', fetchMock);
  return fetchMock;
}

beforeEach(() => {
  localStorage.clear();
  vi.unstubAllGlobals();
});

describe('página de Identidades', () => {
  it('mostra rótulo, natureza, sugestão e a pontuação declarada', async () => {
    mockFetch();
    renderPage();
    // O rótulo aparece no cabeçalho e como nome do cargo sugerido.
    expect((await screen.findAllByText('PROFESSOR PII - EDUCAÇÃO FÍSICA')).length).toBeGreaterThan(0);
    expect(screen.getByText(/Abreviação de cargo/)).toBeInTheDocument();
    expect(screen.getByText(/pontuação 40/)).toBeInTheDocument();
    expect(screen.getByText(/nome idêntico/)).toBeInTheDocument();
  });

  it('bloqueia a decisão sem responsável e justificativa', async () => {
    mockFetch();
    renderPage();
    const confirmar = await screen.findByRole('button', { name: /confirmar cargo/i });
    expect(confirmar).toBeDisabled();

    fireEvent.change(screen.getByPlaceholderText(/seu nome/i), { target: { value: 'anton' } });
    expect(confirmar).toBeDisabled();

    fireEvent.change(screen.getByPlaceholderText(/por que este é/i), {
      target: { value: 'rótulo idêntico ao cargo do edital' },
    });
    expect(confirmar).toBeEnabled();
  });

  it('envia a decisão com dry_run false e o cargo sugerido', async () => {
    const fetchMock = mockFetch();
    renderPage();
    fireEvent.change(await screen.findByPlaceholderText(/seu nome/i), {
      target: { value: 'anton' },
    });
    fireEvent.change(screen.getByPlaceholderText(/por que este é/i), {
      target: { value: 'rótulo idêntico' },
    });
    fireEvent.click(screen.getByRole('button', { name: /confirmar cargo/i }));

    await waitFor(() => {
      expect(
        fetchMock.mock.calls.some(
          ([url, init]) =>
            String(url) === '/api/reconciliacao' &&
            (init as RequestInit)?.method === 'POST',
        ),
      ).toBe(true);
    });

    const call = fetchMock.mock.calls.find(
      ([url, init]) =>
        String(url) === '/api/reconciliacao' && (init as RequestInit)?.method === 'POST',
    )!;
    const body = JSON.parse(String((call[1] as RequestInit).body));
    expect(body).toMatchObject({
      contest_id: 'c1',
      label: 'PROFESSOR PII - EDUCAÇÃO FÍSICA',
      state: 'confirmada',
      reviewer: 'anton',
      reason: 'rótulo idêntico',
      role_id: 'role-1',
      dry_run: false,
    });
  });

  it('aba de conflitos mostra a causa e a próxima ação', async () => {
    mockFetch();
    renderPage();
    await screen.findAllByText('PROFESSOR PII - EDUCAÇÃO FÍSICA');
    fireEvent.click(screen.getByRole('tab', { name: /conflitos/i }));
    // A causa também é uma opção do filtro: procura dentro do cartão.
    const card = await screen.findByRole('article');
    expect(card).toHaveTextContent('Escopo diferente');
    expect(card).toHaveTextContent('separar por cargo antes de comparar');
    expect(card).toHaveTextContent('Superior em Direito');
  });
});
