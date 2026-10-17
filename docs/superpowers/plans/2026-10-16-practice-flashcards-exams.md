# Plano - Fase 23: flashcards, questões e simulados

TDD; lógica pura testada isoladamente (agendamento, validação, seleção, cronômetro, correção);
persistência e API com bancos temporários; prova real em cópia da base.

## Task 1 - Auditoria e mineração
- [x] 7 repositórios prioritários clonados/inspecionados em `%TEMP%`; licenças, commits e stack
      registrados. Único código reutilizado: `flashcards-api` (`app/scheduler.py`, MIT).
      Registro em `docs/superpowers/specs/2026-10-16-practice-flashcards-exams-mining.md`.

## Task 2 - Schema v12 (aditivo)
- [x] Tabelas `pratica_*` (flashcards, revisões, questões, versões, tentativas, simulados,
      questões do simulado); migração aceita 0/2..12; idempotente.

## Task 3 - Lógica pura
- [x] `radar/flashcards.py` (SM-2-lite adaptado + fila + estatísticas) — `tests/test_flashcards.py`.
- [x] `radar/questions.py` (validação, correção, estatísticas) — `tests/test_questions.py`.
- [x] `radar/exams.py` (seleção sem duplicação, cronômetro, expiração, correção) —
      `tests/test_exams.py`.

## Task 4 - Persistência
- [x] `radar/practice_store.py` (CRUD, versões de questão, tentativas, simulados com resposta
      progressiva, desempenho) — `tests/test_practice.py`.

## Task 5 - API, CLI e interface
- [x] Rotas `/api/estudos/flashcards|questoes|tentativas|simulados|desempenho`; CLI
      `estudos-flashcard|questao|simulado|desempenho`; seção **Prática** no frontend;
      ampliação de `test_ui.py`.

## Task 6 - Portabilidade
- [x] Formato `radar-estudos` **v2** com prática, mantendo **v1** importável; testes de
      round-trip, idempotência e compatibilidade.

## Task 7 - Testes e prova real
- [x] Suíte completa: **912 testes, OK**. Prova real em cópia da base (CLI + HTTP), migração da
      base real (v12→v13) com backup e integridade; caminho v11→v12 provado em cópia.

## Task 8 - Licenças, documentação, revisão e commit
- [x] `THIRD_PARTY_NOTICES.md` (MIT do flashcards-api + motivos dos descartes); docs da fase;
      README + log; revisão independente (3 críticos + 5 importantes + 11 menores corrigidos);
      commit/push.
