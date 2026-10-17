# Prova real - Fase 21: plataforma de estudos

Data: 2026-10-16. Python validado: `C:\Users\anton\Documents\OpenCode-PC\runtime\venv\Scripts\python.exe`.

## Suíte de testes

- Baseline observada (antes de implementar): **704 testes, OK** (execução real).
- Final: **751 testes, OK**. Novos: `test_study.py` (22), `test_study_store.py` (25),
  ampliação de `test_ui.py` (harness Node cobre `renderStudy`/`formatClock`).
- Ajuste: 4 asserções de versão de esquema passaram de 9 para 10 (`test_confirmation`, `test_ops`).
- Observação de ambiente: em uma execução houve 1 erro intermitente de socket em
  `test_ops_api` (passou isolado e nas execuções seguintes); não reproduzível — registrado como
  flutuação de ambiente, não regressão.

## Migração da base habitual (v9 → v10)

Backup prévio: `data/radar.sqlite3.bak-20261016-205718` (16.769.024 bytes).

| Momento | integrity_check | user_version | concursos | alertas | propostas |
|---|---|---|---|---|---|
| antes | ok | 9 | 593 | 290 | 751 |
| depois | ok | 10 | 593 | 290 | 751 |

Tabelas criadas: `estudo_disciplinas`, `estudo_topicos`, `estudo_progresso`, `estudo_sessoes`,
`estudo_revisoes`. Migração aditiva e idempotente (reexecução sem efeito).

## Prova funcional (cópia da base real)

CLI (`python -m radar estudos-*`) sobre uma **cópia** consistente da base habitual:

```
estudos-disciplina --nome "Direito Constitucional"   -> {"id": "8ac4d593-...", "nome": "Direito Constitucional"}
estudos-topico --disciplina 8ac4d593-... --nome "Princípios fundamentais" -> {"id": "f70b96dd-...", ...}
estudos-sessao start --disciplina 8ac4d593-... --modo pomodoro -> estado em_andamento modo pomodoro
estudos-sessao status  -> estado em_andamento elapsed 0
estudos-sessao finish  -> estado concluida duracao 0
estudos-painel         -> disciplinas 1 topicos 1 sessoes 1 conteudo {'done': 0, 'total': 1, 'pct': 0}
```

HTTP (servidor loopback real, `python -m radar serve`):

```
GET /api/concursos        -> 200 (contrato v1 inalterado)
GET /api/estudos/painel   -> 200  disciplinas=1 sessoes=1
GET /api/prioridades?limit=2 -> 200 (sem regressão)
```

## Comportamentos verificados por teste automatizado

- Cronômetro: iniciar, pausar, retomar, concluir, recuperar após reinício, duração válida
  (com teto de 24 h), impedir sessão duplicada (também por índice único no banco), rejeitar
  tempos inválidos (`test_study_store`, `test_study`).
- Tópicos: criar/atualizar, relacionar a disciplina, registrar progresso, isolar por edital,
  preservar após reinício (`test_study_store`).
- Revisão espaçada: agenda `[1,7,30,90]` persistida; **marcar revisão feita avança a agenda**
  (`test_marcar_revisao_avanca_a_agenda`), provado na base real (4 → 3 pendentes).
- Painel: estatísticas derivadas dos dados persistidos, agregadas em SQL (sem truncar).
- Contrato v1: bytes de `/api/concursos` iguais antes/depois (`test_study_store.StudyApiTest`).

## Revisão independente (delegação via `task`/code-reviewer)

Achados corrigidos: **1 crítico + 2 importantes + 8 menores + NITs**.

- **Crítico:** a revisão espaçada era **inerte** (`feita_em` nunca gravado; a agenda persistida
  não avançava). Corrigido com `study_store.mark_revision_done` + rota
  `POST /api/estudos/revisoes` + CLI `estudos-revisao` + botão na UI; a pendência passou a ser
  lida da agenda persistida. Regressão: `test_marcar_revisao_avanca_a_agenda`.
- **Importante:** `validate_session` era código morto e o cronômetro não tinha teto (3 dias
  fechado → 72 h registradas). Corrigido com `study.capped_elapsed` aplicado em
  pausar/concluir/ler. Regressão: `test_duracao_truncada_no_teto`.
- **Importante:** o painel truncava os totais em 1000 sessões. Corrigido com agregação em SQL.
- **Menores:** data local (não UTC) para o "dia de estudo"; `contest_id` validado na escrita e
  leitura; índice único de sessão aberta; exclusões em cascata; JSON legível nos 400; menos
  conexões no painel; registro das adaptações na atribuição; `renderStudyTimer` limpa o
  intervalo; arredondamento consistente; seção de Estudos fora do auto-refresh (preserva o
  formulário).

## Limitações honestas

- Nenhuma dependência nova; sem flashcards/banco de questões nem import/export nesta fatia.
- O cronômetro não bloqueia a aba nem emite alerta sonoro no fim do Pomodoro.
