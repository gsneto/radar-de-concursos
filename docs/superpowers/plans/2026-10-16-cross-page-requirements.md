# Plano — Fase 17: requisitos entre páginas e associação auditável

TDD; parser puro sobre blocos (sem rede nos testes). Provas reais separadas.

## Task 1 — Diagnóstico
- [x] 3056: cabeçalho `2.3 … (CARGO 202)` no fim de uma página e `2.3.3 Requisitos:` na
      seguinte; o parser por bloco não casava → 10/15 cargos.

## Task 2 — Documento lógico com mapa de offsets
- [x] `build_logical_document` (texto + spans por bloco/página); evidência ancorada ao bloco
      onde o requisito aparece; valor que cruza a fronteira é truncado e anotado.

## Task 3 — Junção conservadora
- [x] Regex de seção sem ponte (nome não contém `N.M` nem cruza `\n`); ancoragem por
      numeração; sem falsas continuações.

## Task 4 — Robustez de rótulo
- [x] `_clean_label` corta na anotação **mais à esquerda**; anotação "continua na página
      seguinte" reconhecida.

## Task 5 — Testes
- [x] `CrossPageTest` + `LogicalDocumentTest` em `tests/test_section_requirements.py`.
      Suíte: **521 testes, OK**.

## Task 6 — Provas reais
- [x] `docs/superpowers/plans/2026-10-16-cross-page-requirements-prova-real.md`.

## Task 7 — Documentação, revisão independente, commit e push.
- [x] README + log; revisão independente (code-reviewer) e correções; commit/push.

## Revisão independente — achados e correções

| # | Severidade | Achado | Correção |
|---|---|---|---|
| 1 | importante | `extract_section_education` passou a concatenar blocos **sem página** (HTML), que antes eram ignorados | só blocos com `page_number` entram no documento lógico; `block_index` mapeado para a lista original (regressões `test_html_blocks...`, `test_evidence_block_index_maps...`) |
| 2 | importante | a regex "sem ponte" ainda criava seção falsa na fronteira de página (ex.: "3.2 reais") | nome da seção precisa **começar por maiúscula** (regressão `test_number_mid_sentence_is_not_a_section`) |

Sem achados críticos. Suíte após correções: **524 testes, OK**. Prova real reexecutada:
resultados idênticos (3056: 15 cargos/42 vinculadas; 3073: 10/29; idempotente).
