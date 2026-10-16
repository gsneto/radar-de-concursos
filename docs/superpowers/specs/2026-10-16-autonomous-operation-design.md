# Fase 18 — Operação autônoma no Windows, alertas persistentes e atualização do Radar

Data: 2026-10-16. Base: `b7aedfc` (Fase 17), 524 testes OK.

## Objetivo

Transformar os componentes já construídos num **fluxo operacional autônomo**, observável,
recuperável e seguro, sem abrir o OpenCode nem digitar comandos: um ciclo único que coleta
as fontes, enfileira e processa a fila documental em lote limitado, gera alertas
persistentes e publica o estado via API/interface.

## Configuração central (`radar/ops_config.py`)

Uma fonte de verdade, versionável como **exemplo** (`radar_ops.json.example`) e ignorada
quando local (`radar_ops.json`, no `.gitignore`). Precedência: defaults → arquivo →
variáveis `RADAR_*`. Resolve **project_root**, **python** (o do venv validado, nunca o
`python` do PATH), **db_path**, **logs_dir**, intervalos, limite de lote, timeouts e fontes
habilitadas. Nada de segredos. `validate_config` distingue config válida de inválida e
aceita um banco ainda inexistente (o ciclo o cria).

## Ciclo operacional (`radar/ops.py`)

`run_cycle(config)` orquestra os componentes existentes (não cria pipeline paralelo):

1. valida a configuração (aborta com `falhou` e erros explícitos);
2. adquire **instância única** (bloqueio de arquivo);
3. executa as fontes habilitadas via `monitoring.run_cycle` (falha isolada por fonte);
4. reconcilia candidatos (`confirmation.reconcile`);
5. enfileira (`enqueue_pending`) e processa um **lote limitado** (`process_batch`);
6. gera **alertas persistentes**;
7. termina com estado `concluido` / `parcial` / `falhou` / `ignorado`.

Uma fonte indisponível não impede as demais; uma coleta vazia bem-sucedida ≠ falha.

### Instância única

`InstanceLock` usa `msvcrt.locking` (Windows) sobre um arquivo mantido aberto: o SO libera o
bloqueio quando o processo termina, o que **distingue processo ativo de marcador
abandonado**. Um segundo ciclo retorna `ignorado` e registra o motivo; após queda, o
próximo ciclo readquire o bloqueio (não fica preso para sempre). Fallback POSIX por
`O_EXCL` + verificação de PID.

## Alertas persistentes (schema v8)

Tabela aditiva `alertas` (`id, kind, severity, contest_id, observation_id, source_id,
dedup_key UNIQUE, title, detail, event_at, created_at, seen_at, dismissed_at,
payload_json`). Tipos: `novo_candidato`, `documento_recuperado`, `retificacao`,
`falha_fonte`, `prazo_isencao`, `lote_confirmacao`. **Dedup por chave** evita repetir a
mesma novidade em todos os ciclos; marcar como visto/descartado **não apaga** o histórico.
Prazos de isenção (`exemption_end`) geram alerta `atencao` quando próximos (≤ 7 dias) e
`critico` quando expirados — sempre a partir da data documental, nunca presumida.

## Saúde (`ops.health` + `GET /api/saude`)

Responde ao estado **real**: config válida, banco abrível e legível, versão do esquema,
último ciclo e suas fontes, execuções presas (`em_andamento`), fila pendente e alertas não
vistos. Status: `pronto`, `funcionando_com_limitacoes`, `fontes_indisponiveis`,
`sem_ciclo`, `execucao_atrasada`, `banco_indisponivel`, `configuracao_invalida`. Não
dispara coletas.

## Logs

`RotatingFileHandler` (2 MB × 3) em `logs/radar_ops.log`: início/fim do ciclo, `run_id`,
fontes e resultado, tempo, itens da fila, alertas. Sem tokens/cookies/cabeçalhos.

## Agendamento no Windows (`scripts/`)

- `install_tasks.ps1` — registra **"Radar de Concursos - Ciclo"** (a cada N h, padrão 6 h)
  com `MultipleInstances=IgnoreNew` (não sobrepõe) e `StartWhenAvailable` (recupera após
  reinício); usa o **Python do config** e a conta do usuário, **sem senha armazenada**.
  `-IncludeServer` adiciona o servidor no logon.
- `uninstall_tasks.ps1` — remove as tarefas **sem apagar dados**.
- `verify_tasks.ps1` — estado, última execução/resultado e próxima execução.
- `run_cycle.ps1` / `serve.ps1` — ciclo e servidor (loopback) manuais.

## Interface

Nova seção **Alertas** (`#alerts-panel`) e **atualização periódica** (`startAutoRefresh`,
padrão 60 s, configurável por `data-refresh-seconds`), sem recarregar a página. O
`renderAlerts` mostra tipo/severidade com rótulos humanos. Alertas persistem após
reiniciar o navegador (ficam no banco).

## Compatibilidade e limites

- API v1 (`GET /api/concursos`, 18 campos): **inalterada**.
- Nada é promovido a validado; a revisão humana continua.
- Sem credenciais de e-mail/WhatsApp; notificação local é opcional (`notifications.local`).
- Se o Windows estiver desligado/sem rede, o ciclo não roda; a tarefa retoma no próximo
  disparador (`StartWhenAvailable`), sem executar ciclos atrasados em cascata.
