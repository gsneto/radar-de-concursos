# Fase 19 - Notificações nativas do Windows e central de triagem acionável

Data: 2026-10-16. Base: `ba2fd09` (Fase 18), 563 testes OK.

## Objetivo

Tornar o Radar **avisável e acionável sem abrir o terminal**: (A) notificações nativas do
Windows para alertas críticos/oportunidades, com identidade de evento estável, controle de
frequência e clique que abre o concurso; (B) uma **central de triagem** que agrupa alertas
por concurso, prazo, prioridade e evidência, com ações reais (visto/dispensar/adiar/reabrir/
abrir concurso/ver evidência/ver fila). Alertas e triagem continuam funcionando na
interface mesmo com a notificação desligada.

## Canal de notificação (Windows)

- **WinRT `Windows.UI.Notifications`** via **Windows PowerShell 5.1** (`powershell.exe`):
  os tipos WinRT carregam de forma confiável ali (não no PowerShell 7). `scripts/notify.ps1`
  emite o toast e devolve JSON `{"accepted": bool, "error": str|null}`.
- **Identidade de app (AUMID) `RadarDeConcursos.Radar`**: um app desktop *unpackaged* só
  aparece com AUMID próprio se existir um atalho no Menu Iniciar carregando
  `System.AppUserModel.ID`. `scripts/install_app_identity.ps1` cria/atualiza o atalho de
  forma **idempotente** (C#/`ctypes` para escrever a propriedade). `radar/notifications.py`
  expõe `ensure_app_identity()`.
- **Prova de entrega**: `Show()` aceitar (`accepted:true`) **não** prova exibição — um AUMID
  inválido também é aceito. A prova é a leitura pelo **`UserNotificationListener`** (access
  `Allowed`) mostrando `APP=RadarDeConcursos.Radar` com o texto do alerta.

## Política de notificação (`radar/notifications.py`)

`dispatch(db_path, config, *, now, runner, limit)`:

- **Opt-in**: `notifications.local` (padrão `false`). Desligado, nada é enviado e a interface
  de alertas segue normal.
- **Elegibilidade**: categorias (`categories`, padrão `prazo_isencao`, `retificacao`,
  `falha_fonte`) e severidade mínima (`min_severity`, padrão `atencao`).
- **Identidade estável / dedup**: um alerta `enviada` não é reenviado; `erro` é reprocessado
  no ciclo seguinte. Escalação de severidade gera **novo** alerta (chave de dedup inclui o
  estado) e portanto nova notificação.
- **Frequência**: `max_per_cycle` (padrão 5) e `min_interval_seconds` (padrão 30, intervalo
  mínimo entre envios, persistido em `ops_state`). O excedente vira **backlog** e é retomado
  nos ciclos seguintes — nunca descartado.
- **Respeita a triagem**: alertas vistos, dispensados ou adiados (`snoozed_until`) não são
  notificados.
- **Destino seguro**: o clique usa `base_url` do **config** (`http://127.0.0.1:8000`), nunca
  uma URL vinda do payload (evita `javascript:`/hostil).
- **Segredos**: mensagem sem token/cookie/senha.

## Central de triagem (`ops.triage` + `GET /api/triagem`)

- **Agrupamento só por identidade provada**: por `contest_id`. Alertas sem concurso
  identificado ficam no grupo "Sem concurso identificado"; **nunca** se une por semelhança de
  título (dois concursos com título igual permanecem separados).
- **Urgência a partir de datas documentadas** (nunca presumidas):
  `hoje` (prazo expirado/no dia), `proximos` (dentro do horizonte `triage_horizon_days`,
  padrão 7), `retificacoes`, `novos`, `falhas`, `outros`. Prazo **desconhecido** não vira
  "expirado"; `exemption_end` é tratado como fim de isenção, não como fim de inscrição. O
  prazo do concurso usa o **valor vigente** (`valores_atuais`) e, na falta dele, a proposta
  **mais recente** — nunca a mais antiga (uma retificação não pode rejuvenescer o prazo).
- **Ações** (`POST /api/alertas/<id>` e botões na interface): `seen`, `dismiss`, `reopen`,
  `snooze` (`until`, normalizado para UTC). Visto/dispensar/adiar **não apaga** histórico nem
  documentos; reabrir traz de volta à triagem. "Abrir concurso" navega para o card do
  concurso (`#concurso=<id>`, foco/rolagem); "Ver fonte" abre a fonte quando é HTTPS.
- **Backlog incremental**: `generate_alerts` usa *watermark* (`ops_state`) e um orçamento
  `max_new_alerts_per_cycle` (padrão 200). Um backlog grande (>50) é drenado em ciclos
  sucessivos, em ordem cronológica, sem duplicar (dedup por chave) e sem perder itens.

## Esquema (v9)

Aditivo em `radar/document_store.py`: colunas `alertas` `notified_at`, `notify_state`,
`notify_attempts`, `notify_error`, `snoozed_until`; tabela `ops_state(key PK, value,
updated_at)` para *watermarks* e cursores. `SCHEMA_VERSION=9`; migração aceita 0/2..9.
A migração **semeia** os *watermarks* de alertas com o cursor atual quando ainda ausentes
(impede reprocessar todo o histórico na primeira geração pós-migração, o que duplicaria
alertas cuja chave de dedup mudou) e cria índices por `documentos(discovered_at)` e
`versoes_documento(fetched_at)` para a varredura incremental.

## CLI e interface

- `python -m radar ops-triagem [--limit N] [--include-seen]` - grupos e contagens.
- `python -m radar ops-notificar` - despacha notificações elegíveis.
- `python -m radar ops-identidade` - garante a identidade de app (atalho/AUMID).
- Seção **Central de triagem** (`#triage-panel`) na interface: filtros por categoria,
  agrupamento por concurso, ações (visto/adiar/reabrir/dispensar/ver fonte) e "Abrir
  concurso" (navega por `#concurso=<id>` até o card do concurso). Atualização periódica
  inclui a triagem.

## Auditoria de segurança (F19 §9/§11)

- **SQLite em pasta OneDrive**: a base vive em `...\OneDrive\Desktop\...\data\radar.sqlite3`.
  Risco: sincronização parcial durante escrita. Recomendação (não destrutiva, documentada):
  manter a base **fora** de sincronização em tempo real, com backup + verificação +
  rollback; **não** excluir a cópia antiga. Não altera comportamento nesta fase.
- **Prioridade geográfica** (Bahia/Pernambuco, prova vs lotação, deslocamento desde Paulo
  Afonso): **lacuna identificada**, não implementada nesta fase.
- **Inteligência de conteúdo** (perfil pessoal, casamento com conteúdo programático):
  **lacuna identificada**, não implementada nesta fase.

## Compatibilidade e limites

- API v1 (`GET /api/concursos`, 18 campos): **inalterada**.
- Notificação local depende de Windows ligado, rede para a coleta e das configurações de
  foco/notificação do usuário; a exibição visual não é garantida pelo `Show()`.
- Nada é promovido a validado; a revisão humana continua.
