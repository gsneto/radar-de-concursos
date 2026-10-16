# Plano — Fase 16: requisitos por seção sem código e elegibilidade

TDD; parser puro sobre blocos (sem rede nos testes). Provas reais separadas.

## Task 1 — Diagnóstico
- [x] Casos reais: 3056 (`(CARGO NNN)` + `N.M.k Requisitos:`), 3073/3057 (seção sem código
      `N.M NOME` + `N.M.k Requisitos:`). Antes: 0 requisitos.

## Task 2 — Parser de seções (`radar/section_requirements.py`)
- [x] `parse_sections` (numeração como âncora; código embutido separado do nome);
      `_requirement_value` (subitem casado por numeração); `extract_section_education`.

## Task 3 — Associação por nome
- [x] `reconcile_sections_by_name`: `explicita`/`ambigua`/`revisao`/`sem_cargo`; nunca por
      escolaridade; não associa quando ambíguo.

## Task 4 — Extensão do marcador de código
- [x] `parse_code_group` aceita `CARGO` (editais com `(CARGO 200)`).

## Task 5 — Integração
- [x] `document_fields` chama `extract_section_education`; `link_contest_proposals` aplica
      código **e** nome (após persistir).

## Task 6 — Testes
- [x] `tests/test_section_requirements.py` (16) + ampliação em `test_edital_requirements.py`
      e `test_role_reconciliation.py`. Suíte: **509 testes, OK**.

## Task 7 — Provas reais
- [x] `docs/superpowers/plans/2026-10-16-section-based-requirements-prova-real.md`.

## Task 8 — Documentação, revisão independente, commit e push.
- [x] README + log; revisão independente (code-reviewer) e correções; commit/push.

## Revisão independente — achados e correções

| # | Severidade | Achado | Correção |
|---|---|---|---|
| 1 | importante | `_section_label` truncava o nome em **qualquer** travessão em (`—`), podendo associar ao cargo errado | reutiliza `role_reconciliation._clean_label` (remove só anotações conhecidas); regressão `test_em_dash_in_name_is_not_truncated` |
| 2 | importante | gate `"equisito" not in text` era sensível a maiúsculas → seção `REQUISITOS:` não extraída | comparação em `text.lower()`; regressão `test_uppercase_requisitos_is_extracted` |
| 3 | importante | conflito de identidade na camada por **nome** levantava `ValueError` e abortava o lote | `try/except ValueError → ambigua`; regressão `test_identity_conflict_does_not_abort` |
| 4 | menor | `_NON_CARGO_HEADINGS` era código morto | removido |

Sem achados críticos. Suíte após correções: **512 testes, OK**. Prova real reexecutada:
resultados idênticos (3073: 10 cargos/29 vinculadas; idempotente).
