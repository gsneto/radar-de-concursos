# Plano — Fase 10: descoberta complementar via PCI MCP

> TDD; testes com respostas MCP de teste (sem depender da rede); prova real separada.

**Spec:** `docs/superpowers/specs/2026-10-16-pci-mcp-discovery-design.md`

## Task 1 — Cliente e conector `radar/pci_source.py`
- [x] `McpClient` (Streamable HTTP/JSON-RPC 2.0, stdlib), `parse_tool_result`.
- [x] `normalize` (metadados mínimos), `to_candidate` (documento de descoberta), `_overlap_hint`.
- [x] `discover(db_path, *, caller, queries, max_new_concursos)` → `{candidates, summary, partial, failed}`.
- [x] `pci_source(...)` (multi_contest, download_new_only).

## Task 2 — Integração
- [x] `monitoring._run_source`: `discover` pode devolver dict; `summary`/`partial`/`failed` propagados; `default_sources()` inclui PCI.

## Task 3 — Testes (`tests/test_pci_source.py`)
- [x] Cliente (initialize/tools/call/SSE/erros), parsing, normalize, discover (novos, dedup, idempotência, parcial, falha total, vazio, cap incremental, sobreposição), ciclo (estado, v1), segurança.

## Task 4 — Prova real
- [x] `docs/superpowers/plans/2026-10-16-pci-mcp-discovery-prova-real.md`.

## Task 5 — Revisão, commit, push
- [ ] Suíte completa + revisão independente + commit/push.
