import { useState, useMemo, useEffect } from 'react';
import { useNavigate, useSearchParams } from 'react-router-dom';
import {
  Award,
  Calendar,
  CheckCircle2,
  Circle,
  Clock,
  Compass,
  Download,
  Play,
  Printer,
  RotateCcw,
  ShieldAlert,
  Trophy,
  Zap,
} from 'lucide-react';
import { useBancas, useMyContests } from '@/app/queries';
import { Button } from '@/components/ui/button';

export interface StudyBlock {
  id: string;
  disciplina: string;
  topico: string;
  duracaoMin: number;
  tipo: 'teoria' | 'questoes' | 'revisao' | 'simulado';
  dicaBanca?: string;
  actionHref?: string;
}

export interface DaySchedule {
  dayId: number; // 0 = Domingo, 1 = Segunda, ..., 6 = Sábado
  nome: string;
  subtitulo: string;
  isToday: boolean;
  metaMinutos: number;
  blocos: StudyBlock[];
}

const DIAS_SEMANA = [
  { id: 1, nome: 'Segunda-feira', short: 'Seg', subtitulo: 'Núcleo Duro de TI & Interpretação Textual' },
  { id: 2, nome: 'Terça-feira', short: 'Ter', subtitulo: 'Banco de Dados, Modelagem & Legislação' },
  { id: 3, nome: 'Quarta-feira', short: 'Qua', subtitulo: 'Redes, DevOps & Governança / LGPD' },
  { id: 4, nome: 'Quinta-feira', short: 'Qui', subtitulo: 'Segurança da Informação & Raciocínio Lógico' },
  { id: 5, nome: 'Sexta-feira', short: 'Sex', subtitulo: 'Arquitetura de Sistemas & Direito Administrativo' },
  { id: 6, nome: 'Sábado', short: 'Sáb', subtitulo: 'Simulado Realista da Banca & Raio-X de Erros' },
  { id: 0, nome: 'Domingo', short: 'Dom', subtitulo: 'Revisão Espaçada Ativa (Flashcards) & Planejamento' },
];

export function StudyScheduleView() {
  const navigate = useNavigate();
  const [searchParams] = useSearchParams();
  const contestParam = searchParams.get('concurso');

  const { data: myContestsData } = useMyContests();
  const { data: bancasData } = useBancas();

  const myContests = myContestsData?.itens ?? [];

  // Concurso selecionado para base do cronograma
  const [selectedContestId, setSelectedContestId] = useState<string>('');

  useEffect(() => {
    if (contestParam) {
      setSelectedContestId(contestParam);
    } else if (myContests.length > 0 && !selectedContestId) {
      setSelectedContestId(myContests[0].contest_id);
    }
  }, [contestParam, myContests, selectedContestId]);

  // Preferências do ciclo
  const [hoursPreset, setHoursPreset] = useState<number>(20);

  // Estado dos blocos concluídos (persistido no localStorage)
  const [completedBlocks, setCompletedBlocks] = useState<Record<string, boolean>>(() => {
    try {
      const stored = localStorage.getItem('radar_weekly_study_schedule_completed');
      return stored ? JSON.parse(stored) : {};
    } catch {
      return {};
    }
  });

  const toggleBlock = (blockId: string) => {
    setCompletedBlocks((prev) => {
      const updated = { ...prev, [blockId]: !prev[blockId] };
      try {
        localStorage.setItem('radar_weekly_study_schedule_completed', JSON.stringify(updated));
      } catch {
        // ignore storage errors
      }
      return updated;
    });
  };

  const resetWeek = () => {
    if (window.confirm('Deseja zerar as marcações desta semana e iniciar um novo ciclo?')) {
      setCompletedBlocks({});
      try {
        localStorage.removeItem('radar_weekly_study_schedule_completed');
      } catch {
        // ignore
      }
    }
  };

  // Identificação do concurso e banca ativos
  const activeContest = useMemo(() => {
    return myContests.find((c) => c.contest_id === selectedContestId) ?? myContests[0] ?? null;
  }, [myContests, selectedContestId]);

  const activeBanca = useMemo(() => {
    const rawBanca = (activeContest?.banca || '').toLowerCase();
    const bancas = bancasData?.bancas ?? {};
    if (rawBanca.includes('fgv') || rawBanca.includes('getulio')) return bancas['fgv'];
    if (rawBanca.includes('cebraspe') || rawBanca.includes('cespe')) return bancas['cebraspe'];
    if (rawBanca.includes('fcc') || rawBanca.includes('chagas')) return bancas['fcc'];
    if (rawBanca.includes('cesgranrio')) return bancas['cesgranrio'];
    if (rawBanca.includes('vunesp')) return bancas['vunesp'];
    if (rawBanca.includes('quadrix')) return bancas['quadrix'];
    return bancas['fgv'] || null;
  }, [activeContest, bancasData]);

  // Geração da Grade Semanal
  const todayDayIndex = new Date().getDay();

  const schedule: DaySchedule[] = useMemo(() => {
    const multiplier = hoursPreset / 20; // fator de escala conforme a carga horária
    const bancaNome = activeBanca?.nome || activeContest?.banca || 'Banca Oficial';
    const isFGV = (bancaNome || '').toLowerCase().includes('fgv');
    const isCebraspe = (bancaNome || '').toLowerCase().includes('cebraspe');

    const m = (minutosBase: number) => Math.round(minutosBase * multiplier);

    return DIAS_SEMANA.map((dia) => {
      let blocos: StudyBlock[] = [];

      switch (dia.id) {
        case 1: // Segunda
          blocos = [
            {
              id: 'seg-1',
              disciplina: 'Engenharia de Software & Programação',
              topico: 'Padrões de Projeto (GoF) e Arquitetura Limpa',
              duracaoMin: m(90),
              tipo: 'teoria',
              dicaBanca: isFGV
                ? 'FGV: Foque na intenção prática dos padrões em cenários de negócio, não na decoreba.'
                : 'Priorize Factory, Strategy e Singleton.',
              actionHref: '/estudos/sessoes',
            },
            {
              id: 'seg-2',
              disciplina: 'Língua Portuguesa',
              topico: isFGV ? 'Interpretação Textual, Semântica & Reescrita' : 'Sintaxe da Oração e Concordância',
              duracaoMin: m(60),
              tipo: 'questoes',
              dicaBanca: isFGV
                ? 'FGV é a banca mais imprevisível em português: resolva questões buscando a nuance do autor.'
                : 'Atenção às regras de crase e regência verbal.',
              actionHref: '/estudos/questoes',
            },
            {
              id: 'seg-3',
              disciplina: 'Revisão Espaçada',
              topico: '15 Flashcards do Dia (Eng. Software + Português)',
              duracaoMin: m(30),
              tipo: 'revisao',
              actionHref: '/estudos/flashcards',
            },
          ];
          break;

        case 2: // Terça
          blocos = [
            {
              id: 'ter-1',
              disciplina: 'Banco de Dados',
              topico: 'Modelagem Relacional, SQL Avançado & Transações ACID',
              duracaoMin: m(90),
              tipo: 'teoria',
              dicaBanca: isCebraspe
                ? 'Cebraspe adora itens sobre níveis de isolamento de transações (Dirty Read, Phantom Read).'
                : 'Treine subconsultas complexas e JOINs múltiplos.',
              actionHref: '/estudos/sessoes',
            },
            {
              id: 'ter-2',
              disciplina: 'Legislação & Normas',
              topico: activeContest?.orgao
                ? `Regimento Interno e Normas: ${activeContest.orgao}`
                : 'Estatuto dos Servidores Públicos (Lei 8.112)',
              duracaoMin: m(60),
              tipo: 'questoes',
              dicaBanca: 'Leitura atenta dos artigos mais cobrados e resolução de bateria de questões.',
              actionHref: '/estudos/questoes',
            },
            {
              id: 'ter-3',
              disciplina: 'Flashcards Diários',
              topico: 'Fixação de Comandos SQL e Artigos de Lei',
              duracaoMin: m(30),
              tipo: 'revisao',
              actionHref: '/estudos/flashcards',
            },
          ];
          break;

        case 3: // Quarta
          blocos = [
            {
              id: 'qua-1',
              disciplina: 'Redes & Infraestrutura Cloud',
              topico: 'Modelo OSI/TCP-IP, Roteamento e Práticas DevOps/Docker',
              duracaoMin: m(90),
              tipo: 'teoria',
              dicaBanca: 'Domine o fluxo do handshake TCP de 3 vias e portas padrão dos principais serviços.',
              actionHref: '/estudos/sessoes',
            },
            {
              id: 'qua-2',
              disciplina: 'Governança de TI & LGPD',
              topico: 'ITIL v4, COBIT 2019 e Princípios da LGPD (Lei 13.709)',
              duracaoMin: m(60),
              tipo: 'questoes',
              dicaBanca: 'Foque nos papéis da LGPD (Controlador, Operador, Encarregado/DPO) e bases legais.',
              actionHref: '/estudos/questoes',
            },
            {
              id: 'qua-3',
              disciplina: 'Caderno de Erros',
              topico: 'Revisão das 10 questões erradas nos últimos 2 dias',
              duracaoMin: m(30),
              tipo: 'revisao',
              actionHref: '/estudos/questoes',
            },
          ];
          break;

        case 4: // Quinta
          blocos = [
            {
              id: 'qui-1',
              disciplina: 'Segurança da Informação',
              topico: 'Criptografia Simétrica/Assimétrica, Hash e OWASP Top 10',
              duracaoMin: m(90),
              tipo: 'teoria',
              dicaBanca: isCebraspe
                ? 'Cebraspe frequentemente inverte definições de chave pública e privada na assinatura digital.'
                : 'Entenda a diferença entre Injeção de SQL e Cross-Site Scripting (XSS).',
              actionHref: '/estudos/sessoes',
            },
            {
              id: 'qui-2',
              disciplina: 'Raciocínio Lógico & Matemática',
              topico: 'Lógica Proposicional, Equivalências e Probabilidade',
              duracaoMin: m(60),
              tipo: 'questoes',
              dicaBanca: 'Tabelas-verdade, Leis de De Morgan e diagramas de Venn.',
              actionHref: '/estudos/questoes',
            },
            {
              id: 'qui-3',
              disciplina: 'Flashcards de Segurança',
              topico: 'Algoritmos de Cifra (AES, RSA, SHA-256) & Protocolos',
              duracaoMin: m(30),
              tipo: 'revisao',
              actionHref: '/estudos/flashcards',
            },
          ];
          break;

        case 5: // Sexta
          blocos = [
            {
              id: 'sex-1',
              disciplina: 'Arquitetura de Microsserviços & APIs',
              topico: 'RESTful, GraphQL, Mensageria (Kafka/RabbitMQ) e CI/CD',
              duracaoMin: m(90),
              tipo: 'teoria',
              dicaBanca: isFGV
                ? 'FGV exige entendimento prático de tolerância a falhas (Circuit Breaker) e escalabilidade.'
                : 'Foque nos verbos HTTP e códigos de status (200, 201, 400, 401, 403, 500).',
              actionHref: '/estudos/sessoes',
            },
            {
              id: 'sex-2',
              disciplina: 'Direito Administrativo',
              topico: 'Nova Lei de Licitações (Lei 14.133/21) & Atos Administrativos',
              duracaoMin: m(60),
              tipo: 'questoes',
              dicaBanca: 'Modalidades de licitação e critérios de julgamento da Lei 14.133.',
              actionHref: '/estudos/questoes',
            },
            {
              id: 'sex-3',
              disciplina: 'Alinhamento Semanal',
              topico: 'Planejamento das matérias do Simulado de Sábado',
              duracaoMin: m(30),
              tipo: 'revisao',
              actionHref: '/estudos/simulados',
            },
          ];
          break;

        case 6: // Sábado
          blocos = [
            {
              id: 'sab-1',
              disciplina: `Simulado Oficial ${bancaNome}`,
              topico: '50 Questões Cronometradas com Regra de Prova Real',
              duracaoMin: m(150),
              tipo: 'simulado',
              dicaBanca: isCebraspe
                ? 'Simulado C/E: Treine deixar em branco questões que gerem dúvida irreversível para evitar penalidade.'
                : 'Gerencie o tempo: 3 minutos por questão no máximo.',
              actionHref: '/estudos/simulados',
            },
            {
              id: 'sab-2',
              disciplina: 'Raio-X do Simulado & Pegadinhas',
              topico: 'Análise minuciosa de cada questão errada e anotação no caderno de erros',
              duracaoMin: m(60),
              tipo: 'questoes',
              dicaBanca: 'Identifique se o erro foi por falta de teoria, distração ou pegadinha da banca.',
              actionHref: '/estudos/questoes',
            },
          ];
          break;

        case 0: // Domingo
          blocos = [
            {
              id: 'dom-1',
              disciplina: 'Revisão Espaçada Completa (SM-2)',
              topico: 'Limpeza de todos os flashcards pendentes da semana',
              duracaoMin: m(45),
              tipo: 'revisao',
              dicaBanca: 'Revisão ativa é comprovadamente 3x mais eficiente que re-leitura passiva.',
              actionHref: '/estudos/flashcards',
            },
            {
              id: 'dom-2',
              disciplina: 'Planejamento & Descanso Ativo',
              topico: 'Metas da próxima semana, hidratação e descanso cognitivo',
              duracaoMin: m(15),
              tipo: 'revisao',
              dicaBanca: 'O sono consolida a memória de longo prazo aprendida na semana.',
              actionHref: '/estudos',
            },
          ];
          break;
      }

      const totalMin = blocos.reduce((acc, b) => acc + b.duracaoMin, 0);

      return {
        dayId: dia.id,
        nome: dia.nome,
        subtitulo: dia.subtitulo,
        isToday: dia.id === todayDayIndex,
        metaMinutos: totalMin,
        blocos,
      };
    });
  }, [hoursPreset, activeBanca, activeContest, todayDayIndex]);

  // Cálculos de progresso da semana
  const stats = useMemo(() => {
    let totalBlocos = 0;
    let blocosConcluidos = 0;
    let totalMinutos = 0;
    let minutosConcluidos = 0;

    schedule.forEach((dia) => {
      dia.blocos.forEach((bloco) => {
        totalBlocos++;
        totalMinutos += bloco.duracaoMin;
        if (completedBlocks[bloco.id]) {
          blocosConcluidos++;
          minutosConcluidos += bloco.duracaoMin;
        }
      });
    });

    const percentual = totalMinutos > 0 ? Math.round((minutosConcluidos / totalMinutos) * 100) : 0;
    const horasConcluidas = (minutosConcluidos / 60).toFixed(1);
    const horasTotais = (totalMinutos / 60).toFixed(0);

    return {
      totalBlocos,
      blocosConcluidos,
      minutosConcluidos,
      totalMinutos,
      percentual,
      horasConcluidas,
      horasTotais,
    };
  }, [schedule, completedBlocks]);

  // Exportar Calendário .ICS para Google Agenda / Apple Calendar
  const handleExportICS = () => {
    const calendarEvents: string[] = [];

    schedule.forEach((dia) => {
      dia.blocos.forEach((bloco) => {
        calendarEvents.push(`BEGIN:VEVENT
SUMMARY:Estudo: ${bloco.disciplina} (${bloco.topico})
DESCRIPTION:${bloco.dicaBanca || 'Bloco de estudo gerado pelo Radar de Concursos'}
TRIGGER:-PT15M
DURATION:PT${bloco.duracaoMin}M
END:VEVENT`);
      });
    });

    const icsContent = `BEGIN:VCALENDAR
VERSION:2.0
PRODID:-//Radar de Concursos//Ciclo Semanal Inteligente//PT
CALSCALE:GREGORIAN
METHOD:PUBLISH
X-WR-CALNAME:Ciclo de Estudos - ${activeContest?.orgao || 'Radar de Concursos'}
${calendarEvents.join('\n')}
END:VCALENDAR`;

    const blob = new Blob([icsContent], { type: 'text/calendar;charset=utf-8' });
    const url = URL.createObjectURL(blob);
    const link = document.createElement('a');
    link.href = url;
    link.setAttribute('download', `ciclo-estudos-${activeContest?.competition_id || 'semana'}.ics`);
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
  };

  const handlePrint = () => {
    window.print();
  };

  return (
    <div className="space-y-6">
      {/* Banner Principal / Configuração do Ciclo */}
      <div className="relative overflow-hidden rounded-2xl border border-line bg-gradient-to-br from-surface-2/90 via-surface to-surface-2 p-5 sm:p-6 shadow-xl">
        <div className="flex flex-col lg:flex-row lg:items-center justify-between gap-5">
          <div className="space-y-2">
            <div className="flex flex-wrap items-center gap-2">
              <span className="inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded-full text-xs font-semibold bg-amber-400/15 text-amber-400 border border-amber-400/30">
                <Compass size={13} />
                Ciclo de Estudos Automatizado
              </span>
              {activeBanca && (
                <span className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-xs font-medium bg-surface-2 border border-line text-fg-2">
                  <Award size={12} className="text-amber-400" />
                  Calibrado para {activeBanca.nome}
                </span>
              )}
            </div>

            <h2 className="text-xl sm:text-2xl font-bold tracking-tight text-fg">
              Grade Semanal de Estudos Recomendada
            </h2>

            <p className="text-xs sm:text-sm text-fg-3 max-w-2xl leading-relaxed">
              Ciclo intercalado baseado em neurociência e nas disciplinas de maior incidência da banca{' '}
              <strong className="text-fg">{activeBanca?.nome || 'examinadora'}</strong>. Alterne matérias de raciocínio lógico e TI com leitura jurídica e revisão ativa.
            </p>
          </div>

          {/* Seletores de Concurso & Carga Horária */}
          <div className="flex flex-col sm:flex-row items-stretch sm:items-center gap-3 shrink-0">
            {myContests.length > 0 && (
              <div className="flex flex-col gap-1">
                <label className="text-[10px] font-semibold text-fg-3 uppercase tracking-wider">
                  Concurso Alvo (Foco)
                </label>
                <select
                  value={selectedContestId}
                  onChange={(e) => setSelectedContestId(e.target.value)}
                  className="h-9 rounded-lg border border-line bg-surface-2 px-3 text-xs text-fg font-medium focus:border-amber-400 focus:outline-none"
                >
                  {myContests.map((c) => (
                    <option key={c.contest_id} value={c.contest_id}>
                      {c.orgao || c.contest_label} ({c.banca || 'Banca'})
                    </option>
                  ))}
                </select>
              </div>
            )}

            <div className="flex flex-col gap-1">
              <label className="text-[10px] font-semibold text-fg-3 uppercase tracking-wider">
                Meta Semanal
              </label>
              <div className="flex rounded-lg border border-line bg-surface-2 p-0.5">
                {[15, 20, 30, 40].map((h) => (
                  <button
                    key={h}
                    type="button"
                    onClick={() => setHoursPreset(h)}
                    className={`px-2.5 py-1 text-xs font-semibold rounded-md transition-all ${
                      hoursPreset === h
                        ? 'bg-amber-400 text-slate-950 shadow-xs'
                        : 'text-fg-3 hover:text-fg'
                    }`}
                  >
                    {h}h
                  </button>
                ))}
              </div>
            </div>
          </div>
        </div>

        {/* Alerta de Inteligência da Banca */}
        {activeBanca && (
          <div className="mt-5 rounded-xl border border-amber-400/20 bg-amber-400/5 p-3.5 flex items-start gap-3 text-xs">
            <ShieldAlert size={16} className="text-amber-400 shrink-0 mt-0.5" />
            <div className="space-y-0.5">
              <span className="font-semibold text-fg">Diretriz da Banca ({activeBanca.nome}):</span>{' '}
              <span className="text-fg-3">
                {activeBanca.estilo_predominante ||
                  'Foco em enunciados contextualizados e resolução de problemas práticos. O cronograma já reserva tempo dedicado para resolução de bateria de questões reais.'}
              </span>
            </div>
          </div>
        )}
      </div>

      {/* Barra de Progresso Semanal & Ações de Conversão */}
      <div className="grid grid-cols-1 md:grid-cols-4 gap-3.5">
        <div className="md:col-span-2 rounded-xl border border-line bg-surface p-4 flex flex-col justify-between">
          <div className="flex items-center justify-between gap-2 mb-2">
            <div className="flex items-center gap-2">
              <Trophy size={16} className="text-amber-400" />
              <span className="text-xs font-semibold text-fg">Cumprimento da Meta Semanal</span>
            </div>
            <span className="text-xs font-bold text-amber-400">{stats.percentual}%</span>
          </div>

          <div className="w-full bg-surface-2 rounded-full h-2.5 overflow-hidden border border-line/60">
            <div
              className="bg-gradient-to-r from-amber-500 to-amber-300 h-full rounded-full transition-all duration-500"
              style={{ width: `${stats.percentual}%` }}
            />
          </div>

          <div className="mt-2.5 flex items-center justify-between text-2xs text-fg-3">
            <span>
              {stats.horasConcluidas}h de {stats.horasTotais}h estudadas
            </span>
            <span>
              {stats.blocosConcluidos} de {stats.totalBlocos} blocos cumpridos
            </span>
          </div>
        </div>

        <div className="rounded-xl border border-line bg-surface p-4 flex flex-col justify-between">
          <div className="flex items-center gap-1.5 text-xs text-fg-3 mb-1">
            <Zap size={14} className="text-emerald-400" />
            <span>Fórmula de Estudo</span>
          </div>
          <div className="text-lg font-bold text-fg">70% TI · 30% Básicas</div>
          <p className="text-2xs text-fg-3 mt-1">Intercalação anti-fadiga com flashcards ao final de cada dia.</p>
        </div>

        <div className="rounded-xl border border-line bg-surface p-4 flex items-center justify-between gap-2">
          <div className="space-y-1">
            <span className="text-2xs font-semibold text-fg-3 uppercase tracking-wider block">Ferramentas</span>
            <div className="flex items-center gap-1.5">
              <Button
                variant="secondary"
                size="sm"
                onClick={handleExportICS}
                className="gap-1 text-xs"
                title="Adicionar horários ao Google Agenda ou Apple Calendar"
              >
                <Download size={13} />
                Agenda (.ics)
              </Button>
              <Button
                variant="ghost"
                size="sm"
                onClick={handlePrint}
                className="gap-1 text-xs"
                title="Imprimir grade para colar na mesa"
              >
                <Printer size={13} />
                Imprimir
              </Button>
              <Button
                variant="ghost"
                size="sm"
                onClick={resetWeek}
                className="p-1.5 text-fg-3 hover:text-rose-400"
                title="Zerar progresso da semana"
              >
                <RotateCcw size={13} />
              </Button>
            </div>
          </div>
        </div>
      </div>

      {/* Grade Semanal (Segunda a Domingo) */}
      <div className="space-y-4">
        <div className="flex items-center justify-between">
          <h3 className="text-base font-bold text-fg tracking-tight flex items-center gap-2">
            <Calendar size={18} className="text-amber-400" />
            Ciclo Diário de Estudos
          </h3>
          <span className="text-2xs text-fg-3">
            Clique no círculo para marcar o bloco como estudado
          </span>
        </div>

        <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
          {schedule.map((dia) => {
            const diaConcluido = dia.blocos.every((b) => completedBlocks[b.id]);
            const blocosFeitosNoDia = dia.blocos.filter((b) => completedBlocks[b.id]).length;

            return (
              <div
                key={dia.dayId}
                className={`rounded-2xl border transition-all duration-200 overflow-hidden ${
                  dia.isToday
                    ? 'border-amber-400/50 bg-surface shadow-lg ring-1 ring-amber-400/30'
                    : 'border-line/80 bg-surface/80 hover:border-line'
                }`}
              >
                {/* Cabeçalho do Dia */}
                <div
                  className={`p-3.5 sm:p-4 border-b flex items-center justify-between gap-3 ${
                    dia.isToday
                      ? 'bg-amber-400/10 border-amber-400/20'
                      : 'bg-surface-2/60 border-line/60'
                  }`}
                >
                  <div className="flex items-center gap-2.5 min-w-0">
                    <div
                      className={`h-8 w-8 rounded-lg flex items-center justify-center font-bold text-xs shrink-0 ${
                        dia.isToday
                          ? 'bg-amber-400 text-slate-950 font-black'
                          : 'bg-surface-2 border border-line text-fg'
                      }`}
                    >
                      {dia.nome.slice(0, 3)}
                    </div>
                    <div className="min-w-0">
                      <div className="flex items-center gap-2">
                        <span className="font-bold text-sm text-fg tracking-tight">{dia.nome}</span>
                        {dia.isToday && (
                          <span className="px-1.5 py-0.2 rounded-full text-[9px] font-black uppercase tracking-wider bg-amber-400 text-slate-950">
                            Hoje
                          </span>
                        )}
                        {diaConcluido && (
                          <span className="text-emerald-400 text-xs flex items-center gap-1 font-medium">
                            <CheckCircle2 size={13} /> 100%
                          </span>
                        )}
                      </div>
                      <p className="text-2xs text-fg-3 truncate">{dia.subtitulo}</p>
                    </div>
                  </div>

                  <div className="text-right shrink-0">
                    <span className="text-xs font-semibold text-fg">
                      {Math.floor(dia.metaMinutos / 60)}h{dia.metaMinutos % 60 ? `${dia.metaMinutos % 60}m` : ''}
                    </span>
                    <span className="text-[10px] text-fg-3 block">
                      {blocosFeitosNoDia}/{dia.blocos.length} feitos
                    </span>
                  </div>
                </div>

                {/* Lista de Blocos do Dia */}
                <div className="p-3 sm:p-4 space-y-2.5">
                  {dia.blocos.map((bloco) => {
                    const isDone = !!completedBlocks[bloco.id];

                    return (
                      <div
                        key={bloco.id}
                        className={`group rounded-xl border p-3 transition-all flex items-start gap-3 ${
                          isDone
                            ? 'bg-emerald-950/15 border-emerald-500/30 text-fg-3'
                            : 'bg-surface-2/40 border-line/60 hover:bg-surface-2/80 hover:border-line text-fg'
                        }`}
                      >
                        {/* Checkbox interativo */}
                        <button
                          type="button"
                          onClick={() => toggleBlock(bloco.id)}
                          aria-label={isDone ? 'Marcar como não concluído' : 'Marcar como concluído'}
                          className={`mt-0.5 shrink-0 transition-colors ${
                            isDone ? 'text-emerald-400' : 'text-fg-3 hover:text-amber-400'
                          }`}
                        >
                          {isDone ? <CheckCircle2 size={18} /> : <Circle size={18} />}
                        </button>

                        {/* Conteúdo do Bloco */}
                        <div className="min-w-0 flex-1 space-y-1">
                          <div className="flex flex-wrap items-center justify-between gap-1">
                            <div className="flex items-center gap-1.5 flex-wrap">
                              <span
                                className={`text-[10px] font-bold uppercase tracking-wider px-1.5 py-0.5 rounded-sm ${
                                  bloco.tipo === 'teoria'
                                    ? 'bg-blue-500/10 text-blue-400 border border-blue-500/20'
                                    : bloco.tipo === 'questoes'
                                    ? 'bg-emerald-500/10 text-emerald-400 border border-emerald-500/20'
                                    : bloco.tipo === 'simulado'
                                    ? 'bg-amber-500/15 text-amber-400 border border-amber-500/30'
                                    : 'bg-purple-500/10 text-purple-400 border border-purple-500/20'
                                }`}
                              >
                                {bloco.tipo}
                              </span>
                              <span className={`text-xs font-semibold ${isDone ? 'line-through text-fg-3' : 'text-fg'}`}>
                                {bloco.disciplina}
                              </span>
                            </div>

                            <span className="text-2xs font-mono font-medium text-fg-3 flex items-center gap-1">
                              <Clock size={11} />
                              {bloco.duracaoMin} min
                            </span>
                          </div>

                          <p className={`text-xs ${isDone ? 'text-fg-3 line-through' : 'text-fg-2 font-medium'}`}>
                            {bloco.topico}
                          </p>

                          {bloco.dicaBanca && !isDone && (
                            <p className="text-[11px] text-amber-400/90 bg-amber-400/5 px-2 py-1 rounded-md border border-amber-400/15 leading-relaxed">
                              💡 <strong>Banca:</strong> {bloco.dicaBanca}
                            </p>
                          )}
                        </div>

                        {/* Ação rápida para praticar */}
                        {bloco.actionHref && !isDone && (
                          <Button
                            variant="ghost"
                            size="sm"
                            onClick={() => navigate(bloco.actionHref!)}
                            className="shrink-0 p-1.5 text-xs text-fg-3 hover:text-amber-400"
                            title="Abrir ferramenta para estudar agora"
                          >
                            <Play size={13} />
                          </Button>
                        )}
                      </div>
                    );
                  })}
                </div>
              </div>
            );
          })}
        </div>
      </div>
    </div>
  );
}
