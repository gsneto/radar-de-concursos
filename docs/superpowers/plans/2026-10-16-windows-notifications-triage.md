# Plano - Fase 19: notificações nativas e central de triagem

TDD; canal de notificação com `runner` injetável (sem toasts reais nos testes). Prova real
separada.

## Task 1 - Esquema v9
- [x] `radar/document_store.py`: colunas `alertas` (`notified_at`, `notify_state`,
      `notify_attempts`, `notify_error`, `snoozed_until`) + tabela `ops_state`; migração
      aceita 0/2..9; `SCHEMA_VERSION=9`.

## Task 2 - Identidade de app e canal nativo
- [x] `scripts/notify.ps1` (toast WinRT via Windows PowerShell 5.1) e
      `scripts/install_app_identity.ps1` (atalho no Menu Iniciar + AUMID, idempotente).
- [x] `radar/notifications.py`: `AUMID`, `ensure_app_identity`, `native_supported`,
      `send_toast(runner=)`, `notification_config`.

## Task 3 - Política de envio
- [x] `dispatch` (opt-in, categorias/severidade, dedup por estado, retry de erro, limite por
      ciclo com backlog, respeito a visto/dispensado/adiado, destino seguro).

## Task 4 - Triagem e backlog incremental
- [x] `ops.triage` (grupo só por `contest_id`, urgência por data documentada, ações);
      `generate_alerts` com *watermark* + orçamento e backlog; `mark_alert(snooze_until=)`.

## Task 5 - CLI, API e interface
- [x] `ops-triagem`, `ops-notificar`, `ops-identidade`; `GET /api/triagem` e
      `POST /api/alertas/<id>`; seção Central de triagem (`renderTriage`, ações, filtros).

## Task 6 - Testes
- [x] `tests/test_notifications.py` (18), `tests/test_triage.py` (18), ampliações em
      `test_ops.py`, `test_ops_api.py`, `test_ui.py`. Suíte: **605 testes, OK**.

## Task 7 - Prova real (toast entregue, triagem, backlog)
- [x] `docs/superpowers/plans/2026-10-16-windows-notifications-triage-prova-real.md`.

## Task 8 - Auditoria de segurança, documentação, revisão e commit
- [x] Auditoria OneDrive + lacunas (prioridade geográfica, inteligência de conteúdo);
      README + log; revisão independente; commit/push.
