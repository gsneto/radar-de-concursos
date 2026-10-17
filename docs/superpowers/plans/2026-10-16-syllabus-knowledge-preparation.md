# Plano - Fase 22: conteúdo programático, perfil e preparação

TDD; módulos puros (extração, normalização, cobertura, perspectivas) testados isoladamente;
persistência, API, exportação e backup com bancos temporários; prova real em cópia da base.

## Task 1 - Extração do conteúdo programático
- [x] `radar/program_content.py` (seções, hierarquia, evidência, estados, limites);
      wiring em `document_fields.extract_field_proposals`; campos `conteudo_*` em `_FIELDS`.
      `tests/test_program_content.py`.

## Task 2 - Perfil e preparação
- [x] `radar/preparation.py` (normalização, `conceito_key`, `coverage`, `perspective`).
      `radar/knowledge_store.py` (perfil CRUD, `resolve_program`, `preparation_report`,
      `send_gap_to_study`). Schema v11 (`estudo_perfil`). `tests/test_preparation.py`.

## Task 3 - Portabilidade dos dados pessoais
- [x] `radar/study_backup.py` (export/validate/import/backup/restore). `tests/test_study_backup.py`.

## Task 4 - API, CLI e interface
- [x] Rotas `/api/estudos/conteudo|preparacao|perfil|exportar|importar|lacuna`; CLI
      `estudos-conteudo|perfil|cobertura|exportar|importar|backup`; seção Preparação no frontend.
      `tests/test_knowledge_api.py` + ampliação de `test_ui.py`.

## Task 5 - Testes e prova real
- [x] Suíte completa: **829 testes, OK**. Prova real em cópia da base (CLI + HTTP), migração da
      base real com backup e integridade.

## Task 6 - Documentação, revisão e commit
- [x] Design/plano/prova-real; README + log; revisão independente (0 crítico, 7 importantes e
      12 menores corrigidos); commit/push.
