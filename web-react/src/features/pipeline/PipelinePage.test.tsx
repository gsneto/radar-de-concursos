import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { fireEvent, render, screen } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { PipelinePage } from './PipelinePage';

const summary = {
  version: 'pipeline_v1',
  generated_at: '2026-10-29T00:00:00+00:00',
  concursos: 830,
  concursos_com_documento: 829,
  concursos_com_edital: 66,
  documentos: 3303,
  documentos_com_texto: 1913,
  versoes: 1926,
  versoes_extraidas: 1913,
  propostas: 15382,
  evidencias: 15382,
  revisoes_humanas: 0,
  campos_confirmados: 0,
  falhas_por_codigo: { pdf_sem_texto: 6, pdf_ilegivel: 1 },
};

const documents = {
  version: 'pipeline_v1',
  generated_at: '2026-10-29T00:00:00+00:00',
  total: 2,
  returned: 2,
  truncated: false,
  por_bloqueio: { sem_propostas: 1698, sem_versao: 1377, pronto_para_revisao: 209 },
  limitacao: 'Documento baixado não é documento extraído.',
  itens: [
    {
      document_id: 'd1',
      contest_id: 'c1',
      title: 'Edital de abertura',
      official_url: 'https://www.gov.br/edital.pdf',
      tipo_documental: 'edital_abertura',
      kind: 'edital',
      issuer: 'FGV',
      source_identifier: 'fgv-1',
      stages: ['descoberto', 'baixado', 'validado', 'classificado', 'extraido'],
      versions: 1,
      extracted_versions: 1,
      blocks: 40,
      proposals: 12,
      association_state: null,
      contest_state: 'certame',
      blocked_at: 'pronto_para_revisao',
      blocked_reason: null,
      last_extraction_state: 'concluida',
      review_ready: true,
    },
    {
      document_id: 'd2',
      contest_id: 'c2',
      title: 'Anexo digitalizado',
      official_url: null,
      tipo_documental: 'anexo',
      kind: 'edital',
      issuer: 'IBFC',
      source_identifier: null,
      stages: ['descoberto', 'baixado'],
      versions: 1,
      extracted_versions: 0,
      blocks: 0,
      proposals: 0,
      association_state: null,
      contest_state: 'certame',
      blocked_at: 'sem_texto',
      blocked_reason: 'PDF sem camada de texto',
      last_extraction_state: 'falhou',
      review_ready: false,
    },
  ],
};

const coverage = {
  version: 'pipeline_v1',
  generated_at: '2026-10-29T00:00:00+00:00',
  concursos: 2,
  por_categoria: { texto_sem_campo: 1, documento_nao_extraido: 1 },
  itens: [],
  limitacao: 'Categorias são exclusivas.',
};

function renderPage() {
  const client = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  return render(
    <QueryClientProvider client={client}>
      <MemoryRouter>
        <PipelinePage />
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

function mockFetch() {
  const fetchMock = vi.fn(async (url: string) => {
    const body = url.startsWith('/api/pipeline/cobertura')
      ? coverage
      : url.startsWith('/api/pipeline/documentos')
        ? documents
        : summary;
    return new Response(JSON.stringify(body), {
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

describe('página de Pipeline', () => {
  it('mostra o funil principal com denominador explícito', async () => {
    mockFetch();
    renderPage();
    expect(await screen.findByText('Concursos com edital')).toBeInTheDocument();
    expect(screen.getByText(/de 830 concursos/)).toBeInTheDocument();
    expect(screen.getByText(/de 3.303 baixados/)).toBeInTheDocument();
    expect(screen.getByText(/0 campo\(s\) confirmado\(s\)/)).toBeInTheDocument();
  });

  it('lista documentos com o bloqueio e a trilha de etapas', async () => {
    mockFetch();
    renderPage();
    expect(await screen.findByText('Edital de abertura')).toBeInTheDocument();
    expect(screen.getByText('Anexo digitalizado')).toBeInTheDocument();
    expect(screen.getAllByText('Pronto para revisão').length).toBeGreaterThan(0);
    expect(screen.getAllByText('PDF sem camada de texto').length).toBeGreaterThan(0);
    // A trilha mostra a etapa que falta: o segundo documento parou em "baixado".
    const trails = screen.getAllByRole('list', { name: /etapas do documento/i });
    expect(trails).toHaveLength(2);
    expect(trails[1]).toHaveTextContent('extraido');
  });

  it('mostra a distribuição de bloqueios', async () => {
    mockFetch();
    renderPage();
    expect(await screen.findByText('Bloqueios')).toBeInTheDocument();
    expect(screen.getByText('Texto sem propostas')).toBeInTheDocument();
    expect(screen.getByText('Sem versão baixada')).toBeInTheDocument();
  });

  it('oferece link para o documento oficial quando existe URL', async () => {
    mockFetch();
    renderPage();
    const link = await screen.findByRole('link', { name: /abrir documento oficial/i });
    expect(link).toHaveAttribute('href', 'https://www.gov.br/edital.pdf');
    expect(link).toHaveAttribute('rel', expect.stringContaining('noopener'));
  });

  it('pede só documentos com bloqueio por padrão', async () => {
    const fetchMock = mockFetch();
    renderPage();
    await screen.findByText('Edital de abertura');
    const urls = fetchMock.mock.calls.map(([url]) => String(url));
    expect(urls.some((url) => url.includes('pending=1'))).toBe(true);

    fireEvent.click(screen.getByLabelText(/só com bloqueio/i));
    await screen.findByText('Edital de abertura');
    const depois = fetchMock.mock.calls.map(([url]) => String(url));
    expect(depois.some((url) => url.startsWith('/api/pipeline/documentos') && !url.includes('pending=1'))).toBe(true);
  });
});
