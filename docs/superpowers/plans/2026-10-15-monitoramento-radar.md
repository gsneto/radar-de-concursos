# Plano — Monitoramento automático de editais e retificações

> **For agentic workers:** Steps use checkbox (`- [ ]`) syntax. Executar tarefa a tarefa com TDD (RED → GREEN). Não criar commits sem pedido explícito. Não migrar bancos reais.

**Spec:** `docs/superpowers/specs/2026-10-15-monitoramento-radar-design.md`
**Estratégia:** comando repetível `python -m radar monitor` + Agendador de Tarefas do Windows.

## Arquitetura

Novo módulo `radar/monitoring.py` orquestra um ciclo único. Persistência em duas tabelas novas (`ciclos_monitoramento`, `ciclos_fontes`) via migração aditiva `user_version=4` em `radar/document_store.py`. CLI ganha o subcomando `monitor`. `radar/server.py` ganha `GET /api/monitoramento`. `web/` ganha painel de status. Reutiliza descoberta, download, extração e revisão existentes.

## Files

- Modificar: `radar/document_store.py` (schema v4 + leitura de monitoramento).
- Criar: `radar/monitoring.py` (ciclo, classificação, persistência).
- Modificar: `radar/__main__.py` (subcomando `monitor`).
- Modificar: `radar/server.py` (rota de status).
- Modificar: `web/index.html`, `web/styles.css`, `web/app.js` (painel).
- Criar: `tests/test_monitoring.py`, `tests/test_monitoring_api.py`.
- Modificar: `tests/test_ui.py`, `README.md`, `docs/AUTONOMOUS_WORK_LOG.md`.
- Criar: `docs/MONITORING_SCHEDULING.md` (agendamento Windows).

## Task 1 — Schema v4 aditivo

- [ ] **RED:** em `tests/test_monitoring.py`, criar banco v2 temporário e banco v3 temporário; exigir que `migrate_document_schema` os leve a `user_version=4` com as tabelas `ciclos_monitoramento`/`ciclos_fontes` e colunas do contrato; migração repetida idempotente; v4 intacta; `PRAGMA integrity_check='ok'`; recusa de versão futura sem tocar o banco.
- [ ] Implementar `_V4_TABLE`, `_V4_COLUMNS`, `_apply_v4`, `SCHEMA_VERSION=4`; aceitar 0/2/3/4 em `migrate_document_schema`; leitura aceita 2/3/4.
- [ ] Rodar teste focado e suíte; conferir GREEN.

## Task 2 — Classificação de mudanças e ciclo (núcleo)

- [ ] **RED:** em `tests/test_monitoring.py`, com banco migrado, `run_cycle` com `fetch_article`/`transport` injetáveis: nenhum doc novo; um doc novo; mesma URL/mesmo conteúdo; telemetria volátil; mudança substantiva; nova retificação; doc inacessível (falha preserva sucesso anterior); timeout de fonte; erro de download; execução repetida sem alertas duplicados.
- [ ] Implementar `radar/monitoring.py`: `run_cycle(db_path, *, fetch_article=fetch_official, transport=None, analyze=False, now=None)`; recuperação de ciclo `em_andamento`; persistência ciclo+fontes; resumo. Reutilizar `discover_documents`, `register_document`, `download_document`, `record_version`.
- [ ] Rodar focado e suíte; GREEN.

## Task 3 — Análise opcional e falha de extração

- [ ] **RED:** `--analyze` sobre versão nova cria blocos/propostas e deixa `extraction_state` apropriado; falha de extração grava `falhou` + evento sem apagar versão; nada é validado automaticamente.
- [ ] Implementar análise opcional no ciclo (reutilizando `extract_blocks`/`extract_field_proposals`/`record_analysis`).
- [ ] Rodar focado e suíte; GREEN.

## Task 4 — CLI `monitor`

- [ ] **RED:** `python -m radar monitor --db` em banco não migrado falha com mensagem clara; em banco migrado executa ciclo e imprime resumo; código de saída correto.
- [ ] Adicionar subcomando `monitor` em `radar/__main__.py`.
- [ ] Rodar focado e suíte; GREEN.

## Task 5 — API de status

- [ ] **RED:** `tests/test_monitoring_api.py`: banco não migrado → `503`; após ciclos → 200 com `last_cycle`/`sources`/`pending_analysis`/`coverage_state`; sem `local_path`; bytes de `/api/concursos` idênticos antes/depois; métodos ≠ GET → 405.
- [ ] Implementar `monitoring_status(db_path)` em `document_store.py` e a rota em `server.py`.
- [ ] Rodar focado e suíte; GREEN.

## Task 6 — Interface

- [ ] **RED:** `tests/test_ui.py` exige no HTML/JS os elementos de monitoramento (última verificação, estado da fonte, novos, alterações, pendentes, falhas, cobertura não verificada) e distinção novo×técnico; responsividade preservada.
- [ ] Implementar painel em `web/index.html`, `web/styles.css`, `web/app.js` (reutilizando o padrão de estados).
- [ ] Rodar focado e suíte; GREEN.

## Task 7 — Agendamento e documentação

- [ ] Criar `docs/MONITORING_SCHEDULING.md` com instruções `schtasks`/GUI (sem habilitar tarefa).
- [ ] Atualizar `README.md` (comando e limites).
- [ ] Atualizar `docs/AUTONOMOUS_WORK_LOG.md`.

## Task 8 — Verificação final e revisão independente

- [ ] Suíte completa no venv isolado; `git diff --check`.
- [ ] Revisão independente via `task`/code-reviewer; reproduzir achados; corrigir; reexecutar suíte.
