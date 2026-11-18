# Diretório Estilo PCI, ~350 Organizadoras, Acervo de Provas, Progresso por Etapa & Dashboard de Histórico Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans and superpowers:test-driven-development to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Unir a organização rápida estilo PCI Concursos (~350 organizadoras A–Z, atalhos por região/carreira, tabela de provas anteriores e índice de simulados por matéria em 1 clique — com foco profundo em TI e superfície expansível nas demais áreas) a um rastreador de porcentagem por etapa em cada aula (0%–100%) e um dashboard visual completo com todo o histórico de estudo do aluno.

**Architecture:** Implementação nativa sobre o backend Python 3.12 stdlib + SQLite + `pymupdf` (`radar/`) e a SPA React 19 + TypeScript + Tailwind v4 (`web-react/`), sem novas dependências externas. Novas rotas (`GET /api/organizadoras`, `GET/POST /api/estudos/provas`) são sincronizadas em `radar/api_contract.py`; o progresso granular das 5 etapas de cada aula e a trilha cronológica de ações do estudante usam `useUserStorage` (`ready = !authMe.isLoading`) combinado às tabelas `estudo_sessoes`, `pratica_tentativas` e `pratica_simulados` do servidor.

**Tech Stack:** Python 3.12, SQLite 3, `pymupdf`, React 19, TypeScript 5.9, Vite 7, TanStack Query 5, Tailwind CSS 4, Vitest + Testing Library.

**Spec:** `AGENTS.md` e `docs/superpowers/specs/2026-10-22-frontend-react-observatorio-design.md`

## Global Constraints

- Respeitar `source_policy.py` e `AGENTS.md`: zero scraping de bancos comerciais de questões ou textos editoriais; persistir apenas metadados factuais de descoberta e atos públicos oficiais (editais, provas públicas e gabaritos oficiais).
- Manter foco profundo em **TI / Sistemas de Informação + matérias básicas** e estrutura superficial categorizada por `carreira` (`ti`, `administrativa`, `fiscal`, `tribunais`, `policial`, `educacao`) pronta para expansão.
- Contraste WCAG AA (`>= 4.5:1`) tanto no tema escuro quanto em `html.light` (usar `text-accent-ink`, `text-ok-ink`, `text-info-ink`, `text-risk-ink`).
- Isolamento estrito por usuário (`user_id` no SQLite e `useUserStorage(..., userId, ..., !authMe.isLoading)` no navegador).
- Sincronizar qualquer rota nova em `radar/api_contract.py` (`python -m radar api-contrato --verificar` = `ok: true`) e manter `web-react/dist` atualizado (`npm --prefix web-react run build`).

## Review Focus

- Nomes alternativos de bancas (`CESPE` vs `Cebraspe`, `AOCP` vs `Instituto AOCP`) reconciliados sem duplicar contagens.
- Porcentagem da aula calculada exatamente sobre as 5 etapas (`0%`, `20%`, `40%`, `60%`, `80%`, `100%`) e sincronizada com a conclusão da aula ao atingir `100%`.
- Isolamento total entre alunos no progresso por etapa e no histórico de atividades (`Alice` nunca vê etapas nem histórico de `Bob`).
- Simulado em 1 clique por matéria ou por prova anterior nunca falha silenciosamente quando uma carreira superficial ainda tem `0` questões extraídas (desabilita o botão com indicação clara `"Em expansão"`).
- Nenhuma métrica ou sequência de dias inventada no Dashboard de Evolução: `0` atividades exibe estado vazio honesto.

---

### Task 1: Catálogo de ~350 Organizadoras, Acervo/Extrator de Provas Anteriores & Consultas PCI Expandidas

**Files:**
- Create: `radar/organizers_catalog.py`
- Create: `radar/exam_papers.py`
- Modify: `radar/real_exam_questions.py`
- Modify: `radar/pci_source.py`
- Modify: `radar/server.py`
- Modify: `radar/api_contract.py`
- Test: `tests/test_organizers_and_exam_papers.py`

**Interfaces:**
- Produces:
  - `GET /api/organizadoras?q=&grupo=&letra=&com_raio_x=` → `{ total, grupos, itens: [{ slug, nome, grupo, uf, pci_url, aliases, tem_raio_x_ti, raio_x_id, concursos_count, provas_count, questoes_count }] }`
  - `GET /api/estudos/provas?q=&banca=&carreira=&ano=` → `{ total, por_carreira, itens: [{ id, titulo, cargo, orgao, banca_slug, banca_nome, ano, nivel, carreira, edital_ou_prova_url, gabarito_url, questoes_count }] }`
  - `POST /api/estudos/provas` (admin) → cadastra prova oficial e opcionalmente extrai questões de `texto_prova` + `texto_gabarito`.

### Task 2: Diretório Rápido Estilo PCI no Radar (`/oportunidades`) & Catálogo A–Z de ~350 Organizadoras (`/estudos/bancas`)

**Files:**
- Create: `web-react/src/features/opportunities/PciQuickDirectoryBar.tsx`
- Modify: `web-react/src/features/opportunities/OpportunitiesPage.tsx`
- Create: `web-react/src/features/studies/OrganizersDirectorySection.tsx`
- Modify: `web-react/src/features/studies/BancaRadiographyView.tsx`
- Modify: `web-react/src/app/queries.ts`
- Modify: `web-react/src/lib/types.ts`
- Test: `web-react/src/features/studies/LessonsView.test.tsx` & `OpportunitiesPage.test.tsx`

### Task 3: Aba `Provas Anteriores` Estilo PCI & Índice de `Simulados por Matéria` em 1 Clique

**Files:**
- Create: `web-react/src/features/studies/tabs/ExamPapersTab.tsx`
- Modify: `web-react/src/features/studies/tabs/ExamsSimulationTab.tsx`
- Modify: `web-react/src/features/studies/StudiesPage.tsx`
- Modify: `web-react/src/app/nav.ts`
- Test: `web-react/src/features/studies/StudiesPage.test.tsx`

### Task 4: Porcentagem por Etapa da Aula (0%–100%) & Registro Estruturado de Atividades

**Files:**
- Create: `web-react/src/lib/lesson-progress.ts`
- Create: `web-react/src/lib/lesson-progress.test.ts`
- Modify: `web-react/src/features/studies/lessons/LessonWorkspaceShell.tsx`
- Modify: `web-react/src/features/studies/lessons/LessonCatalogView.tsx`
- Modify: `web-react/src/features/studies/LessonsView.tsx`
- Test: `web-react/src/features/studies/LessonsView.test.tsx`

### Task 5: Dashboard de Evolução & Histórico Completo de Tudo o que o Aluno Fez (`/estudos/evolucao` & `/historico`)

**Files:**
- Create: `web-react/src/features/studies/tabs/StudentJourneyDashboard.tsx`
- Modify: `web-react/src/features/studies/StudiesPage.tsx`
- Modify: `web-react/src/features/history/HistoryPage.tsx`
- Modify: `web-react/src/app/nav.ts`
- Test: `web-react/src/features/studies/StudentJourneyDashboard.test.tsx`
