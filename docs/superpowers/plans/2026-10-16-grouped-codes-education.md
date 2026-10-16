# Plano — Fase 15: códigos agrupados, requisitos multibanca e elegibilidade

TDD; parser puro sobre blocos (sem rede nos testes). Provas reais separadas.

## Task 1 — Diagnóstico
- [x] Causa: Anexo II usa `CÓDIGOS … ATÉ …` (faixa), não `CÓDIGO NNN` singular; 3049 perde
      14 de 22 cargos. Reproduzido no edital real.

## Task 2 — Parser de códigos (`parse_code_group`)
- [x] Individual, lista e faixa (`ATÉ`/`A`/hífen/travessão); guardas de contexto e amplitude;
      zeros à esquerda; nunca inventa códigos.

## Task 3 — Extração por bloco + evidência compartilhada
- [x] `extract_education` expande o bloco, emite proposta por código com evidência que
      inclui o bloco literal; associação por código.

## Task 4 — Reconciliação e códigos ausentes
- [x] `reconcile_proposals_by_code`: rótulo só-código; anotação após "—" ignorada;
      `missing_codes` reporta códigos da faixa ausentes no HTML.

## Task 5 — Multibanca
- [x] `extract_declared_education` (rótulo explícito) como complemento genérico; roda só
      quando o Anexo II por cargo não produziu requisitos.

## Task 6 — Testes
- [x] `CodeGroupTest`, `GroupedEducationTest`, `DeclaredEducationTest`,
      `ExemptionRegressionTest` (regressão Fase 14) e ampliações em
      `test_role_reconciliation.py`. Suíte: **489 testes, OK**.

## Task 7 — Provas reais
- [x] `docs/superpowers/plans/2026-10-16-grouped-codes-education-prova-real.md`.

## Task 8 — Documentação, revisão independente, commit e push.
- [x] README + log; revisão independente (code-reviewer) e correções; commit/push.

## Revisão independente — achados e correções

| # | Severidade | Achado | Correção |
|---|---|---|---|
| 1 | importante | `parse_code_group` descartava códigos em blocos **mistos** (lista + faixa): `CÓDIGOS 200, 400 ATÉ 402` perdia o 200 | expande **todas** as faixas e preserva os avulsos fora delas (regressão `test_mixed_list_and_range`) |
| 2 | importante | `extract_declared_education` supercapturava o valor atravessando frases | terminador de frase (`[.;\n]`) na parada (regressão `test_does_not_capture_across_sentence`) |
| 3 | importante | `_LEVEL` casava nomes próprios ("Superior Tribunal de Justiça") → requisito fabricado | formas ancoradas (`nível/ensino X`, `X completo/em`, `X – área`) (regressão `test_proper_noun_superior_is_not_a_level`) |
| 4 | menor | split em " —" enfraquecia a checagem de nome para cargos que contenham "—" | remoção apenas de anotações **conhecidas** (`_clean_label`) |

Sem achados críticos. Suíte após correções: **492 testes, OK**. Prova real reexecutada:
22/22 cargos, reconciliação idêntica (147/22/125/0/0).
