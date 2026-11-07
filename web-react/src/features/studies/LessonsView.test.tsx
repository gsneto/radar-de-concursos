import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { render, screen } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { BancaRadiographyView } from './BancaRadiographyView';
import { LessonsView } from './LessonsView';

function renderWithClient(ui: React.ReactElement) {
  const client = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  return render(<QueryClientProvider client={client}>{ui}</QueryClientProvider>);
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

    expect(await screen.findByText(/Plano de Aulas Estruturado/i)).toBeInTheDocument();
    expect(await screen.findByText('Aula 01: Modelagem Conceitual e Formas Normais')).toBeInTheDocument();
    expect(screen.getByText('3 questões reais')).toBeInTheDocument();
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
