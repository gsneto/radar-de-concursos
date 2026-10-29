import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { MesaPage } from './MesaPage';

const listing = {
  version: 'opportunities_v1',
  generated_at: '2026-10-29T00:00:00+00:00',
  total: 1,
  limit: 25,
  offset: 0,
  has_more: false,
  limitacao: 'Cargo sem identidade não é ambiguidade do valor.',
  itens: [
    {
      contest_id: 'c1',
      competition_id: 'prefsjceducacao25',
      contest_title: 'Edital retificado',
      role_id: null,
      scope: '',
      role_name: null,
      role_reconciliado: false,
      role_code: null,
      role_specialty: null,
      documental: {
        estado: 'campos_candidatos',
        estado_label: 'Campos candidatos disponíveis para revisão',
        documentos: 34,
        documentos_oficiais: 34,
        editais: 1,
        retificacoes: 3,
        proxima_acao: 'revisar propostas dos campos decisivos',
      },
      campos: {
        education: {
          campo: 'education',
          label: 'Escolaridade/requisito',
          estado: 'em_conflito',
          valores: ['Licenciatura Plena'],
          propostas: 3,
          com_pagina: 3,
        },
        si_compatibility: {
          campo: 'si_compatibility',
          label: 'Compatibilidade com Sistemas de Informação',
          estado: 'ambiguo',
          valores: ['ambiguo'],
          propostas: 3,
          com_pagina: 3,
        },
        immediate_vacancies: {
          campo: 'immediate_vacancies',
          label: 'Vagas imediatas',
          estado: 'confirmado',
          valores: ['4'],
          propostas: 1,
          com_pagina: 1,
        },
      },
      pendentes: 2,
      propostas: 7,
      conflitos: 1,
      tem_pagina: true,
      ultima_atualizacao: '2026-10-18T02:28:22+00:00',
      prioridade: 6,
      motivos: ['vagas indígenas'],
      proxima_acao: 'revisar propostas dos campos decisivos',
    },
  ],
};

function renderPage() {
  const client = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  return render(
    <QueryClientProvider client={client}>
      <MemoryRouter>
        <MesaPage />
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

function mockFetch() {
  const fetchMock = vi.fn(async (url: string) => {
    void url;
    return new Response(JSON.stringify(listing), {
      status: 200,
      headers: { 'Content-Type': 'application/json' },
    });
  });
  vi.stubGlobal('fetch', fetchMock);
  return fetchMock;
}

beforeEach(() => {
  vi.unstubAllGlobals();
});

describe('página da Mesa', () => {
  it('mostra cargo, situação documental e o estado de cada campo decisivo', async () => {
    mockFetch();
    renderPage();
    expect(await screen.findByText('Cargo não reconciliado')).toBeInTheDocument();
    // "Campos candidatos" também é opção do filtro; procura dentro do cartão.
    const card = screen.getByRole('article');
    expect(card).toHaveTextContent('Campos candidatos');
    expect(screen.getByText('em conflito')).toBeInTheDocument();
    expect(screen.getByText('ambíguo')).toBeInTheDocument();
    expect(screen.getByText('confirmado')).toBeInTheDocument();
    expect(screen.getByText(/1 conflito/)).toBeInTheDocument();
  });

  it('mostra a próxima ação declarada pelo servidor', async () => {
    mockFetch();
    renderPage();
    expect(
      await screen.findAllByText(/revisar propostas dos campos decisivos/),
    ).not.toHaveLength(0);
  });

  it('envia os filtros escolhidos para a API', async () => {
    const fetchMock = mockFetch();
    renderPage();
    await screen.findByText('Cargo não reconciliado');

    fireEvent.change(screen.getByLabelText(/situação documental/i), {
      target: { value: 'campos_candidatos' },
    });
    await waitFor(() => {
      const urls = fetchMock.mock.calls.map(([url]) => String(url));
      expect(urls.some((url) => url.includes('document_state=campos_candidatos'))).toBe(true);
    });
  });

  it('busca por texto vai na query, não no cliente', async () => {
    const fetchMock = mockFetch();
    renderPage();
    await screen.findByText('Cargo não reconciliado');
    fireEvent.change(screen.getByPlaceholderText(/órgão, concurso ou cargo/i), {
      target: { value: 'quadrix' },
    });
    fireEvent.click(screen.getByRole('button', { name: /aplicar/i }));
    await waitFor(() => {
      const urls = fetchMock.mock.calls.map(([url]) => String(url));
      expect(urls.some((url) => url.includes('search=quadrix'))).toBe(true);
    });
  });

  it('linka o dossiê com o escopo do cargo', async () => {
    mockFetch();
    renderPage();
    const link = await screen.findByRole('link', { name: /abrir dossiê/i });
    expect(link.getAttribute('href')).toContain('/dossie/c1');
  });
});
