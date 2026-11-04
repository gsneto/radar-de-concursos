# Cobertura de Testes (Python + React) — Fase 47

Data de verificação: **2026-11-04** (`America/Recife`).
Branch: `radar-configuracao`.

---

## 1. Resumo Executivo

| Camada | Arquivos de Teste | Total de Testes | Status | Tempo de Execução |
|---|---:|---:|---|---:|
| **Backend Python (`tests/`)** | 85 arquivos (`test_*.py`) | **1.898 testes** (1 skipped condicional) | **100% PASS** (em `.venv`) | ~201 s |
| **Frontend React (`web-react/src/`)** | 16 arquivos (`*.test.ts` / `*.test.tsx`) | **103 testes** | **100% PASS** (`vitest run`) | ~12 s |
| **Total Combinado** | **101 arquivos de teste** | **2.001 testes automatizados** | **100% PASS** | ~213 s |

> **Importante (Ambiente Python):** Execute sempre a suíte Python usando `.\.venv\Scripts\python.exe`. O Python global do sistema não possui `pypdf` nem `pymupdf` instalados, o que causaria 35 erros de importação nos testes de extração de PDF e OCR.

---

## 2. Cobertura do Frontend React (`web-react/src/`) — Antes vs. Depois da Fase 47

### 2.1 Cobertura por Página (`src/features/`)

| Página (`src/features/*`) | Rota na SPA | Antes da Fase 47 | Depois da Fase 47 | Cenários Cobertos (Dados, Vazio, Erro, A11y) |
|---|---|---|---|---|
| `OverviewPage.tsx` | `/` | Sem teste dedicado | **`OverviewPage.test.tsx` (3 testes)** | KPIs (`aria-label="Indicadores"`), funil de cobertura, oportunidades prioritárias, prazos próximos, estados vazios e retry de erro HTTP. |
| `OpportunitiesPage.tsx` | `/oportunidades` | Sem teste dedicado | **`OpportunitiesPage.test.tsx` (3 testes)** | Tabela/cards, busca (`role="searchbox"`), filtros por UF, toggle de filtros avançados (`aria-expanded`), chips de filtro ativo e remoção, estado vazio e erro. |
| `DeadlinesPage.tsx` | `/prazos` | Sem teste dedicado | **`DeadlinesPage.test.tsx` (3 testes)** | KPIs (`aria-label="Resumo de prazos"`), `role="tablist"` (`Próximos`, `Mais adiante`, `Vencidos`, `Sem data`), toggle de detalhes (`aria-expanded`), estado vazio e erro. |
| `DossierPage.tsx` | `/dossie/:contestId` | Sem teste dedicado | **`DossierPage.test.tsx` (2 testes)** | Cabeçalho do certame, `role="tablist"` (`Resumo`, `Cargo e requisitos`, `Vagas e modalidades`, `Prazos`, `Localização`, `Documentos`, `Evidências`), troca de aba e erro 404. |
| `ReviewPage.tsx` | `/revisao` | `ReviewPage.test.tsx` (5 testes) | **`ReviewPage.test.tsx` (5 testes)** | Trecho de evidência, validação aritmética, bloqueio sem autor/justificativa, envio de `evidence_sha256` + `scope_snapshot`, persistência de revisor. |
| `MesaPage.tsx` | `/mesa` | `MesaPage.test.tsx` (5 testes) | **`MesaPage.test.tsx` (5 testes)** | Listagem por oportunidade, filtros por campo/conflito/estado documental, link para dossiê e mesa de revisão. |
| `IdentityPage.tsx` | `/identidades` | `IdentityPage.test.tsx` (4 testes) | **`IdentityPage.test.tsx` (4 testes)** | Sugestão estrutural de cargo, bloqueio sem responsável/justificativa, envio de decisão append-only (`dry_run: false`), aba de conflitos. |
| `PipelinePage.tsx` | `/pipeline` | `PipelinePage.test.tsx` (5 testes) | **`PipelinePage.test.tsx` (5 testes)** | Etapas do pipeline, primeiro bloqueio por documento, filtro de pendentes, cobertura por concurso. |
| `StudiesPage.tsx` | `/estudos/*` | Sem teste dedicado | **`StudiesPage.test.tsx` (2 testes)** | KPIs (`aria-label="Indicadores de estudo"`), `role="tablist"` (`Visão geral`, `Sessões`, `Questões`, `Flashcards`, `Simulados`), distribuição por disciplina, estados vazios e erro. |
| `SettingsPage.tsx` | `/configuracoes` | Sem teste dedicado | **`SettingsPage.test.tsx` (3 testes)** | Formulário de preferências (`Paulo Afonso`, `BA`, `BA, PE`, `300 km`), submissão `POST /api/preferencias`, preferência de barra lateral no `localStorage` e estado de erro. |
| `HistoryPage.tsx` / `DiagnosticsPage.tsx` | `/historico`, `/operacao` | Cobertos via componentes/contrato | Cobertos via componentes/contrato | Consultas de leitura (`useTimeline`, `/api/saude`, `/api/fontes`). |

### 2.2 Cobertura de Componentes e Utilitários (`src/components/`, `src/lib/`, `src/styles/`)

- `src/components/ui/ui.test.tsx` (**7 testes**): `ErrorState`, `EmptyState`, `Badge`, `Button`, `Card`, `Kpi`.
- `src/lib/api.test.ts` (**11 testes**): cliente HTTP, serialização de query string, tratamento de erros JSON.
- `src/lib/deadlines.test.ts` (**12 testes**): recorte de grupos operacionais (`OPERATIONAL_GROUPS`) e janela de 30 dias.
- `src/lib/domain.test.ts` (**6 testes**): mapeamento de rótulos e tons semânticos de prontidão, SI e reserva indígena.
- `src/lib/format.test.ts` (**19 testes**): formatação de datas sem deslocamento de fuso, durações, números e URLs seguras (`safeUrl`).
- `src/styles/tokens.test.ts` (**13 testes**): verificação matemática de contraste WCAG AA ($\ge 4,5:1$) para os tokens de cor do tema escuro.

---

## 3. Cobertura do Backend Python (`radar/` e `tests/`)

Todos os **92 módulos** em `radar/` possuem cobertura direta ou indireta nos **85 arquivos de teste** em `tests/`:

- **Domínio de Cobertura, Extração e Quadros**: `test_document_extract.py`, `test_document_extract_pdf.py`, `test_document_extract_real.py`, `test_vacancy_tables.py`, `test_vacancy_columns_f41.py`, `test_quadrix_vacancies.py`, `test_multipage.py`, `test_ocr_and_extraction.py`, `test_coverage_consolidation_f47.py`.
- **Elegibilidade, SI, Reserva Indígena e Carteira**: `test_eligibility_f38.py`, `test_eligibility_f39.py`, `test_indigenous_scope_f40.py`, `test_portfolio_f36.py`, `test_priority.py`, `test_geography.py`.
- **Prazos, Conflitos e Revisão Humana**: `test_deadline_audit_f37.py`, `test_review.py`, `test_review_api.py`, `test_review_groups_f42.py`, `test_pilot_f43.py`, `test_role_identity_f35.py`, `test_role_reconciliation.py`.
- **Fontes, Conectores, Orçamento e Operação**: `test_sources.py`, `test_fgv_source.py`, `test_quadrix_source.py`, `test_dou_source.py`, `test_ibfc_source.py`, `test_pci_source.py`, `test_monitoring.py`, `test_ops.py`, `test_notifications.py`.
- **Servidor HTTP, Segurança, Contrato API e Entrega SPA**: `test_server.py`, `test_contract.py`, `test_backend_gate_f44.py`, `test_frontend_react_f46.py`, `test_coverage_consolidation_f47.py`.
- **Módulo de Estudos e Prática**: `test_study.py`, `test_knowledge_api.py`, `test_practice.py`, `test_flashcards.py`, `test_questions.py`, `test_exams.py`, `test_packages.py`, `test_media.py`, `test_study_backup.py`.

---

## 4. Como Reproduzir

```powershell
# 1. Suíte completa Python (usando a .venv do projeto)
.\.venv\Scripts\python.exe -m unittest discover -s tests -t .

# 2. Suíte Fase 47 (consolidação, geografia, despacho GET e hardening HTTP)
.\.venv\Scripts\python.exe -m unittest tests.test_coverage_consolidation_f47

# 3. Verificação de tipos e suíte React (Vitest)
cd web-react
npx tsc -b
npm test
```
