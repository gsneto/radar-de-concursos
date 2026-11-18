# Evolução de Arquitetura, Design System & UX do Frontend Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Elevar o frontend React (`web-react/`) ao padrão comercial SaaS AA+ eliminando monólitos de >1.600 linhas, corrigindo contrastes do tema claro, removendo telemetria sintética em favor de métricas reais auditáveis, zerando re-renderizações de mousemove, isolando `localStorage` por usuário e otimizando o peso das imagens de flashcards.

**Architecture:** Mantém a SPA React 19 + Vite 7 + TanStack Query v5 + Tailwind v4 servida estaticamente por `radar/server.py` (`web-react/dist` versionado), decompondo views gigantes por responsabilidade funcional dentro de `src/features/studies/`, centralizando persistência local escopada por `user_id` em `src/lib/user-storage.ts`, padronizando modais acessíveis com `@radix-ui/react-dialog` (já instalado no `package.json`) e garantindo contraste WCAG ≥ 4.5:1 via testes automatizados sobre `tailwind.css`.

**Tech Stack:** React 19, TypeScript 5.9, Vite 7, TanStack React Query 5, Tailwind CSS 4, `@radix-ui/react-dialog`, Vitest 3 + Testing Library, Python 3.12 (`Pillow` opcional / script CLI para conversão WebP).

**Spec:** `docs/superpowers/specs/2026-10-22-frontend-react-observatorio-design.md` e `AGENTS.md`

## Global Constraints

- Distinguir vagas imediatas de cadastro de reserva; local de prova de local de exercício; zero de valor desconhecido (`—` / `Não informado`).
- Não apresentar informação antiga como atual; não inventar vagas, datas, latências em milissegundos ou contagens estáticas fictícias (`AGENTS.md`).
- Contraste mínimo WCAG AA ≥ 4.5:1 para todo texto normal (`fg`, `fg-2`, `fg-3`) contra todas as superfícies (`bg`, `surface`, `surface-2`, `surface-3`) **tanto no tema escuro (`@theme`) quanto no tema claro (`html.light`)**.
- `web-react/dist/` é versionado no Git (`!web-react/dist/` em `.gitignore`) e validado por `tests/test_frontend_react_f46.py`; toda tarefa que altera `web-react/src` deve rodar `npm --prefix web-react run build` antes do commit.
- Nenhum `fetch` direto fora de `web-react/src/lib/api.ts`; nenhuma dependência NPM nova além das já presentes em `web-react/package.json`.
- Chunks JS individuais de produção devem permanecer abaixo de `500 kB` (`chunkSizeWarningLimit: 500` em `vite.config.ts`).

## Review Focus

- Alternância de tema claro (`html.light`) sobre cartões pedagógicos e badges: textos amarelos/cianos/ardósia nunca podem ficar ilegíveis sobre fundo `#ffffff` ou `#f1f5f9`.
- Troca de conta no mesmo navegador (`Alice` faz logout e `Bob` entra): nenhum estado de `localStorage` (aulas concluídas, capítulos vistos, notas de vídeo, blocos do cronograma ou favoritos) de `Alice` pode aparecer para `Bob`.
- Duplo cronômetro concorrente: iniciar estudo dentro de uma aula (`LessonsView`) deve refletir a mesma sessão real de `/api/estudos/sessoes` exibida em `/estudos/sessoes`, nunca um `setInterval` fantasma descartado ao fechar a aba.
- Teclado e leitor de tela em modais (`Lightbox` de flashcards e `Criar Aula`): `Tab` fica preso dentro do diálogo (focus trap), `Escape` fecha e devolve o foco ao botão acionador.
- Banco recém-criado com `0` concursos monitorados ou `0` sessões: painéis da `OverviewPage` e `MyContestsPage` exibem zero/estado vazio honesto sem gráficos ou contadores simulados.

---

## Mapa de Arquivos (File Structure)

- **Design System & Contraste (Task 1)**
  - Modify: `web-react/src/styles/tailwind.css` — ajustar `--color-fg-3` no tema claro (`#475569`) e criar tokens semânticos de destaque (`--color-accent-ink`, `--color-ok-ink`, `--color-info-ink`, `--color-danger-ink`) legíveis nos dois temas.
  - Modify: `web-react/src/styles/tokens.test.ts` — expandir a matriz de contraste 4.5:1 para cobrir o bloco `html.light`.
- **Performance de Renderização & Layout de Cartões (Task 2)**
  - Modify: `web-react/src/components/21st/glow-card.tsx` — trocar `useState({ x, y })` a 60fps por CSS custom properties (`--glow-x`, `--glow-y`) via `useRef` + `contentClassName`.
  - Modify: `web-react/src/components/21st/opportunity-glow-card.tsx` — eliminar o double-padding (`p-5` + `p-4`) e `hover:bg-white/[0.04]` invisível no modo claro.
  - Create: `web-react/src/components/21st/glow-card.test.tsx` — testar atualização de variáveis CSS sem re-render dos filhos.
- **Honestidade de Domínio na Visão Geral (Task 3)**
  - Create: `web-react/src/features/overview/ObservatoryHealthBento.tsx` — substituir `RadarBento` por 3 cartões alimentados exclusivamente por `Coverage`, `Timeline` e `Portfolio` reais.
  - Delete: `web-react/src/components/21st/radar-bento.tsx` — remover simulação `Math.random()` de pings/latência e terminal falso.
  - Modify: `web-react/src/features/overview/OverviewPage.tsx` e `web-react/src/features/overview/OverviewPage.test.tsx`.
- **Isolamento Local Multiusuário & Diálogo Acessível Radix (Task 4)**
  - Create: `web-react/src/lib/user-storage.ts` + `web-react/src/lib/user-storage.test.ts` — helper `useUserStorage<T>(key, initialValue, userId)` com namespace `radar:u:${userId || 'local'}:${key}` e migração suave da chave legada para o perfil local (`''`).
  - Create: `web-react/src/components/ui/dialog.tsx` + `web-react/src/components/ui/dialog.test.tsx` — wrapper enxuto sobre `@radix-ui/react-dialog`.
  - Modify: `web-react/src/features/studies/JottaFlashcardView.tsx` e `web-react/src/features/studies/StudyScheduleView.tsx` — adotar `ModalDialog` e `useUserStorage`.
- **Decomposição Modular de `LessonsView` & `StudiesPage` + Cronômetro Unificado (Task 5)**
  - Create: `web-react/src/features/studies/lessons/LessonCatalogView.tsx`
  - Create: `web-react/src/features/studies/lessons/LessonTheoryStage.tsx`
  - Create: `web-react/src/features/studies/lessons/LessonVisualStage.tsx`
  - Create: `web-react/src/features/studies/lessons/LessonVideoStage.tsx`
  - Create: `web-react/src/features/studies/lessons/LessonPracticeStage.tsx`
  - Create: `web-react/src/features/studies/lessons/LessonTutorDrawer.tsx`
  - Create: `web-react/src/features/studies/tabs/StudyOverviewTab.tsx`
  - Create: `web-react/src/features/studies/tabs/SessionsTimerTab.tsx`
  - Create: `web-react/src/features/studies/tabs/QuestionsPracticeTab.tsx`
  - Create: `web-react/src/features/studies/tabs/FlashcardsDeckTab.tsx`
  - Create: `web-react/src/features/studies/tabs/ExamsSimulationTab.tsx`
  - Modify: `web-react/src/features/studies/LessonsView.tsx` (reduzir de ~2.088 para ~220 linhas orquestradoras) e `web-react/src/features/studies/StudiesPage.tsx` (reduzir de ~1.640 para ~190 linhas).
- **Otimização WebP dos Flashcards IA & Onboarding Guiado do Aluno (Task 6)**
  - Create: `scripts/optimize_flashcard_assets.py` — gera versões `.webp` otimizadas (`quality=82`, largura máx `1080px`) ao lado dos `.jpg` em `web-react/public/flashcards/`.
  - Modify: `radar/server.py` (confirmar `.webp` em `_CONTENT_TYPES`), `web-react/src/features/studies/JottaFlashcardView.tsx` e `web-react/src/features/account/PlansAndAuthPage.tsx` — usar `<picture><source srcSet="...webp" type="image/webp" /><img ... /></picture>`.
  - Create: `web-react/src/features/my-contests/StudentOnboardingChecklist.tsx` + teste em `MyContestsPage.test.tsx` — checklist real de 3 passos (1. Escolher Concurso Foco → 2. Gerar/Abrir Ciclo Semanal → 3. Concluir 1ª Aula ou Revisão SM-2).

---

### Task 1: Contraste WCAG AA do Tema Claro & Tokens Semânticos de Tonalidade

**Files:**
- Modify: `web-react/src/styles/tailwind.css:50-67,183-221`
- Modify: `web-react/src/styles/tokens.test.ts:1-61`

**Interfaces:**
- Produces: CSS tokens `--color-fg-3` ajustado em `html.light` (`#475569`, contraste ≥ 5.7:1 sobre `surface-3` `#e2e8f0`) e tokens semânticos `--color-accent-ink`, `--color-ok-ink`, `--color-info-ink`, `--color-risk-ink` em `@theme` e `html.light`.

- [ ] **Step 1: Escrever o teste falho de contraste para o tema claro em `web-react/src/styles/tokens.test.ts`**

```ts
describe('contraste dos tokens de texto no tema claro (html.light)', () => {
  const lightBlock = css.slice(css.indexOf('html.light'));
  const lightToken = (name: string): string => {
    const match = lightBlock.match(new RegExp(`--color-${name}:\\s*([^;]+);`));
    if (!match) throw new Error(`token light ausente: ${name}`);
    return match[1].trim();
  };

  for (const text of ['fg', 'fg-2', 'fg-3']) {
    for (const surface of ['bg', 'surface', 'surface-2', 'surface-3']) {
      it(`light: ${text} sobre ${surface} atinge 4,5:1`, () => {
        const value = ratio(lightToken(text), lightToken(surface));
        expect(value).toBeGreaterThanOrEqual(4.5);
      });
    }
  }
});
```

- [ ] **Step 2: Rodar o teste para confirmar a falha em `fg-3` sobre `surface-2` e `surface-3`**

Run: `npm --prefix web-react test -- src/styles/tokens.test.ts --run`
Expected: FAIL em `light: fg-3 sobre surface-2 atinge 4,5:1` (~4.37) e `surface-3` (~3.83).

- [ ] **Step 3: Atualizar `web-react/src/styles/tailwind.css` com tokens `html.light` compatíveis com WCAG AA**

Definir `--color-fg-3: #475569;` e `--color-unknown: #475569;` em `html.light`, adicionar `--color-accent-ink`, `--color-ok-ink`, `--color-info-ink`, `--color-risk-ink` em `@theme` (tons claros `-300`) e em `html.light` (tons escuros `-700`/`-800` com contraste ≥ 4.5:1 sobre branco), além de variante `.grid-texture` para tema claro.

- [ ] **Step 4: Rodar os testes de tokens e o build de produção**

Run: `npm --prefix web-react test -- src/styles/tokens.test.ts --run && npm --prefix web-react run build`
Expected: PASS (25/25 asserções em `tokens.test.ts`, build sem erros).

- [ ] **Step 5: Commit**

```bash
git add web-react/src/styles/tailwind.css web-react/src/styles/tokens.test.ts web-react/dist
git commit -m "fix(ui): enforce WCAG AA 4.5:1 contrast across light theme tokens"
```

---

### Task 2: Zero-Rerender `GlowCard` via Variáveis CSS & Correção de Double-Padding

**Files:**
- Modify: `web-react/src/components/21st/glow-card.tsx:18-107`
- Modify: `web-react/src/components/21st/opportunity-glow-card.tsx:1-95`
- Create: `web-react/src/components/21st/glow-card.test.tsx`

**Interfaces:**
- Produces: `GlowCard({ accent?: Accent; className?: string; contentClassName?: string; children: ReactNode })` que grava `--glow-x` e `--glow-y` diretamente no elemento DOM via `cardRef.current?.style.setProperty(...)` sem chamar `setState` em `onMouseMove`/`onTouchMove`.

- [ ] **Step 1: Escrever o teste falho em `web-react/src/components/21st/glow-card.test.tsx`**

```tsx
import { fireEvent, render, screen } from '@testing-library/react';
import { describe, expect, it } from 'vitest';
import { GlowCard } from './glow-card';

describe('GlowCard', () => {
  it('atualiza --glow-x e --glow-y no DOM ao mover o mouse sem re-renderizar filhos', () => {
    let renders = 0;
    function Child() {
      renders += 1;
      return <span>Conteúdo interno</span>;
    }

    const { container } = render(
      <GlowCard contentClassName="p-4">
        <Child />
      </GlowCard>,
    );
    expect(screen.getByText('Conteúdo interno')).toBeInTheDocument();
    const initialRenders = renders;

    const root = container.firstElementChild as HTMLElement;
    fireEvent.mouseMove(root, { clientX: 120, clientY: 80 });
    expect(root.style.getPropertyValue('--glow-x')).toBe('120px');
    expect(root.style.getPropertyValue('--glow-y')).toBe('80px');
    expect(renders).toBe(initialRenders);
  });
});
```

- [ ] **Step 2: Rodar o teste para confirmar que falha**

Run: `npm --prefix web-react test -- src/components/21st/glow-card.test.tsx --run`
Expected: FAIL (`--glow-x` vazio e `renders` incrementado a cada `mouseMove`).

- [ ] **Step 3: Implementar `GlowCard` baseado em CSS Custom Properties e ajustar `OpportunityGlowCard`**

Em `glow-card.tsx`, remover `const [pos, setPos] = useState(...)`; usar `useRef<HTMLDivElement>(null)` para atualizar `--glow-x` e `--glow-y` via `style.setProperty`, referenciando `var(--glow-x, 0px) var(--glow-y, 0px)` nos gradientes/máscaras e aceitando `contentClassName = 'p-5'`. Em `opportunity-glow-card.tsx`, passar `contentClassName="p-5"` removendo o `p-4` duplicado interno e substituir `hover:bg-white/[0.04]` por `hover:bg-surface-2`.

- [ ] **Step 4: Rodar os testes de `GlowCard` e `OpportunitiesPage`**

Run: `npm --prefix web-react test -- src/components/21st/glow-card.test.tsx src/features/opportunities/OpportunitiesPage.test.tsx --run && npm --prefix web-react run build`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add web-react/src/components/21st/glow-card.tsx web-react/src/components/21st/opportunity-glow-card.tsx web-react/src/components/21st/glow-card.test.tsx web-react/dist
git commit -m "perf(ui): eliminate 60fps React re-renders in GlowCard and fix double padding"
```

---

### Task 3: Substituição do `RadarBento` Fictício por Telemetria Auditável Real

**Files:**
- Create: `web-react/src/features/overview/ObservatoryHealthBento.tsx`
- Modify: `web-react/src/features/overview/OverviewPage.tsx`
- Modify: `web-react/src/features/overview/OverviewPage.test.tsx`
- Delete: `web-react/src/components/21st/radar-bento.tsx`

**Interfaces:**
- Consumes: `Coverage`, `Timeline`, `Portfolio` de `@/lib/types` e `GlowCard` de Task 2.
- Produces: `ObservatoryHealthBento({ coverage, timeline, portfolio }: { coverage?: Coverage; timeline?: Timeline; portfolio?: Portfolio })` sem timers `setInterval` e sem `Math.random()`.

- [ ] **Step 1: Escrever o teste falho em `web-react/src/features/overview/OverviewPage.test.tsx`**

Adicionar asserção em `OverviewPage.test.tsx` verificando que:
1. A página **não** renderiza textos fictícios (`ms resposta`, `radar ops-ciclo --auto`, `822 decisões registradas`).
2. Renderiza os eventos reais vindos de `Timeline` (`itens` de `/api/linha-do-tempo`) e a distribuição real de estados documentais de `Coverage`, exibindo estado vazio honesto (`Nenhum evento operacional registrado`) quando `timeline.itens` está vazio.

- [ ] **Step 2: Rodar o teste para confirmar que falha**

Run: `npm --prefix web-react test -- src/features/overview/OverviewPage.test.tsx --run`
Expected: FAIL (encontra o `RadarBento` antigo com dados simulados).

- [ ] **Step 3: Criar `ObservatoryHealthBento.tsx`, atualizar `OverviewPage.tsx` e remover `radar-bento.tsx`**

Implementar `ObservatoryHealthBento` exibindo 3 cartões verificáveis: (1) Cobertura Documental & Evidências SHA-256 reais (`coverage`), (2) Últimos Eventos da Linha do Tempo (`useTimeline(8)`), e (3) Distribuição Real por Prontidão/Compatibilidade SI (`portfolio`). Remover `web-react/src/components/21st/radar-bento.tsx`.

- [ ] **Step 4: Verificar testes e build**

Run: `npm --prefix web-react test -- src/features/overview/OverviewPage.test.tsx --run && npm --prefix web-react run build`
Expected: PASS e zero referências remanescentes a `radar-bento`.

- [ ] **Step 5: Commit**

```bash
git add -A web-react/src/features/overview web-react/src/components/21st web-react/dist
git commit -m "refactor(overview): replace synthetic RadarBento telemetry with real audit data"
```

---

### Task 4: Isolamento de `localStorage` por Usuário & Modal Acessível Radix

**Files:**
- Create: `web-react/src/lib/user-storage.ts`
- Create: `web-react/src/lib/user-storage.test.ts`
- Create: `web-react/src/components/ui/dialog.tsx`
- Create: `web-react/src/components/ui/dialog.test.tsx`
- Modify: `web-react/src/features/studies/JottaFlashcardView.tsx`
- Modify: `web-react/src/features/studies/StudyScheduleView.tsx`

**Interfaces:**
- Produces:
  - `scopedStorageKey(baseKey: string, userId?: string | null): string` → retorna `radar:u:${userId || 'local'}:${baseKey}`.
  - `useUserStorage<T>(baseKey: string, initialValue: T, userId?: string | null): [T, (next: T | ((prev: T) => T)) => void, () => void]` — recarrega automaticamente quando `userId` muda (login/logout) e migra `localStorage.getItem(baseKey)` apenas quando `!userId` (modo fundador local).
  - `ModalDialog({ open, onOpenChange, title, description, maxWidthClass, children }): JSX.Element` sobre `@radix-ui/react-dialog`.

- [ ] **Step 1: Escrever os testes falhos `user-storage.test.ts` e `dialog.test.ts`**

```ts
// src/lib/user-storage.test.ts
import { renderHook, act } from '@testing-library/react';
import { beforeEach, describe, expect, it } from 'vitest';
import { useUserStorage } from './user-storage';

describe('useUserStorage', () => {
  beforeEach(() => localStorage.clear());

  it('isola dados entre dois userIds distintos no mesmo navegador', () => {
    const { result, rerender } = renderHook(
      ({ uid }) => useUserStorage<string[]>('completed_lessons', [], uid),
      { initialProps: { uid: 'alice-1' as string | null } },
    );
    act(() => result.current[1](['bd-01']));
    expect(result.current[0]).toEqual(['bd-01']);

    rerender({ uid: 'bob-2' });
    expect(result.current[0]).toEqual([]);

    rerender({ uid: 'alice-1' });
    expect(result.current[0]).toEqual(['bd-01']);
  });
});
```

```tsx
// src/components/ui/dialog.test.tsx
import { fireEvent, render, screen } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';
import { ModalDialog } from './dialog';

describe('ModalDialog', () => {
  it('renderiza diálogo acessível com título e fecha com Escape', () => {
    const onOpenChange = vi.fn();
    render(
      <ModalDialog open onOpenChange={onOpenChange} title="Visualizar Ficha" description="Detalhe em alta resolução">
        <button type="button">Ação interna</button>
      </ModalDialog>,
    );
    expect(screen.getByRole('dialog', { name: 'Visualizar Ficha' })).toBeInTheDocument();
    fireEvent.keyDown(document, { key: 'Escape' });
    expect(onOpenChange).toHaveBeenCalledWith(false);
  });
});
```

- [ ] **Step 2: Rodar os testes para confirmar que falham**

Run: `npm --prefix web-react test -- src/lib/user-storage.test.ts src/components/ui/dialog.test.tsx --run`
Expected: FAIL (arquivos inexistentes).

- [ ] **Step 3: Implementar `user-storage.ts`, `dialog.tsx` e integrá-los em `JottaFlashcardView.tsx` e `StudyScheduleView.tsx`**

Implementar `useUserStorage` em `src/lib/user-storage.ts` e `ModalDialog` em `src/components/ui/dialog.tsx` usando `@radix-ui/react-dialog`. Substituir o `localStorage` global `'radar_weekly_study_schedule_completed'` em `StudyScheduleView.tsx` por `useUserStorage('weekly_schedule_completed', {}, authMe.data?.user?.id)` e usar `ModalDialog` no lightbox de `JottaFlashcardView.tsx`.

- [ ] **Step 4: Rodar os testes e o build**

Run: `npm --prefix web-react test -- src/lib/user-storage.test.ts src/components/ui/dialog.test.tsx src/features/studies/StudyScheduleView.test.tsx --run && npm --prefix web-react run build`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add web-react/src/lib/user-storage.ts web-react/src/lib/user-storage.test.ts web-react/src/components/ui/dialog.tsx web-react/src/components/ui/dialog.test.tsx web-react/src/features/studies/JottaFlashcardView.tsx web-react/src/features/studies/StudyScheduleView.tsx web-react/dist
git commit -m "feat(a11y,auth): add Radix ModalDialog and scope localStorage state per user"
```

---

### Task 5: Decomposição Modular de `LessonsView` & `StudiesPage` + Cronômetro Unificado

**Files:**
- Create: `web-react/src/features/studies/lessons/LessonCatalogView.tsx`
- Create: `web-react/src/features/studies/lessons/LessonTheoryStage.tsx`
- Create: `web-react/src/features/studies/lessons/LessonVisualStage.tsx`
- Create: `web-react/src/features/studies/lessons/LessonVideoStage.tsx`
- Create: `web-react/src/features/studies/lessons/LessonPracticeStage.tsx`
- Create: `web-react/src/features/studies/lessons/LessonTutorDrawer.tsx`
- Create: `web-react/src/features/studies/tabs/StudyOverviewTab.tsx`
- Create: `web-react/src/features/studies/tabs/SessionsTimerTab.tsx`
- Create: `web-react/src/features/studies/tabs/QuestionsPracticeTab.tsx`
- Create: `web-react/src/features/studies/tabs/FlashcardsDeckTab.tsx`
- Create: `web-react/src/features/studies/tabs/ExamsSimulationTab.tsx`
- Modify: `web-react/src/features/studies/LessonsView.tsx`
- Modify: `web-react/src/features/studies/StudiesPage.tsx`
- Test: `web-react/src/features/studies/LessonsView.test.tsx` e `web-react/src/features/studies/StudiesPage.test.tsx`

**Interfaces:**
- Consumes: `useUserStorage` e `ModalDialog` de Task 4; `useStudyPanel` e `/api/estudos/sessoes` de `queries.ts`.
- Produces:
  - Cada etapa da aula (`resumo`, `visual`, `video`, `flashcards`, `questoes`) isolada em componente próprio `< 350 LOC` com props tipadas explícitas.
  - Cada aba de `StudiesPage` isolada em `tabs/*Tab.tsx` (`< 320 LOC` cada).
  - Cronômetro da barra superior da aula sincronizado com `sessao_aberta` do servidor (`POST /api/estudos/sessoes` com `start`/`pause`/`resume`/`finish`) e chaves locais de aula (`completed_lessons`, `completed_video_chapters`, `lesson_synced_notes`, `favorite_flashcards`) migradas para `useUserStorage(..., userId)`.

- [ ] **Step 1: Escrever testes em `LessonsView.test.tsx` e `StudiesPage.test.tsx` cobrindo isolamento por usuário e modal Radix**

Adicionar teste em `LessonsView.test.tsx` garantindo que:
1. As 5 etapas (`1. Resumo`, `2. Quadro Visual`, `3. Videoaula`, `4. Flashcards`, `5. Questões`) continuam navegáveis.
2. Aulas marcadas como concluídas usam a chave escopada `radar:u:...` de `useUserStorage`.

- [ ] **Step 2: Rodar o teste para confirmar a falha antes da extração**

Run: `npm --prefix web-react test -- src/features/studies/LessonsView.test.tsx --run`
Expected: FAIL na asserção da chave escopada `radar:u:`.

- [ ] **Step 3: Extrair subcomponentes de `LessonsView.tsx` e `StudiesPage.tsx` e conectar `useUserStorage` + `ModalDialog` + sessão unificada**

Mover cada estágio para `src/features/studies/lessons/*` e cada aba para `src/features/studies/tabs/*`, mantendo `LessonsView.tsx` e `StudiesPage.tsx` como cascas finas de roteamento/estado (< 250 linhas cada). Substituir o modal manual de criação de aula por `ModalDialog` e conectar o botão Play/Pause do cabeçalho da aula à sessão persistida de `/api/estudos/sessoes` (com fallback local apenas se offline).

- [ ] **Step 4: Rodar toda a suíte de estudos e validar os tamanhos dos arquivos e chunks**

Run: `npm --prefix web-react test -- src/features/studies/ --run && npm --prefix web-react run build`
Expected: PASS em todos os testes de `studies/` e nenhum arquivo em `features/studies/` acima de 400 linhas.

- [ ] **Step 5: Commit**

```bash
git add -A web-react/src/features/studies web-react/dist
git commit -m "refactor(studies): decompose LessonsView and StudiesPage into focused stage/tab modules"
```

---

### Task 6: Otimização WebP de Flashcards IA & Checklist de Onboarding em 3 Passos

**Files:**
- Create: `scripts/optimize_flashcard_assets.py`
- Modify: `web-react/src/features/studies/JottaFlashcardView.tsx`
- Modify: `web-react/src/features/account/PlansAndAuthPage.tsx`
- Create: `web-react/src/features/my-contests/StudentOnboardingChecklist.tsx`
- Modify: `web-react/src/features/my-contests/MyContestsPage.tsx`
- Modify: `web-react/src/features/my-contests/MyContestsPage.test.tsx`

**Interfaces:**
- Consumes: `useMyContests`, `useStudyPanel`, `useFlashStats` de `@/app/queries`; `useUserStorage` de Task 4.
- Produces:
  - Imagens `.webp` em `web-react/public/flashcards/*.webp` com redução ≥ 65% sobre os `9.1 MB` de `.jpg`, servidas via `<picture><source type="image/webp" ... /><img width="800" height="1000" decoding="async" ... /></picture>` (mantendo `.jpg` como fallback e link de download HD).
  - `StudentOnboardingChecklist` em `/` (`MyContestsPage`) guiando novos estudantes pelos 3 passos reais de ativação (1. Favoritar Concurso Foco → 2. Configurar Ciclo Semanal → 3. Estudar 1ª Aula ou Flashcard SM-2), ocultável via `useUserStorage('onboarding_dismissed', false, userId)`.

- [ ] **Step 1: Escrever o teste falho de onboarding em `web-react/src/features/my-contests/MyContestsPage.test.tsx`**

```tsx
it('exibe trilha de ativação em 3 passos com progresso real e permite dispensar', async () => {
  // Mock 0 meus concursos, 0 sessões, 0 revisões SM-2
  // Espera encontrar os 3 passos ("1. Escolher Concurso Foco", "2. Abrir Ciclo Semanal", "3. Iniciar 1ª Aula ou Flashcard")
  // Ao clicar em "Ocultar guia", grava no userStorage e remove o banner
});
```

- [ ] **Step 2: Rodar o teste para confirmar que falha**

Run: `npm --prefix web-react test -- src/features/my-contests/MyContestsPage.test.tsx --run`
Expected: FAIL (`StudentOnboardingChecklist` ainda não existe).

- [ ] **Step 3: Criar `scripts/optimize_flashcard_assets.py`, gerar `.webp`, adotar `<picture>` e implementar `StudentOnboardingChecklist.tsx`**

Executar `.\.venv\Scripts\python.exe scripts/optimize_flashcard_assets.py` (usando `pymupdf` já instalado no `.venv` ou `Pillow` se disponível para converter cada `.jpg` em `.webp` / `.jpg` otimizado sem dependências externas novas), atualizar `JottaFlashcardView.tsx` e `PlansAndAuthPage.tsx` para `<picture>` com `width`/`height` explícitos (zero CLS), e integrar `StudentOnboardingChecklist` em `MyContestsPage.tsx`.

- [ ] **Step 4: Rodar a suíte completa (Vitest + Build + Gate Python F46)**

Run: `npm --prefix web-react test -- --run && npm --prefix web-react run build && .\.venv\Scripts\python.exe -m unittest tests.test_frontend_react_f46 -v`
Expected: 100% PASS em Vitest, build limpo com assets `.webp` copiados para `web-react/dist/flashcards/`, e 9/9 PASS em `test_frontend_react_f46`.

- [ ] **Step 5: Commit**

```bash
git add scripts/optimize_flashcard_assets.py web-react/public/flashcards web-react/src/features/studies/JottaFlashcardView.tsx web-react/src/features/account/PlansAndAuthPage.tsx web-react/src/features/my-contests web-react/dist
git commit -m "feat(ux,perf): add WebP flashcard pictures and 3-step student onboarding checklist"
```
