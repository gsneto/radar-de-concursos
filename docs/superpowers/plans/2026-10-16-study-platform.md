# Plano - Fase 21: mineração open source e plataforma de estudos

TDD; lógica pura testada isoladamente; persistência e API com banco temporário; prova real em
cópia da base habitual.

## Task 1 - Auditoria e mineração
- [x] 9 repositórios obrigatórios: clonados/inspecionados em `%TEMP%`; licenças, commits e
      stack registrados; `ispectr3/RadarConcursos` indisponível. Buscas adicionais (PT/EN).
      Registro em `docs/superpowers/specs/2026-10-16-study-platform-open-source-mining.md`.

## Task 2 - Schema v10 (aditivo)
- [x] Tabelas `estudo_*` em `radar/document_store.py`; migração aceita 0/2..10; idempotente.

## Task 3 - Lógica pura (`radar/study.py`)
- [x] Revisões espaçadas, progresso, tempo, validação de sessão (adaptado MIT + próprio).
      `tests/test_study.py` (18).

## Task 4 - Persistência (`radar/study_store.py`)
- [x] Disciplinas/tópicos, progresso por edital, sessões (cronômetro), revisões, painel.
      `tests/test_study_store.py` (19).

## Task 5 - API, CLI e interface
- [x] Rotas `/api/estudos/*`; CLI `estudos-*`; seção **Estudos** no frontend.
      Ampliação de `test_ui.py`.

## Task 6 - Testes e prova real
- [x] Suíte completa: **751 testes, OK**. Prova real em cópia da base (CLI + HTTP), migração da
      base real com backup e verificação de integridade.

## Task 7 - Licenças, documentação, revisão e commit
- [x] `THIRD_PARTY_NOTICES.md`; design/plano/prova-real; README + log; revisão independente
      (1 crítico + 2 importantes + 8 menores corrigidos); commit/push.
