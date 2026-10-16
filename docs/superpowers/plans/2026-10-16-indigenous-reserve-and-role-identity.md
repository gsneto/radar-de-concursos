# Plano — Fase 14: reserva indígena, identidade por código, formação e isenção

TDD; parsers puros sobre blocos/HTML (sem rede nos testes). Provas reais separadas.

## Task 1 — Schema v7 + campos
- [x] `cargos_identidade.code` (aditivo, v7); leitura 2..7.
- [x] Novos campos: `indigenous_reserve_vacancies` (contagem), `accepted_courses`,
      `si_compatibility`, `exemption_start/end/result_preliminary/appeal/result_final`.

## Task 2 — Reserva indígena (Frente A)
- [x] `quadrix_tables`: PI do grupo imediato → `indigenous_vacancies`; PI do grupo de
      reserva → `indigenous_reserve_vacancies`; sem coluna → nenhuma proposta.

## Task 3 — Identidade por código (Frente B)
- [x] `ensure_role(code=...)` contextualizado; `parse_cargo_table`; `role_reconciliation`.

## Task 4 — Formação e SI (Frente C)
- [x] `edital_requirements.extract_education` + `classify_si_compatibility`.

## Task 5 — Complemento isenção
- [x] `edital_requirements.extract_exemption_dates` (cronograma, com proximidade).

## Task 6 — Classificação e CLI
- [x] `classify_opportunity` + `role_opportunities` + CLI `confirmacao-oportunidades`.

## Task 7 — Testes
- [x] `tests/test_edital_requirements.py` (14), `tests/test_role_reconciliation.py` (10),
      ampliações em `test_quadrix_tables.py`, `test_document_store.py`, `test_confirmation.py`.
      Suíte: **460 testes, OK**.

## Task 8 — Provas reais
- [x] `docs/superpowers/plans/2026-10-16-indigenous-reserve-and-role-identity-prova-real.md`.

## Task 9 — Documentação, revisão independente, commit e push.
- [x] README + log; revisão independente (code-reviewer) e correções; commit/push.

## Revisão independente — achados e correções

| # | Severidade | Achado | Correção |
|---|---|---|---|
| 1 | importante | `_dates_after` atravessava o fim de frase e capturava a data de **inscrição/pagamento** como isenção | janela truncada na primeira fronteira de frase (`re.split(r"[.\n]")`); regressão `does_not_cross_sentence` |
| 2 | importante | `ensure_role` rejeitava variação benigna de nome para o mesmo código e o `ValueError` **abortava** a reconciliação | comparação tolerante (`role_names_compatible`, tokens em comum) + `reconcile_proposals_by_code` captura `ValueError` → `ambiguous` |
| 3 | importante | `classify_opportunity` tratava dado **ausente** como "sem vaga" (imediato=0, reserva não extraída) | só afirma `sem_vaga_indigena` quando **ambos** conhecidos e 0; senão `vaga_indigena_desconhecida` |
| 4 | importante | `_DATE_RANGE`/`_DATE_PAIR` não reconheciam "DD a DD/MM/AAAA" (mesmo mês) → início errado e fim ausente | padrão `_DATE_PAIR_A` adicionado |
| 5 | menor (observação) | `parse_cargo_table`/`reconcile_proposals_by_code` sem chamador de produção | `link_contest_proposals` (nível DB) + CLI `quadrix-cargos` ligam o fluxo |

Sem achados críticos. Suíte após correções: **467 testes, OK**. Prova real reexecutada:
resultados idênticos (46 cargos, 263 propostas, idempotente).
