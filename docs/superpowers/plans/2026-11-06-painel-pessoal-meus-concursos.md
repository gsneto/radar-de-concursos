# Painel Pessoal "Meus Concursos" — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Transform the GSN Concursos application into a personal candidate focus dashboard where the user tracks their chosen target competitions, monitors countdown deadlines, and studies directly for them.

**Architecture:**
- **Backend (SQLite + stdlib HTTP):** New table `meus_concursos`, python module `radar/my_contests.py`, endpoints `GET /api/meus-concursos`, `POST /api/meus-concursos`, `DELETE /api/meus-concursos/<contest_id>`.
- **Frontend (React 19 + TanStack Query):**
  - New landing view `MyContestsPage` mounted at `/`.
  - Empty state with "Buscar Concursos no Radar" CTA button leading to `/oportunidades`.
  - Selected state with 21st.dev Glow Cards displaying contest info, salary, vacancies, countdown timers, and "Estudar para este Concurso" action button.
  - "Favoritar / Selecionar" toggle on every opportunity in `OpportunitiesPage` (`OpportunityGlowCard` and table view).
  - Deep-link integration with `StudiesPage` filtering content to the chosen competition.

---

### Task 1: Backend Persistence & API for "Meus Concursos"

- [ ] Create test `tests/test_my_contests.py` covering:
  - Table initialization `meus_concursos` (id, contest_id, role_id, selected_at, status, notes).
  - Adding a contest to "Meus Concursos" (`add_my_contest`).
  - Listing selected contests with enriched contest/role/deadline details (`list_my_contests`).
  - Removing a contest (`remove_my_contest`).
  - Idempotency on adding the same contest twice.
- [ ] Implement `radar/my_contests.py` with the storage operations.
- [ ] Register routes in `radar/server.py`:
  - `GET /api/meus-concursos`: returns `{ total: int, items: list[dict] }`
  - `POST /api/meus-concursos`: accepts `{ contest_id: str, role_id?: str, notes?: str }`
  - `DELETE /api/meus-concursos/<contest_id>`: deletes or archives the selection.
- [ ] Run `python -m unittest tests/test_my_contests.py` and verify all tests pass.

---

### Task 2: Frontend Data Layer & Types

- [ ] Update `web-react/src/lib/types.ts` with `MyContest` interface:
  - `contest_id: string`, `contest_label: string`, `role_name?: string`, `remuneracao?: string | number`, `vagas?: number`, `proxima_data?: string`, `proximo_evento?: string`, `dias_restantes?: number`, `selected_at: string`.
- [ ] Update `web-react/src/app/queries.ts`:
  - Add query hook `useMyContests()`.
  - Add mutation hook `useToggleMyContest()`.
  - Update `keys.myContests = () => ['my-contests'] as const`.
- [ ] Update `web-react/src/lib/api.test.ts` to verify mock calls for `/api/meus-concursos`.

---

### Task 3: Selection Toggle in "Oportunidades" (`/oportunidades`)

- [ ] In `web-react/src/components/21st/opportunity-glow-card.tsx`:
  - Add a Bookmark / Star button: "Selecionar" / "Selecionado".
  - Distinct active visual state (highlighted glow / amber star icon).
- [ ] In `web-react/src/features/opportunities/OpportunitiesPage.tsx`:
  - Integrate `useMyContests()` and `useToggleMyContest()`.
  - Add star toggle in table row view and cards view.
  - Add quick filter pill: "Meus Selecionados".
- [ ] Update `OpportunitiesPage.test.tsx` to verify toggling selection.

---

### Task 4: Personal Dashboard View "Meus Concursos" (`/`)

- [ ] Create `web-react/src/features/my-contests/MyContestsPage.tsx`:
  - **Empty State:**
    - Elegant 21st.dev style hero card.
    - Title: "Seu Painel de Foco está Vazio".
    - Description: "O Radar monitora os concursos oficiais do Brasil para você. Selecione os certames que você vai prestar para acompanhar prazos e montar seu plano de estudos."
    - Prominent action button with Compass/Search icon: **"Buscar Concursos no Radar"** -> navigates to `/oportunidades`.
  - **Populated State:**
    - Header with summary: "X concursos no seu foco".
    - Action button: "+ Adicionar mais concursos".
    - Grid of 21st.dev `GlowCard` for each selected contest:
      - Title and Official Organ
      - Canonical Role and Salary (e.g. R$ 16.034,70)
      - Countdown badge (e.g. *Inscrições em 27 dias* / *Prova em 60 dias*)
      - Action: **"Estudar para este Concurso"** (links to `/estudos?concurso=<contest_id>`)
      - Secondary action: "Ver Dossiê" and "Remover do Painel".
- [ ] Create `web-react/src/features/my-contests/MyContestsPage.test.tsx` verifying:
  - Renders empty state and CTA button when no contests selected.
  - Clicking CTA navigates to `/oportunidades`.
  - Renders selected contest cards with actions when populated.

---

### Task 5: Routing & Sidebar Navigation Alignment

- [ ] In `web-react/src/app/router.tsx`:
  - Set `MyContestsPage` as the default element at `/`.
  - Move previous analytics overview to `/visao-geral` or secondary tab.
- [ ] In `web-react/src/app/sidebar.tsx`:
  - Update navigation item order:
    1. **Meus Concursos** (`/`, icon: Target / BookmarkCheck)
    2. **Radar de Oportunidades** (`/oportunidades`, icon: Compass / Radar)
    3. **Prazos & Calendário** (`/prazos`, icon: Calendar)
    4. **Estudos & Editais** (`/estudos`, icon: BookOpen)
- [ ] In `web-react/src/features/studies/StudiesPage.tsx`:
  - Support `?concurso=<contest_id>` to filter/highlight disciplines belonging to that selected contest.

---

### Task 6: End-to-End Verification, Build & Autonomous Push

- [ ] Run backend unit tests: `python -m unittest discover -s tests -p "test_*.py"`.
- [ ] Run frontend unit tests: `npm test -- --run` in `web-react`.
- [ ] Run frontend production build: `npm run build` in `web-react`.
- [ ] Verify live server at `http://127.0.0.1:8000/`.
- [ ] Autonomous commit & push per `AGENTS.md`.
