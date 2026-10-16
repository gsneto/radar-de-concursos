# Plano — Fase 8: extração de vagas por cargo e modalidade

> Execução com TDD (RED → GREEN). Sem commit de bancos/segredos. Não migrar base real.

**Spec:** `docs/superpowers/specs/2026-10-16-extracao-vagas-dou-design.md`

## Task 1 — Extrator genérico `radar/vacancy_tables.py`

- [ ] RED: `tests/test_vacancy_tables.py` — cargo+total; indígenas por cargo; reserva só global; CR sem número não vira 0; zero confirmado vs ausente; cabeçalho multi-linha; colunas em ordem diferente; quebra de linha no nome do cargo; número fora de seção de vagas ignorado; dois cargos semelhantes não fundidos.
- [ ] Implementar `normalize`, `detect_header`, `map_columns`, `parse_quantity`, `extract`.
- [ ] GREEN + suíte.

## Task 2 — Integração em `document_fields`

- [ ] RED: `_HTMLBlocks` expõe linhas por tabela; `CARGO|...|VAGAS` produz imediatas por cargo; contrato atual preservado (107/3, [0,0,1,2], sem `reserve`).
- [ ] Substituir a heurística de cabeçalho fixo pelo extrator genérico (HTML); manter PDF.
- [ ] GREEN + suíte.

## Task 3 — `document_store.ensure_role`

- [ ] RED: idempotente; cria `cargos_identidade` + `observacoes_cargo`; recusa concurso/observação inexistentes.
- [ ] Implementar transacional.
- [ ] GREEN + suíte.

## Task 4 — DOU texto completo

- [ ] RED: `fetch_article` extrai `texto-dou`; sem chrome; fallback para o `content` do JSON quando ausente.
- [ ] Implementar em `dou_source.py`.
- [ ] GREEN + suíte.

## Task 5 — Prova real + documentação

- [ ] `docs/superpowers/plans/2026-10-16-extracao-vagas-dou-prova-real.md` com URLs, HTTP, hashes, propostas, desconhecidos, limitações.
- [ ] README/log.

## Task 6 — Revisão independente, commit e push
