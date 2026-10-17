# Fase 21 - Plataforma de estudos integrada ao Radar

Data: 2026-10-16. Base: `dc1eb6c` (Fase 20), 704 testes OK.

## Objetivo

Evoluir o Radar para uma plataforma que também apoia a **rotina de estudos**: disciplinas e
tópicos, cronômetro (livre/Pomodoro), registro de sessões, progresso por tópico/edital,
revisão espaçada e um painel com estatísticas reais. Tudo integrado à arquitetura existente,
sem reescrever o Radar e sem quebrar o contrato v1.

## Mineração e reutilização

Ver `docs/superpowers/specs/2026-10-16-study-platform-open-source-mining.md`. Resumo: código
**adaptado (MIT)** de `estudo-organizado` (revisões espaçadas, agregação de tempo, progresso,
cálculo de tempo decorrido); ideia de Pomodoro do `smart-student-productivity-dashboard` (MIT).
Projetos sem licença ou proprietários foram descartados. Nenhuma dependência nova (stdlib-only).

## Arquitetura

- **`radar/study.py`** — lógica **pura** (sem banco/DOM): `revision_dates`, `pending_revisions`,
  `content_progress`, `total_study_seconds`, `minutes_by_discipline`, `elapsed_seconds`,
  `validate_session`. Testável e determinística.
- **`radar/study_store.py`** — persistência SQLite (tabelas `estudo_*`) e o painel
  (`study_dashboard`), derivado **dos dados persistidos** (nunca de exemplos fictícios).
- **Schema v10** (aditivo) em `radar/document_store.py`: `estudo_disciplinas`,
  `estudo_topicos`, `estudo_progresso`, `estudo_sessoes`, `estudo_revisoes`.
- **API aditiva**: `GET /api/estudos/painel`, `GET/POST /api/estudos/disciplinas`,
  `GET/POST /api/estudos/topicos`, `GET/POST /api/estudos/progresso`,
  `GET/POST /api/estudos/sessoes`, `GET /api/estudos/sessao-atual`,
  `GET/POST /api/estudos/revisoes`.
- **CLI**: `estudos-painel`, `estudos-disciplina`, `estudos-topico`, `estudos-sessao`.
- **Interface**: seção **Estudos** (`#study-panel`) com cronômetro, disciplinas/tópicos,
  troca de estado de progresso e painel.

## Separação de dados pessoais

- Dados de estudo ficam em tabelas próprias, **nunca** expostas pelo contrato v1 nem enviadas
  às fontes de concursos. O banco é o mesmo (gitignored), mas a semântica é separada.
- **Catálogo × progresso**: o progresso é por `(contest_id, topico_id)` (`''` = geral). Estudar
  um tópico para um edital **não** altera o progresso dele em outro.

## Cronômetro

- No máximo **uma** sessão aberta por vez (`em_andamento`/`pausada`) — impede duplicação.
- `inicio` + `duracao_segundos` (acumulado) permitem **retomada após reinício** (o estado vive
  no banco; o frontend só desenha o relógio).
- Pausar/retomar/concluir/descartar. A duração é limitada a um teto plausível de 24 h
  (`study.capped_elapsed`), de modo que uma sessão que atravessa um fechamento longo do
  aplicativo **não** vire horas de estudo dormindo; sessões `descartada` não contam para o tempo
  estudado.

## Revisão espaçada

Agenda por frequências `[1, 7, 30, 90]` dias a partir da conclusão, **persistida** em
`estudo_revisoes` (a agenda é a fonte de verdade). Concluir um tópico cria as datas; marcar uma
revisão como feita (`POST /api/estudos/revisoes`, CLI `estudos-revisao`) grava `feita_em` e a
próxima data não feita passa a ser a pendente. O painel lista as revisões **vencidas**.

## Compatibilidade

- Contrato v1 (18 campos) **inalterado** (verificado por teste e por execução real).
- Migração **aditiva** v9→v10; base real migrada com backup, `integrity_check=ok` e contagens
  preservadas (593 concursos, 290 alertas, 751 propostas).
- Alertas, triagem, notificações, priorização e ranking da Fases 18–20 preservados.

## Pendências (fases futuras)

- Perfil de conhecimento × **conteúdo programático** extraído dos editais (lacunas,
  reaproveitamento, planejamento orientado a oportunidades).
- Import/export e backup dos dados pessoais de estudo.
- Flashcards e banco de questões (apenas software; conteúdo exige direitos próprios).
