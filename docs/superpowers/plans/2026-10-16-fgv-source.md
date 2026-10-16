# Plano — Fase 9: terceira fonte (FGV Conhecimento)

> TDD; fixtures determinísticas; rede só na prova. Sem commit de segredos/bancos.

**Spec:** `docs/superpowers/specs/2026-10-16-fgv-source-design.md`

## Task 1 — Adaptador `radar/fgv_source.py`
- [x] `parse_catalog`, `parse_detail`, `classify_document`, `catalog_url`, `detail_url`, `to_candidate`.
- [x] `fetch_catalog`/`fetch_detail` (UA, HTTPS, limite, decodificação robusta).
- [x] `discover(db_path, ...)` multi-concurso (identidade por slug; detalhe só de novos; limite por ciclo).
- [x] `fgv_source(...)` descritor (`multi_contest`, `download_new_only`).

## Task 2 — Integração
- [x] `document_discovery._AUTHORIZED_SOURCES` += `conhecimento.fgv.br` (`/concursos/`, `/sites/default/files/concursos/`).
- [x] `monitoring._run_source` multi-concurso (`db_path` no discover; `known_ids` por observação; `download_new_only`).
- [x] `default_sources()` inclui a FGV.

## Task 3 — Testes (`tests/test_fgv_source.py`)
- [x] Catálogo (válido/vazio/dedup/links não-concurso), paginação/URL, detalhe (título/status/docs), classificação, descoberta (identidade por concurso, limite, idempotência), ciclo (registra+baixa uma vez, v1 intacto, falha), segurança de hosts.

## Task 4 — Prova real
- [x] `docs/superpowers/plans/2026-10-16-fgv-source-prova-real.md`.

## Task 5 — Revisão, commit, push
- [ ] Suíte completa + revisão independente + commit/push.
