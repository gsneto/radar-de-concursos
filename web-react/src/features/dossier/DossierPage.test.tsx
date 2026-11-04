import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { fireEvent, render, screen } from '@testing-library/react';
import { MemoryRouter, Route, Routes } from 'react-router-dom';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { DossierPage } from './DossierPage';

function renderPage(initialEntry = '/dossie/c-tjpe') {
  const client = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  return render(
    <QueryClientProvider client={client}>
      <MemoryRouter initialEntries={[initialEntry]}>
        <Routes>
          <Route path="/dossie/:contestId" element={<DossierPage />} />
        </Routes>
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

const sampleDossier = {
  version: 'portfolio_dossier_v1',
  generated_at: '2026-11-04T12:00:00Z',
  identificacao: {
    contest_id: 'c-tjpe',
    competition_id: 'tjpe26',
    contest_label: 'TJ-PE 2026',
    contest_title: 'Tribunal de Justiça de Pernambuco',
    role_id: 'r-1',
    role_name: 'Analista Judiciário - Sistemas de Informação',
    scope: 'role:r-1',
    documentos: 3,
    edital_principal: {
      document_id: 'doc-1',
      title: 'Edital de Abertura TJ-PE 01/2026',
      tipo: 'edital_abertura',
      issuer: 'FGV',
      official_url: 'https://conhecimento.fgv.br/sites/default/files/concursos/edital-tjpe.pdf',
      versoes: 1,
      paginas_extraidas: 40,
    },
  },
  prontidao: {
    estado: 'candidatos_prontos_para_revisao',
    estado_label: 'Pronto para revisão',
    motivos: ['Propostas com evidência literal extraídas'],
  },
  proxima_acao: 'Revisar propostas candidatas na Mesa de Revisão',
  vagas: {
    total_publicado: { estado: 'candidato', valores: ['10'], propostas: [] },
    imediatas: { estado: 'candidato', valores: ['8'], propostas: [] },
    reserva: { estado: 'candidato', valores: ['CR'], propostas: [] },
    indigenas: {
      estado: 'explicito_imediato',
      ambito: 'cargo',
      imediatas: { estado: 'candidato', valores: ['2'], propostas: [] },
      reserva: { estado: 'nao_extraido', valores: [], propostas: [] },
    },
  },
  formacao: {
    escolaridade: { estado: 'candidato', valores: ['Superior completo'], propostas: [] },
    cursos_aceitos: { estado: 'candidato', valores: ['Sistemas de Informação'], propostas: [] },
    compatibilidade_si: {
      estado: 'explicito',
      motivo: 'Menciona expressamente Bacharelado em Sistemas de Informação',
      propostas: [],
    },
  },
  prazos: [
    {
      contest_id: 'c-tjpe',
      grupo: 'inscricao_fim',
      grupo_label: 'Fim das inscrições',
      valor: '2026-11-20',
      dias_restantes: 16,
      urgencia: 'ate_30_dias',
      urgencia_label: 'Em até 30 dias',
      estado_temporal: 'futuro',
      estado_operacional: 'revalidado_na_fonte',
      estado_operacional_label: 'Revalidado na fonte',
      documento: 'Edital de Abertura TJ-PE 01/2026',
      pagina: 5,
    },
  ],
  localizacao: {
    prova: { text: 'Recife/PE', uf: 'PE', state: 'extraido_nao_revisado', proposals: [] },
    lotacao: { text: 'Recife/PE', uf: 'PE', state: 'extraido_nao_revisado', proposals: [] },
    abrangencia: { text: 'Estadual (PE)', state: 'extraido_nao_revisado' },
  },
  lacunas: ['Confirmação humana pendente para vagas imediatas'],
  conflitos: { oportunidade: [], concurso: [] },
};

beforeEach(() => {
  vi.unstubAllGlobals();
});

describe('DossierPage', () => {
  it('renderiza cabeçalho, abas acessíveis e permite navegar entre seções do dossiê', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn(async (url: string) => {
        if (url.startsWith('/api/carteira/dossie')) {
          return new Response(JSON.stringify(sampleDossier), {
            status: 200,
            headers: { 'Content-Type': 'application/json' },
          });
        }
        if (url.includes('/detalhes')) {
          return new Response(
            JSON.stringify({
              contest_id: 'c-tjpe',
              documents: [],
              proposals: [],
            }),
            { status: 200, headers: { 'Content-Type': 'application/json' } },
          );
        }
        return new Response('{}', { status: 200 });
      }),
    );

    renderPage();

    expect(await screen.findByRole('heading', { name: 'TJ-PE 2026' })).toBeInTheDocument();
    expect(screen.getByText('Analista Judiciário - Sistemas de Informação')).toBeInTheDocument();
    expect(screen.getByRole('tablist', { name: 'Seções do dossiê' })).toBeInTheDocument();
    expect(screen.getByText('Revisar propostas candidatas na Mesa de Revisão')).toBeInTheDocument();

    // Navegar para a aba Prazos
    const prazosTab = screen.getByRole('tab', { name: 'Prazos' });
    fireEvent.click(prazosTab);
    expect(prazosTab).toHaveAttribute('aria-selected', 'true');
    expect(screen.getAllByText('Fim das inscrições').length).toBeGreaterThan(0);
  });

  it('exibe estado de erro quando o dossiê não é encontrado', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn(async () =>
        new Response(JSON.stringify({ error: 'Concurso inexistente' }), {
          status: 404,
          headers: { 'Content-Type': 'application/json' },
        }),
      ),
    );

    renderPage('/dossie/inexistente');

    expect(await screen.findByText('Dossiê indisponível')).toBeInTheDocument();
  });
});
