# Plano — Fase 11: fila de confirmação documental e reconciliação multifonte

> TDD; testes com resolvers/transportes injetáveis (sem rede); prova real separada.

**Spec:** `docs/superpowers/specs/2026-10-16-official-confirmation-queue-design.md`

## Task 1 — Schema v5 + fila (`radar/confirmation.py`)
- [x] Migração aditiva v5 (`fila_confirmacao`); leitura aceita 2..5.
- [x] Estados, `enqueue_from_candidates`/`enqueue_pending`, `compute_priority`,
      `select_batch`, `process_batch` (lotes, isolamento por item, backoff),
      `recover_stale`, `queue_status`, `get_item`, `reconcile`.

## Task 2 — Resolvers de referência oficial (`radar/official_resolvers.py`)
- [x] `FgvCatalogResolver` (catálogo FGV) e `DouSearchResolver` (busca pública do DOU),
      com filtro de "concurso" (evita licitações/contratos) e ambiguidade explícita.

## Task 3 — CLI e API
- [x] `confirmacao-status`, `confirmacao-reconciliar`, `confirmacao-lote` (`--limit`,
      `--enqueue`, `--dry-run`), `confirmacao-item`.
- [x] `GET /api/confirmacao` (aditivo, somente leitura); v1 intacto.

## Task 4 — Testes
- [x] `tests/test_confirmation.py`, `tests/test_official_resolvers.py`,
      `tests/test_confirmation_api.py`.

## Task 5 — Prova real
- [x] `docs/superpowers/plans/2026-10-16-official-confirmation-queue-prova-real.md`.

## Task 6 — Revisão, commit, push
- [x] Suíte completa (**368 testes OK**) + revisão independente (code-reviewer).
- [x] Achados importantes corrigidos (isolamento do lote, `last_attempt_at` na marcação,
      retomada de estados com backoff) + menores (contagem de `enqueue_pending`, guarda
      de FK, `reconcile` ambíguo, `upcoming`). Commit/push na branch de trabalho.

## Revisão independente — achados e correções

| # | Severidade | Achado | Correção |
|---|---|---|---|
| 1 | importante | erro inesperado (marcação/`_finish`/COUNT) abortava o lote | corpo do item em `try/except`; item vira `falhou` e o lote continua |
| 2 | importante | `em_processamento` não gravava `last_attempt_at` → `recover_stale` recuperava item fresco | `_mark_processing` grava `last_attempt_at` |
| 3 | importante | `documento_localizado`/`inconclusivo` recebiam backoff mas nunca eram retomados | `select_batch` re-seleciona `RETRYABLE_STATES` quando `next_attempt_at` vence |
| 4 | menor | `enqueue_pending` supercontava `created` (INSERT OR IGNORE) | conta por `total_changes` |
| 5 | menor | `reconcile` nunca classificava `ambiguo` | órgãos distintos para o mesmo título normalizado → `ambiguo` |
| 6 | menor | `enqueue_from_candidates` abortava tudo por FK de observação inexistente | valida existência da observação antes de inserir |
| 8 | menor | `queue_status.upcoming` omitia estados retomáveis | inclui `inconclusivo`/`documento_localizado` |

Débito técnico documentado (não corrigido nesta fase): itens 7 (estados inalcançáveis
`fonte_oficial_localizada`/`documento_registrado`/`confirmacao_parcial`/`concluido`),
9 (`user_version` cru no CLI), 10 (URL do DOU por concatenação), 11 (redirect do
`_http_get`). Sem achados críticos.
