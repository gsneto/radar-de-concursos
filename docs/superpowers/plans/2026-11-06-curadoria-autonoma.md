# Curadoria Autônoma e Resolução de Dados Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implementar o motor de curadoria autônoma (`radar.autonomous_curator`) e integrá-lo à CLI e API para auditar, reconciliar e confirmar dados de concursos sem intervenção humana manual, promovendo oportunidades para `informacao_confirmada`.

**Architecture:** Módulo Python determinístico que consome a fila de propostas e rótulos não reconciliados, aplica regras de classificação de não-cargos, resolução cronológica de retificações, verificação aritmética de vagas e formação de SI, gravando decisões append-only em `revisoes_campo`, `reconciliacoes_cargo` e `valores_atuais`.

**Tech Stack:** Python 3.11+, SQLite3 (schema v21), `radar.review`, `radar.role_identity`, `radar.portfolio`.

**Spec:** `docs/superpowers/specs/2026-11-06-curadoria-autonoma-design.md`

---

## Global Constraints
- Nenhuma alteração pode violar as regras de `AGENTS.md` (zero de inventar vagas, preservar evidência literal e SHA256).
- Não realizar migração de schema (permanecer estritamente no schema SQLite v21).
- Toda decisão deve ser append-only com `reviewer="agente_autonomo"`, `origin="cli"` e justificativa explícita.
- Executar comandos Python sempre via `.\.venv\Scripts\python.exe`.
- Manter 100% dos testes existentes (1.898 Python + 103 React Vitest) verdes.

---

## Review Focus
1. Classificação segura de não-cargos (rejeição em `reconciliacoes_cargo` sem afetar cargos reais de TI ou certames jurídicos).
2. Resolução cronológica precisa (garantir que a retificação oficial mais recente vença, e versões obsoletas sejam rejeitadas com motivo).
3. Deduplicação honesta de propostas com a mesma evidência literal.
4. Idempotência estrita: reexecutar o ciclo no mesmo banco não pode gerar decisões concorrentes ou corromper o estado.
5. Transição real da carteira operacional (`radar.portfolio`) de pendências para `informacao_confirmada`.

---

## Tarefa 1: Módulo `radar/autonomous_curator.py` com testes (TDD)
- [ ] Criar teste de caracterização e regras em `tests/test_autonomous_curator.py` testando:
  - Rejeição determinística de não-cargos (`conteúdo programático`, `local de prova`).
  - Reconciliação canônica de cargo existente e criação de cargo legítimo de TI.
  - Resolução de conflito de prazo (data mais recente de retificação prevalece).
  - Deduplicação de propostas e validação aritmética de vagas.
  - Validação de formação em Sistemas de Informação com evidência textual.
  - Idempotência de ciclo completo (`run_curation_cycle`).
- [ ] Implementar `radar/autonomous_curator.py` com as funções:
  - `curate_non_roles(db_path, *, dry_run=False, limit=1000)`
  - `reconcile_canonical_roles(db_path, *, dry_run=False, limit=1000)`
  - `curate_deadlines_chronology(db_path, *, dry_run=False, limit=1000)`
  - `curate_vacancies_arithmetic(db_path, *, dry_run=False, limit=1000)`
  - `curate_formation_si(db_path, *, dry_run=False, limit=1000)`
  - `run_curation_cycle(db_path, *, dry_run=False, limit=1000)`
- [ ] Rodar `pytest tests/test_autonomous_curator.py` e garantir 100% de aprovação.

## Tarefa 2: Subcomando da CLI em `radar/__main__.py`
- [ ] Adicionar parser e handler `curadoria-autonoma` em `radar/__main__.py` com suporte a `--dry-run`, `--limite` e `--config`.
- [ ] Escrever teste CLI em `tests/test_cli_curadoria.py` (ou integrá-lo a teste existente) verificando execução e saída JSON estruturada.
- [ ] Rodar suíte completa de testes da CLI.

## Tarefa 3: Endpoint HTTP em `radar/server.py` e Contrato de API
- [ ] Adicionar rota declarativa `POST /api/curadoria/executar` em `_POST_DISPATCH` de `radar/server.py`.
- [ ] Atualizar inventário em `radar/api_contract.py` e `docs/API.md`.
- [ ] Escrever teste de rota em `tests/test_server_curadoria.py`.

## Tarefa 4: Execução na base real `data/radar.sqlite3` e Auditoria de Resultados
- [ ] Fazer backup de segurança de `data/radar.sqlite3`.
- [ ] Executar `python -m radar curadoria-autonoma` no banco real.
- [ ] Inspecionar as métricas resultantes (`revisoes_campo`, `valores_atuais`, `reconciliacoes_cargo` e estados da carteira operacional).
- [ ] Verificar a transição de oportunidades para `informacao_confirmada`.

## Tarefa 5: Documentação, Verificação Completa e Publicação Git
- [ ] Documentar o fluxo em `docs/AUTONOMOUS_CURATOR.md` com exemplos e métricas antes vs. depois.
- [ ] Atualizar `docs/BACKEND_INVENTORY.md` e `README.md`.
- [ ] Executar toda a suíte de testes Python (`pytest`) e frontend React (`npm test`).
- [ ] Conferir diff, criar commit descritivo e fazer push para `radar-configuracao` seguindo a política de autonomia.
