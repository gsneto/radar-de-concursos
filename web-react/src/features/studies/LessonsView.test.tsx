import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { render, screen } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { BancaRadiographyView } from './BancaRadiographyView';
import { LessonsView } from './LessonsView';

function renderWithClient(ui: React.ReactElement, initialEntries = ['/']) {
  const client = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  return render(
    <QueryClientProvider client={client}>
      <MemoryRouter initialEntries={initialEntries}>{ui}</MemoryRouter>
    </QueryClientProvider>
  );
}

beforeEach(() => {
  vi.unstubAllGlobals();
});

describe('LessonsView', () => {
  it('renderiza o plano de aulas com objetivos e questões associadas', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn(async (url: string) => {
        if (url.includes('/api/estudos/aulas')) {
          return new Response(
            JSON.stringify({
              aulas: [
                {
                  id: 'bd-01',
                  disciplina: 'Banco de Dados',
                  titulo: 'Aula 01: Modelagem Conceitual e Formas Normais',
                  objetivos: ['Compreender 1FN, 2FN e 3FN'],
                  questoes_count: 3,
                },
              ],
            }),
            { status: 200, headers: { 'Content-Type': 'application/json' } }
          );
        }
        if (url.includes('/api/estudos/questoes')) {
          return new Response(JSON.stringify([]), {
            status: 200,
            headers: { 'Content-Type': 'application/json' },
          });
        }
        return new Response('{}', { status: 200 });
      })
    );

    renderWithClient(<LessonsView />);

    expect(await screen.findByText(/Ambiente Completo de Ensino/i)).toBeInTheDocument();
    expect(await screen.findByText('Aula 01: Modelagem Conceitual e Formas Normais')).toBeInTheDocument();
    expect(screen.getByText('3 questões')).toBeInTheDocument();
  });

  it('renderiza os detalhes pedagógicos da aula quando aula selecionada via parâmetro', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn(async (url: string) => {
        if (url.includes('/api/estudos/aulas/bd-01')) {
          return new Response(
            JSON.stringify({
              aula: {
                id: 'bd-01',
                disciplina: 'Banco de Dados',
                titulo: 'Aula 01: Modelagem Conceitual e Formas Normais',
                objetivos: ['Compreender 1FN, 2FN e 3FN'],
                conteudo_resumo: 'A normalização de dados elimina anomalias.',
                pontos_criticos: ['Pegadinha da FGV sobre transitividade'],
                bancas_destaque: {
                  fgv: 'Cobra dependência funcional em tabelas com chaves compostas.',
                },
                tabela_resumo: {
                  titulo: 'Comparativo de Formas Normais',
                  colunas: ['Forma', 'Regra'],
                  linhas: [['1FN', 'Valores atômicos']],
                },
                videoaulas: [
                  {
                    titulo: 'Normalização Completa',
                    canal: 'Canal Concursos TI',
                    duracao: '32 min',
                    youtube_id: 'sample_id',
                    resumo: 'Aula completa de normalização.',
                  },
                ],
                flashcards: [
                  {
                    id: 'fc-1',
                    frente: 'O que exige a 1FN?',
                    verso: 'Apenas valores atômicos indivisíveis.',
                    mnemonico: '1FN = Átomo único',
                    tag: 'Normalização',
                  },
                ],
                questoes_count: 1,
              },
            }),
            { status: 200, headers: { 'Content-Type': 'application/json' } }
          );
        }
        if (url.includes('/api/estudos/aulas')) {
          return new Response(
            JSON.stringify({
              aulas: [
                {
                  id: 'bd-01',
                  disciplina: 'Banco de Dados',
                  titulo: 'Aula 01: Modelagem Conceitual e Formas Normais',
                  objetivos: ['Compreender 1FN, 2FN e 3FN'],
                  questoes_count: 1,
                },
              ],
            }),
            { status: 200, headers: { 'Content-Type': 'application/json' } }
          );
        }
        if (url.includes('/api/estudos/questoes')) {
          return new Response(JSON.stringify([]), {
            status: 200,
            headers: { 'Content-Type': 'application/json' },
          });
        }
        return new Response('{}', { status: 200 });
      })
    );

    renderWithClient(<LessonsView />, ['/?aula=bd-01']);

    expect(await screen.findByText('Aula 01: Modelagem Conceitual e Formas Normais')).toBeInTheDocument();
    expect(await screen.findByText('Comparativo de Formas Normais')).toBeInTheDocument();
    expect(screen.getByText('Valores atômicos')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /Videoaula/i })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /Flashcards/i })).toBeInTheDocument();
  });
});

describe('BancaRadiographyView', () => {
  it('exibe perfil analítico comparativo e regras de pontuação', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn(async (url: string) => {
        if (url.includes('/api/estudos/bancas')) {
          return new Response(
            JSON.stringify({
              bancas: {
                fgv: {
                  id: 'fgv',
                  nome: 'Fundação Getulio Vargas (FGV)',
                  estilo_predominante: 'Múltipla Escolha (5 alternativas A-E)',
                  regras_pontuacao: '1 ponto por acerto, sem penalidade por erro',
                  caracteristicas: ['Enunciados longos em casos práticos.'],
                  dicas_ti: ['Atenção para ACID e microsserviços.'],
                  dicas_gerais: ['Gerencie o tempo de prova.'],
                  palavras_chave_alerta: ['exclusivamente', 'sempre'],
                },
                cebraspe: {
                  id: 'cebraspe',
                  nome: 'Cebraspe (Cespe)',
                  estilo_predominante: 'Certo ou Errado',
                  regras_pontuacao: 'Uma resposta errada anula uma certa',
                  caracteristicas: ['Assertivas individuais.'],
                  dicas_ti: ['Decore definições literais de RFCs.'],
                  dicas_gerais: ['Deixe em branco na dúvida.'],
                  palavras_chave_alerta: ['vedado', 'independe'],
                },
              },
            }),
            { status: 200, headers: { 'Content-Type': 'application/json' } }
          );
        }
        return new Response('{}', { status: 200 });
      })
    );

    renderWithClient(<BancaRadiographyView />);

    expect(await screen.findByText(/Radiografia Comparativa de Bancas/i)).toBeInTheDocument();
    expect(await screen.findByText('Fundação Getulio Vargas (FGV)')).toBeInTheDocument();
    expect(screen.getByText(/1 ponto por acerto/i)).toBeInTheDocument();
    expect(screen.getByText('exclusivamente')).toBeInTheDocument();
  });
});
