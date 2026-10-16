# Plano — Fase 12: expansão da confirmação oficial (Quadrix) e documentos da FGV

TDD; parsers puros com fetchers/transportes injetáveis (sem rede nos testes). Provas
reais separadas, em banco temporário isolado.

## Task 1 — Schema v6: classificação documental fina
- [x] Migração **aditiva** v6: `ALTER TABLE documentos ADD COLUMN tipo_documental TEXT`.
- [x] `SCHEMA_VERSION=6`, leitura aceita 2..6; `register_document` grava `document_type`.

## Task 2 — Novo conector oficial: Quadrix (`radar/quadrix_source.py`)
- [x] `parse_catalog` (lista `/index/<status>/`), `parse_detail` (página `/informacoes/<id>/`),
      `classify_document`, `to_candidate`, `_page_candidate`, `discover` (multi-concurso,
      incremental), `quadrix_source`.
- [x] Allowlist: `anexos-r2.selecao.net.br` restrito a `/uploads/`.

## Task 3 — Frente B: seguir links da FGV
- [x] `fgv_source.discover` com `max_refresh_details` (revisão de conhecidos por
      `last_checked_at`), classificando documentos por evidência.

## Task 4 — Fila e resolvers
- [x] `QuadrixResolver` (catálogo Quadrix → edital completo) em `default_resolvers()`.
- [x] `confirmation.metrics` + CLI `confirmacao-metricas`.

## Task 5 — Testes
- [x] `tests/test_quadrix_source.py` (18, novo), ampliações em `test_fgv_source.py`,
      `test_official_resolvers.py`, `test_confirmation.py`, `test_ui.py`.
      Suíte: **395 testes, OK**.

## Task 6 — Provas reais (A: Quadrix; B: FGV) em banco temporário.
- [x] `docs/superpowers/plans/2026-10-16-official-confirmation-expansion-prova-real.md`.

## Task 7 — Documentação, revisão independente, commit e push.
- [x] README + log de trabalho; revisão independente (code-reviewer) e correções; commit/push.

## Revisão independente — achados e correções

| # | Severidade | Achado | Correção |
|---|---|---|---|
| 1 | crítico | `get_competition_details` lia `tipo_documental` mas `_READABLE_VERSIONS` aceita 2..5 → banco não migrado (v5) quebrava o endpoint de detalhe | detecção da coluna via `PRAGMA table_info`; degrada para `NULL` quando ausente (teste `test_v5_database_reads_without_tipo_documental_column`) |
| 2 | importante | `QuadrixResolver`/`FgvCatalogResolver` escolhiam a primeira entrada em empate, sem marcar ambiguidade (172 grupos de títulos duplicados no catálogo Quadrix) | empate na pontuação máxima → `ambiguity` (item vira `inconclusivo`); testes de empate |
| 3 | importante | classificador errava: `"Cronograma ... conforme retificações"` virava `retificacao` | tipos finos explícitos avaliados antes da heurística ampla de "retifica" (teste `Cronograma - atualizado conforme retificações`) |
| 4 | menor | `_register_official` não gravava `tipo_documental` | deriva via `document_types.classify(title)` |
| 5 | menor | `_resolve` passou a executar toda a cadeia (mais requisições) | volta o curto-circuito no primeiro casamento não ambíguo, guardando o ambíguo como reserva |
| 6 | menor | fallback de página do Quadrix nunca concluía (`documento_localizado` eterno) | resolução `no_download` → estado `fonte_oficial_localizada` (retomável) |
| 7 | menor | `_V6_DDL` morto | removido |

Sem achados críticos remanescentes após as correções. Suíte: **401 testes, OK**.
