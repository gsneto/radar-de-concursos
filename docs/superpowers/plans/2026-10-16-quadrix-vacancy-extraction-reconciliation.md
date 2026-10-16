# Plano — Fase 13: extração de vagas da Quadrix e reconciliação multifonte

TDD; parser puro sobre blocos de texto (sem rede nos testes). Provas reais separadas.

## Task 1 — Diagnóstico reprodutível
- [x] Causa: PDF textual sem separador de célula + layout Quadrix ≠ DOU. Documento real
      reprocessado (3049/3056) com 0 propostas antes da correção.

## Task 2 — Estratégia específica (`radar/quadrix_tables.py`)
- [x] Cabeçalho de duas linhas por modalidade; linhas `[código] rótulo <imediatas> <reserva> <total>`.
- [x] `immediate/reserve/indigenous` por soma/valor da coluna; `-` = zero; soma conferida
      contra o Total; sem coluna indígena → sem proposta indígena.
- [x] Integração em `document_fields` (blocos de PDF), sem tocar HTML/DOU.

## Task 3 — Frente B: métricas e priorização
- [x] `confirmation.metrics.by_source`; `confirmation.priority_report` + CLI
      `confirmacao-prioridades`.

## Task 4 — Testes
- [x] `tests/test_quadrix_tables.py` (16) + ampliações em `test_confirmation.py`.
      Suíte: **420 testes, OK**.

## Task 5 — Provas reais
- [x] `docs/superpowers/plans/2026-10-16-quadrix-vacancy-extraction-reconciliation-prova-real.md`.

## Task 6 — Documentação, revisão independente, commit e push.
- [x] README + log; revisão independente (code-reviewer) e correções; commit/push.

## Revisão independente — achados e correções

| # | Severidade | Achado | Correção |
|---|---|---|---|
| 1 | importante | linha malformada (token avulso entre linhas ou célula em branco) fazia `break` e **abortava o resto da página** — viola "falha por item não para o lote" | âncora no código (seguido de rótulo), `continue` em vez de `break`, avança além de corridas inválidas (regressões `stray_number`, `blank_cell`) |
| 2 | importante | a conferência soma×Total podia ser driblada por deslocamento de coluna (rótulo terminando em número), emitindo proposta errada e internamente consistente | exige corrida de valores exatamente igual à largura do cabeçalho e token seguinte não-valor (regressão `shifted_columns`) |
| 3 | menor | estratégia roda para todo bloco de PDF, sem gate de fonte (agnóstica de banca) | documentado; o requisito estrutural (corrida com `AC`) impede disparo em DOU/FGV típicos |
| 4 | menor | `indigenous_vacancies` = PI do grupo **imediato**; reserva indígena fica diluída em `reserve_vacancies` | documentado no docstring/spec como "indígena imediato" |
| 5 | menor | continuação de tabela entre páginas / grupo de modalidades interrompido | omissão conservadora (sem valor errado); registrado nas limitações |

Sem achados críticos remanescentes. Suíte após correções: **423 testes, OK**. Prova real A
reexecutada com os mesmos resultados (133 propostas; idempotente).
