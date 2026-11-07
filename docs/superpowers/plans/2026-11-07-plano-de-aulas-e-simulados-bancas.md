# Plano de Aulas, Radiografia de Bancas e Simulados com Provas Reais — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Transform the Studies area into a comprehensive learning and exam training platform with structured lesson plans ("Plano de Aula"), banca-specific examination profiles (FGV, Cebraspe, Quadrix, IBFC), a rich bank of authentic previous exam questions with pedagogical commentary, and banca-tailored mock exams.

**Architecture:**
- **Backend (Python stdlib + SQLite):**
  - `radar/lesson_plan.py`: Lesson plan generation, syllabus structuring, banca style comparative matrix (FGV, Cebraspe, Quadrix, IBFC).
  - `radar/real_exam_questions.py`: Authentic previous exam question seeds and ingestion covering key IT & core subjects (Banco de Dados, Engenharia de Software, Redes, Português, Direito Constitucional).
  - Enhancements to `radar/practice_store.py` and `radar/server.py` exposing:
    - `GET /api/estudos/aulas`: list lesson plans grouped by discipline.
    - `GET /api/estudos/aulas/<aula_id>`: detailed lesson with theory, banca analysis, pitfalls, and targeted practice questions.
    - `GET /api/estudos/bancas`: comparative profile matrix of FGV, Cebraspe, Quadrix, IBFC.
    - `POST /api/estudos/simulados`: support `banca` filter and Cebraspe C/E scoring rules.
- **Frontend (React 19 + TanStack Query + Tailwind v4 + 21st.dev):**
  - Navigation tab: **"Plano de Aulas"** (`/estudos/aulas`) and **"Radiografia de Bancas"** (`/estudos/bancas`).
  - Interactive Lesson Viewer component with Theory summary, "Como a Banca Cobra" spotlight, and Practice Questions with detailed answer explanations.
  - Banca-tailored Mock Exam Generator letting candidates pick FGV, Cebraspe (C/E), Quadrix, or their chosen target contest.

---

### Task 1: Comparative Banca Profiles & Lesson Plan Engine

- [ ] Create test `tests/test_lesson_plan.py` covering:
  - Retrieval of banca comparative profiles (FGV, Cebraspe, Quadrix, IBFC).
  - Generation/retrieval of lesson plans for disciplines (e.g. Banco de Dados, Língua Portuguesa, Engenharia de Software).
  - Lesson structure: `id`, `disciplina`, `titulo`, `objetivos`, `teoria_resumida`, `radiografia_bancas`, `pontos_criticos`, `questoes_ids`.
- [ ] Implement `radar/lesson_plan.py` with:
  - Canonical banca intelligence profiles:
    - **FGV**: Casos práticos, enunciados longos, interpretação textual sofisticada, pegadinhas de ambiguidade, arquitetura/código em TI.
    - **Cebraspe**: Assertivas Certo/Errado com regra de 1 errada anula 1 certa, termos restritivos/absolutos ("sempre", "nunca", "exclusivamente"), jurisprudência pacificada.
    - **Quadrix**: Assertivas C/E e múltipla escolha, rigor em legislações específicas e regimentos, pegadinhas literais de troca de palavras.
    - **IBFC**: Questões diretas e pontuais, cobrança literal de texto legal, opções A-B-C-D objetivas.
  - Lesson plan catalog with structured curriculum units.
- [ ] Run `python -m unittest tests/test_lesson_plan.py` and verify all tests pass.

---

### Task 2: Real Previous Exam Question Seeds & Ingestion

- [ ] Create test `tests/test_real_exam_questions.py` covering:
  - Ingestion of real previous exam questions into `pratica_questoes`.
  - Proper tag mapping (`banca:fgv`, `banca:cebraspe`, `banca:quadrix`, `banca:ibfc`).
  - Verification of answer keys, types (`escolha_unica` vs `verdadeiro_falso`), and pedagogical comments.
- [ ] Implement `radar/real_exam_questions.py` with a curated set of real questions from:
  - FGV (TI & Português)
  - Cebraspe (TI & Constitucional)
  - Quadrix (TI & Legislação)
  - IBFC (TI & Noções de Direito)
- [ ] Wire automatic seed/sync helper into database startup or on-demand endpoint.
- [ ] Run `python -m unittest tests/test_real_exam_questions.py` and verify all tests pass.

---

### Task 3: REST API Endpoints for Lessons, Bancas & Mock Exam Filter

- [ ] Register and test routes in `radar/server.py`:
  - `GET /api/estudos/aulas`: list all lesson plans (optionally filtered by `disciplina`).
  - `GET /api/estudos/aulas/<aula_id>`: get specific lesson with related questions.
  - `GET /api/estudos/bancas`: returns profile analysis of each banca.
  - Update `POST /api/estudos/simulados` to accept `banca` filter in query/body.
- [ ] Add integration test in `tests/test_server_lessons.py` verifying HTTP 200 responses and JSON schemas.
- [ ] Run `python -m unittest tests/test_server_lessons.py`.

---

### Task 4: Frontend Types, Queries & Lesson Viewer UI

- [ ] Update `web-react/src/lib/types.ts`:
  - Add `Lesson`, `LessonSummary`, `BancaProfile`, `BancaProfilesResponse`.
- [ ] Update `web-react/src/app/queries.ts`:
  - Add `useLessons()`, `useLesson(id)`, `useBancas()`.
- [ ] Create `web-react/src/features/studies/LessonsView.tsx`:
  - Structured lesson grid/accordion by discipline.
  - Lesson detail view with rich tabs:
    1. **Teoria Resumida**: Resumo direto ao ponto do conteúdo.
    2. **Como as Bancas Cobram**: Radiografia detalhada (FGV vs Cebraspe vs Quadrix vs IBFC).
    3. **Pontos de Atenção & Pegadinhas**: Armadilhas frequentes.
    4. **Questões de Fixação**: Exercícios reais comentados.
- [ ] Create `web-react/src/features/studies/BancaRadiographyView.tsx`:
  - Interactive comparative matrix of the 4 major exam boards with tips, penalties, and subject tendencies.

---

### Task 5: Integration into Studies Page & Mock Exam Creation

- [ ] Update `web-react/src/features/studies/StudiesPage.tsx`:
  - Add tabs: `Aulas` (`/estudos/aulas`) and `Bancas` (`/estudos/bancas`).
  - In `ExamsView` (Simulados modal):
    - Add Banca selector (FGV, Cebraspe, Quadrix, IBFC, ou Qualquer Banca).
    - Warn when Cebraspe is chosen: "Modo Cebraspe: Assertivas Certo/Errado com penalidade de erro".
- [ ] Write Vitest tests in `web-react/src/features/studies/LessonsView.test.tsx` verifying:
  - Lessons listing and rendering of theory & banca analysis.
  - Interactive answering of practice questions with comment reveal.

---

### Task 6: End-to-End Verification, Build & Autonomous Push

- [ ] Run full Python test suite (`python -m unittest discover`).
- [ ] Run full Vitest suite (`npm test -- --run` in `web-react`).
- [ ] Build production assets (`npm run build` in `web-react`).
- [ ] Restart daemon server and verify endpoints.
- [ ] Autonomous Git commit and push per `AGENTS.md`.
