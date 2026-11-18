import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { fireEvent, render, screen } from '@testing-library/react';
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
  localStorage.clear();
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
    expect(screen.getAllByRole('button', { name: /Quadro Digital & Mapa Mental/i }).length).toBeGreaterThan(0);
    expect(screen.getAllByRole('button', { name: /Videoaula Recomendada/i }).length).toBeGreaterThan(0);
    expect(screen.getAllByRole('button', { name: /Flashcards Visuais/i }).length).toBeGreaterThan(0);
    expect(screen.getAllByRole('button', { name: /Avaliação de Domínio/i }).length).toBeGreaterThan(0);
    expect(screen.getAllByRole('button', { name: /Professor Virtual/i }).length).toBeGreaterThan(0);
  });

  it('navega pelas 5 etapas da aula e isola aulas concluídas na chave escopada radar:u:', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn(async (url: string) => {
        if (url.includes('/api/auth/me')) {
          return new Response(
            JSON.stringify({
              authenticated: true,
              user: {
                id: 'usr-ana-1',
                nome: 'Ana',
                email: 'ana@radar.dev',
                role: 'student',
                plan: 'free',
                status: 'active',
              },
            }),
            { status: 200, headers: { 'Content-Type': 'application/json' } }
          );
        }
        if (url.includes('/api/estudos/painel')) {
          return new Response(
            JSON.stringify({
              total_segundos: 0,
              semana_segundos: 0,
              sessoes_concluidas: 0,
              revisoes_pendentes: 0,
              disciplinas: 1,
              conteudo: { topics: { done: 0, total: 0, pct: 0 }, overall: { done: 0, total: 0, pct: 0 } },
              minutos_por_disciplina: [],
              revisoes: [],
              sessao_aberta: null,
            }),
            { status: 200, headers: { 'Content-Type': 'application/json' } }
          );
        }
        if (url.includes('/api/estudos/aulas/bd-01')) {
          return new Response(
            JSON.stringify({
              aula: {
                id: 'bd-01',
                disciplina: 'Banco de Dados',
                titulo: 'Aula 01: Modelagem Conceitual e Formas Normais',
                objetivos: ['Compreender 1FN, 2FN e 3FN'],
                teoria_resumida: '1FN: Valores atômicos indivisíveis.',
                pontos_criticos: ['Pegadinha da FGV sobre transitividade'],
                radiografia_bancas: { fgv: 'Cobra dependência funcional.' },
                quadro_visual: {
                  titulo: 'Quadro Esquematizado de Formas Normais',
                  relacoes_conceituais: [],
                },
                videoaulas: [
                  {
                    titulo: 'Normalização Completa',
                    canal: 'Canal Concursos TI',
                    duracao: '32 min',
                    youtube_id: 'sample_id',
                    resumo: 'Aula completa.',
                  },
                ],
                flashcards: [
                  {
                    id: 'fc-1',
                    frente: 'O que exige a 1FN?',
                    verso: 'Apenas valores atômicos.',
                    mnemonico: '1FN = Átomo',
                    tag: 'Normalização',
                  },
                ],
                questoes_detalhadas: [
                  {
                    id: 'q-1',
                    tipo: 'escolha_unica',
                    disciplina: 'Banco de Dados',
                    topico: 'Normalização',
                    dificuldade: 'media',
                    fonte: 'FGV 2024',
                    enunciado: 'Qual forma normal exige valores atômicos?',
                    gabarito: 'A',
                    comentario: '1FN elimina atributos multivalorados.',
                    alternativas_formatadas: [
                      { letra: 'A', texto: '1FN', correta: true, justificativa: 'Correta' },
                      { letra: 'B', texto: '2FN', correta: false, justificativa: 'Incorreta' },
                    ],
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
        return new Response('[]', { status: 200, headers: { 'Content-Type': 'application/json' } });
      })
    );

    renderWithClient(<LessonsView />, ['/?aula=bd-01']);

    const doneBtn = await screen.findByRole('button', { name: /Marcar Concluída/i });
    fireEvent.click(doneBtn);

    expect(localStorage.getItem('radar:u:usr-ana-1:completed_lessons')).toBe('["bd-01"]');
    expect(localStorage.getItem('radar_completed_lessons')).toBeNull();

    fireEvent.click(screen.getByRole('button', { name: /2\. Quadro Digital/i }));
    expect(screen.getByText('Quadro Esquematizado de Formas Normais')).toBeInTheDocument();

    fireEvent.click(screen.getByRole('button', { name: /3\. Videoaula Recomendada/i }));
    expect(screen.getByText(/Assista à aula em vídeo/i)).toBeInTheDocument();

    fireEvent.click(screen.getByRole('button', { name: /4\. Flashcards Visuais/i }));
    expect(screen.getByText(/Fichas de Memorização Visual da Aula/i)).toBeInTheDocument();

    fireEvent.click(screen.getByRole('button', { name: /5\. Questões & Avaliação de Domínio/i }));
    expect(screen.getByText(/Qual forma normal exige valores atômicos\?/i)).toBeInTheDocument();
  });

  it('inicia cronômetro parado em 00:00 (sem setInterval fantasma), aciona POST /api/estudos/sessoes ao clicar em Iniciar e valida modal acessível de Nova Aula', async () => {
    const sessionPosts: unknown[] = [];
    vi.stubGlobal(
      'fetch',
      vi.fn(async (url: string, init?: RequestInit) => {
        if (url.includes('/api/auth/me')) {
          return new Response(
            JSON.stringify({
              authenticated: true,
              user: { id: 'admin-1', nome: 'Admin', email: 'adm@radar.dev', role: 'admin', plan: 'founder', status: 'active' },
            }),
            { status: 200, headers: { 'Content-Type': 'application/json' } },
          );
        }
        if (url.includes('/api/estudos/sessoes') && init?.method === 'POST') {
          sessionPosts.push(JSON.parse(String(init.body)));
          return new Response(JSON.stringify({ ok: true }), {
            status: 200,
            headers: { 'Content-Type': 'application/json' },
          });
        }
        if (url.includes('/api/estudos/aulas') && init?.method === 'POST') {
          return new Response(JSON.stringify({ error: 'Falha ao publicar aula no banco' }), {
            status: 500,
            headers: { 'Content-Type': 'application/json' },
          });
        }
        if (url.includes('/api/estudos/painel')) {
          return new Response(
            JSON.stringify({
              total_segundos: 0,
              semana_segundos: 0,
              sessoes_concluidas: 0,
              revisoes_pendentes: 0,
              disciplinas: 1,
              conteudo: { topics: { done: 0, total: 0, pct: 0 }, overall: { done: 0, total: 0, pct: 0 } },
              minutos_por_disciplina: [],
              revisoes: [],
              sessao_aberta: null,
            }),
            { status: 200, headers: { 'Content-Type': 'application/json' } },
          );
        }
        if (url.includes('/api/estudos/aulas/bd-01')) {
          return new Response(
            JSON.stringify({
              aula: {
                id: 'bd-01',
                disciplina: 'Banco de Dados',
                titulo: 'Aula 01: Modelagem Conceitual',
                objetivos: ['Compreender 1FN'],
                teoria_resumida: '1FN: Valores atômicos.',
                pontos_criticos: [],
                radiografia_bancas: {},
                questoes_ids: [],
              },
            }),
            { status: 200, headers: { 'Content-Type': 'application/json' } },
          );
        }
        if (url.includes('/api/estudos/aulas')) {
          return new Response(
            JSON.stringify({
              aulas: [
                {
                  id: 'bd-01',
                  disciplina: 'Banco de Dados',
                  titulo: 'Aula 01: Modelagem Conceitual',
                  objetivos: ['Compreender 1FN'],
                  questoes_count: 0,
                },
              ],
            }),
            { status: 200, headers: { 'Content-Type': 'application/json' } },
          );
        }
        return new Response('[]', { status: 200, headers: { 'Content-Type': 'application/json' } });
      }),
    );

    localStorage.setItem('gsn.workspace_mode', 'admin');
    renderWithClient(<LessonsView />, ['/?aula=bd-01']);

    expect(await screen.findByText('Aula 01: Modelagem Conceitual')).toBeInTheDocument();
    const startBtn = screen.getByTitle('Iniciar sessão');
    expect(startBtn).toBeInTheDocument();
    expect(screen.getByText('00:00:00')).toBeInTheDocument();

    fireEvent.click(startBtn);
    expect(sessionPosts).toEqual([{ action: 'start', disciplina_id: null, modo: 'aula' }]);

    fireEvent.click(screen.getByRole('button', { name: /Voltar para Todas as Aulas/i }));
    const newLessonBtn = await screen.findByRole('button', { name: /Nova Aula/i });
    fireEvent.click(newLessonBtn);

    const titleInput = await screen.findByLabelText(/Título da Aula/i);
    fireEvent.change(titleInput, { target: { value: 'Aula Teste Radix' } });
    fireEvent.click(screen.getByRole('button', { name: /Publicar Aula/i }));

    expect(await screen.findByRole('alert')).toHaveTextContent(/Falha ao publicar aula no banco/i);
  });

  it('atualiza o contador de porcentagem por etapa (0% -> 20% -> 40%) e grava histórico do que o aluno fez', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn(async (url: string) => {
        if (url.includes('/api/auth/me')) {
          return new Response(
            JSON.stringify({
              authenticated: true,
              user: { id: 'usr-pct-1', nome: 'Carlos', email: 'c@radar.dev', role: 'student', plan: 'pro', status: 'active' },
            }),
            { status: 200, headers: { 'Content-Type': 'application/json' } },
          );
        }
        if (url.includes('/api/estudos/aulas/bd-01')) {
          return new Response(
            JSON.stringify({
              aula: {
                id: 'bd-01',
                disciplina: 'Banco de Dados',
                titulo: 'Aula 01: Modelagem Conceitual',
                objetivos: ['Compreender 1FN'],
                teoria_resumida: '1FN exige valores atômicos.',
                pontos_criticos: [],
                radiografia_bancas: {},
                quadro_visual: { titulo: 'Quadro 1FN', relacoes_conceituais: [] },
                videoaulas: [],
                flashcards: [],
                questoes_ids: [],
              },
            }),
            { status: 200, headers: { 'Content-Type': 'application/json' } },
          );
        }
        if (url.includes('/api/estudos/aulas')) {
          return new Response(
            JSON.stringify({
              aulas: [
                {
                  id: 'bd-01',
                  disciplina: 'Banco de Dados',
                  titulo: 'Aula 01: Modelagem Conceitual',
                  objetivos: ['Compreender 1FN'],
                  questoes_count: 0,
                },
              ],
            }),
            { status: 200, headers: { 'Content-Type': 'application/json' } },
          );
        }
        return new Response('[]', { status: 200, headers: { 'Content-Type': 'application/json' } });
      }),
    );

    renderWithClient(<LessonsView />, ['/?aula=bd-01']);

    expect(await screen.findByLabelText('Progresso das etapas da aula')).toHaveTextContent('0%');

    // Concluir Etapa 1 (Resumo & Teoria) -> sobe para 20%
    fireEvent.click(screen.getByRole('button', { name: /Concluir Etapa Atual/i }));
    expect(screen.getByLabelText('Progresso das etapas da aula')).toHaveTextContent('20%');

    // Ir para Etapa 2 e concluí-la -> sobe para 40%
    fireEvent.click(screen.getByRole('button', { name: /2\. Quadro Digital/i }));
    fireEvent.click(screen.getByRole('button', { name: /Concluir Etapa Atual/i }));
    expect(screen.getByLabelText('Progresso das etapas da aula')).toHaveTextContent('40%');

    // Verifica que o histórico de atividades do aluno registrou as 2 etapas
    const rawLog = localStorage.getItem('radar:u:usr-pct-1:student_activity_log');
    expect(rawLog).not.toBeNull();
    const parsedLog = JSON.parse(rawLog!);
    expect(parsedLog.length).toBeGreaterThanOrEqual(2);
    expect(parsedLog[0].pct).toBe(40);
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

  it('alterna para o Diretório Completo A–Z de organizadoras estilo PCI com filtro por letra e grupo', async () => {
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
                  estilo_predominante: 'Múltipla Escolha',
                  regras_pontuacao: '1 ponto por acerto',
                  caracteristicas: [],
                  dicas_ti: [],
                  dicas_gerais: [],
                  palavras_chave_alerta: [],
                },
              },
            }),
            { status: 200, headers: { 'Content-Type': 'application/json' } },
          );
        }
        if (url.includes('/api/organizadoras')) {
          return new Response(
            JSON.stringify({
              total: 3,
              letras: { A: 1, F: 1, Z: 1 },
              grupos: { nacional: 1, federal_if_uf: 0, regional_municipal: 2 },
              itens: [
                {
                  slug: 'a-s-instituto',
                  nome: 'A.S. Instituto',
                  letra: 'A',
                  grupo: 'regional_municipal',
                  grupo_label: 'Regional, Estadual & Municipal',
                  pci_url: 'https://www.pciconcursos.com.br/organizadoras/a-s-instituto',
                  tem_raio_x_ti: false,
                  raio_x_id: null,
                  concursos_count: 0,
                  provas_count: 0,
                  questoes_count: 0,
                },
                {
                  slug: 'fgv',
                  nome: 'FGV',
                  letra: 'F',
                  grupo: 'nacional',
                  grupo_label: 'Nacional & Grande Porte',
                  pci_url: 'https://www.pciconcursos.com.br/organizadoras/fgv',
                  tem_raio_x_ti: true,
                  raio_x_id: 'fgv',
                  concursos_count: 4,
                  provas_count: 5,
                  questoes_count: 12,
                },
                {
                  slug: 'zambini',
                  nome: 'Zambini',
                  letra: 'Z',
                  grupo: 'regional_municipal',
                  grupo_label: 'Regional, Estadual & Municipal',
                  pci_url: 'https://www.pciconcursos.com.br/organizadoras/zambini',
                  tem_raio_x_ti: false,
                  raio_x_id: null,
                  concursos_count: 0,
                  provas_count: 0,
                  questoes_count: 0,
                },
              ],
            }),
            { status: 200, headers: { 'Content-Type': 'application/json' } },
          );
        }
        return new Response('{}', { status: 200 });
      }),
    );

    renderWithClient(<BancaRadiographyView />);

    const dirTab = await screen.findByRole('button', { name: /Diretório Completo A–Z/i });
    fireEvent.click(dirTab);

    expect(await screen.findByText('A.S. Instituto')).toBeInTheDocument();
    expect(screen.getByText('Zambini')).toBeInTheDocument();
    expect(screen.getByText(/5 provas/i)).toBeInTheDocument();
  });
});
