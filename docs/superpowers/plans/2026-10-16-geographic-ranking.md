# Plano - Fase 20: inteligência geográfica e ranking explicável

TDD; módulos puros (localização/geografia/ranking/preferências) testados isoladamente e
integração com banco real temporário. Prova real separada.

## Task 1 - Localização estruturada
- [x] `radar/location.py` (`parse_location`, `resolve_location`, estados, prova × lotação,
      abrangência, conflito, validado prevalece). `tests/test_location.py` (20).

## Task 2 - Distância e preferências
- [x] `radar/geography.py` (seed + provedor local + Haversine; `geografica_linha_reta`;
      desconhecido explícito). `tests/test_geography.py` (13).
- [x] `radar/preferences.py` (validação, defaults, sem dados pessoais). `tests/test_preferences.py` (8).

## Task 3 - Ranking explicável
- [x] `radar/ranking.py` (pesos documentados, `factors` com motivo, ausência ≠ zero, piso
      excepcional, rótulos, urgência à parte). `tests/test_ranking.py` (16).

## Task 4 - Junção com os dados
- [x] `radar/priority.py` (propostas/revisões/valores vigentes; prova × lotação; distância;
      urgência; ordenação determinística). `tests/test_priority.py` (13, inclui retificação/conflito
      e coexistência com alertas/triagem).

## Task 5 - API, CLI e interface
- [x] `GET /api/prioridades`, `GET/POST /api/preferencias`; `ops-prioridades`, `ops-preferencias`;
      seção `#priorities-panel` com preferências, filtros e explicação. `tests/test_priority_api.py` (7)
      e ampliação em `test_ui.py`.

## Task 6 - Configuração
- [x] `preferences` em `ops_config.DEFAULTS` + `update_preferences` (grava só a chave, sem segredos);
      `radar_ops.json.example` atualizado; `radar_ops.json` permanece ignorado.

## Task 7 - Testes e prova real
- [x] Suíte completa: **681 testes, OK**. Prova real:
      `docs/superpowers/plans/2026-10-16-geographic-ranking-prova-real.md`.

## Task 8 - Auditoria, documentação, revisão e commit
- [x] Auditoria do SQLite; auditoria do perfil de conhecimento (Fase 21); README + log;
      revisão independente; commit/push.
