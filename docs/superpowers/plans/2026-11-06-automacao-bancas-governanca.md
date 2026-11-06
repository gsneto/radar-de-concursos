# Automação Completa, Expansão de Bancas e Governança Git Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Integrar curadoria autônoma no ciclo operacional contínuo (`ops.py`), expor gatilho no frontend React, habilitar IBFC, criar conector para Cebraspe e consolidar a governança com merge para `main`.

**Architecture:** 
1. `radar/ops.py`: invocar `run_curation_cycle` dentro de `run_cycle`, persistindo métricas de curadoria no retorno do ciclo.
2. `web-react`: adicionar chamada à API `POST /api/curadoria/executar` e botão com status na UI (`Topbar` / `OverviewPage`), gerando novo build em `web-react/dist`.
3. `radar/ops_config.py` & configs: ativar fonte IBFC por padrão.
4. `radar/cebraspe_source.py`: implementar conector Cebraspe (HTML parsing de catálogo e páginas de concurso, classificação de tipos documentais, descoberta sem autenticação) e registrar no catálogo de fontes e monitoramento.
5. Governança: validar todos os testes (Python + Vitest), commitar, branch/merge para `main`, push para `origin` e instruções operacionais.

**Tech Stack:** Python 3.11+, SQLite3 (WAL), React 18, TypeScript, TailwindCSS, Vitest, PowerShell.

---

## Global Constraints

- Respeitar estritamente as regras de domínio de `AGENTS.md` (não inventar dados, manter evidências SHA-256 e proveniência).
- Não violar o modelo de ameaça em loopback (`127.0.0.1`) do servidor HTTP.
- Executar testes reais antes de qualquer alegação de sucesso.
- O build do frontend em `web-react/dist` deve ser recompilado e versionado.

---

## Tasks

### Task 1: Integrar Curadoria Autônoma em `radar/ops.py` e Configuração de Fontes

**Files:**
- Modify: `radar/ops.py`
- Modify: `radar/ops_config.py`
- Modify: `radar_ops.json`
- Modify: `radar_ops.json.example`
- Test: `tests/test_ops_curadoria.py`

- [ ] Escrever teste unitário `tests/test_ops_curadoria.py` validando que `run_cycle` chama a curadoria autônoma e popula `result["curation"]`.
- [ ] Modificar `radar/ops.py` para chamar `run_curation_cycle(db_path, now=now)` durante a execução do ciclo operacional.
- [ ] Atualizar `radar/ops_config.py` para incluir `"ibfc"` em `DEFAULT_SOURCES` e `DEFAULT_MIN_INTERVAL_HOURS`.
- [ ] Atualizar `radar_ops.json` e `radar_ops.json.example` ativando `"ibfc": {"enabled": true}`.
- [ ] Executar os testes unitários com Python e validar que passam.

### Task 2: Implementar Conector Oficial Cebraspe (`radar/cebraspe_source.py`)

**Files:**
- Create: `radar/cebraspe_source.py`
- Modify: `radar/source_catalog.py`
- Modify: `radar/connectors.py`
- Modify: `radar/monitoring.py`
- Test: `tests/test_cebraspe_source.py`

- [ ] Escrever testes unitários em `tests/test_cebraspe_source.py` com amostras HTML simuladas de catálogo e página de certame Cebraspe.
- [ ] Implementar `radar/cebraspe_source.py` com parsing de catálogo (`/concursos/`), páginas individuais de certame, extração de links de editais/retificações/comunicados e classificação tipológica.
- [ ] Registrar fonte `cebraspe` em `radar/source_catalog.py` (com política de armazenamento de metadados e documentos públicos).
- [ ] Registrar conector em `radar/connectors.py` e adicionar aos `default_sources()` em `radar/monitoring.py`.
- [ ] Executar `pytest`/`unittest` para validar 100% de aprovação no novo conector.

### Task 3: Gatilho de Curadoria na Interface React (`web-react`)

**Files:**
- Modify: `web-react/src/lib/api.ts`
- Modify: `web-react/src/components/topbar.tsx` (ou componente adjacente)
- Test: `web-react/src/components/ui.test.tsx` ou teste específico
- Build: `web-react/dist`

- [ ] Adicionar função `executeCuradoria(dryRun?: boolean)` em `web-react/src/lib/api.ts`.
- [ ] Adicionar botão "Executar Curadoria" com estado de carregamento e exibição de feedback (badge / toast de total de decisões tomadas) na interface React.
- [ ] Escrever / atualizar teste Vitest para cobrir o gatilho de curadoria na UI.
- [ ] Rodar `npm test` em `web-react` para validar todos os testes do frontend.
- [ ] Rodar `npm run build` para regerar os arquivos estáticos de produção em `web-react/dist`.

### Task 4: Verificação Completa e Governança Git (Merge para `main`)

**Files:**
- Test: Suíte completa Python (`python -m unittest discover -s tests -t .`)
- Test: Suíte completa React (`npm test` no `web-react`)
- Git: Commit das alterações na branch `radar-configuracao`
- Git: Push para `origin/radar-configuracao`
- Git: Criação e merge na branch `main`
- Git: Push de `main` para `origin/main`

- [ ] Executar toda a suíte de testes Python e Vitest.
- [ ] Commitar alterações na branch `radar-configuracao` e fazer push.
- [ ] Criar branch `main`, sincronizar com `radar-configuracao` e fazer push para `origin/main`.
- [ ] Retornar para a branch de trabalho configurada.
- [ ] Entregar relatório final com status e instruções de agendamento/notificações.
