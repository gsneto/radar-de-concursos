# Frontend React — identidade "Observatório" (Fase 46)

Data: 2026-10-22. Base: `cd1873b` (Fase 45), branch `radar-configuracao`, schema v21.
Status: design aprovado em conversa; este documento é o contrato da implementação.

## 1. Objetivo

Substituir o frontend vanilla da Fase 45 por uma aplicação React com identidade visual
própria ("Observatório"), mantendo intactos: o backend Python, o contrato HTTP (129
entradas método+rota), o contrato v1 de `GET /api/concursos` e os 21 painéis técnicos.

Sucesso = o produto parece um instrumento de precisão, não um template; os dados
continuam reais; a Operação continua acessível; a suíte segue verde; o app roda com
`python -m radar serve` sem exigir Node no computador de destino.

## 2. Decisões e justificativas

### 2.1 Stack

| Peça | Versão alvo | Licença | Motivo |
|---|---|---|---|
| React | 19 | MIT | ecossistema necessário para 21st.dev/shadcn |
| TypeScript | 5.x strict | Apache-2.0 | contratos tipados sobre a API |
| Vite | 7 | MIT | build estático, dev server com proxy |
| Tailwind CSS | 4 (`@theme`) | MIT | tokens em CSS, sem arquivo de config |
| shadcn/ui + Radix | atual | MIT | primitivas acessíveis copiadas no repo |
| Motion | 12 | MIT | transições e microinterações |
| TanStack Query | 5 | MIT | cache, loading/erro, retry, invalidação |
| TanStack Table | 8 | MIT | ordenação/paginação da lista de oportunidades |
| React Router | 7 | MIT | rotas por URL real |
| cmdk | 1 | MIT | command palette |
| lucide-react | atual | ISC | ícones consistentes |

**Excluídos, com motivo:**

- **React Bits** — licença MIT + Commons Clause: proíbe vender software que o contenha.
  O Radar pode virar produto pago. Usado apenas como referência de técnica; os efeitos
  desejados são reimplementados com Motion/CSS.
- **Next.js** — exigiria runtime Node; o backend é Python.
- **Recharts / Chart.js** — o SVG próprio da Fase 45 já é acessível e leve; biblioteca
  adicionaria peso sem ganho.
- **21st.dev** — permitido, mas cada componente é verificado individualmente quanto a
  licença antes de entrar; componentes com licença restritiva são reimplementados.

### 2.2 Distribuição

Vite gera `web-react/dist` **commitado**. `radar/server.py` serve `dist/` com fallback
SPA; `/api/*` inalterado; `/legacy/` serve a UI vanilla da Fase 45 (Operação).

Justificativa: o produto é local (`python -m radar serve`) e não deve exigir Node no
destino. Custo aceito: `dist/` versionado (~1–2 MB) e necessidade de `npm run build`
antes de commitar mudanças de frontend.

### 2.3 Identidade "Observatório"

Fundo quase preto azulado, tipografia display condensada, acento âmbar, dados em mono.
A metáfora do radar é estrutural (varredura, anéis, leitura de instrumento), não decorativa.

| Token | Valor | Uso |
|---|---|---|
| `--bg` | `#07090D` | fundo da aplicação |
| `--surface-1` | `#0D1117` | cartões |
| `--surface-2` | `#121822` | cabeçalhos, hover, poços |
| `--border` | `rgba(255,255,255,.08)` | divisórias |
| `--border-strong` | `rgba(255,255,255,.14)` | foco de cartão, inputs |
| `--fg` | `#E8EDF5` | texto principal |
| `--fg-2` | `#98A4B8` | texto secundário |
| `--fg-3` | `#66738A` | metadados |
| `--amber` | `#F5A524` | ação primária, seleção, série principal |
| `--teal` | `#2DD4BF` | "verificado/ok" apenas |
| `--ok` | `#34D399` | sucesso confirmado |
| `--warn` | `#FBBF24` | atenção |
| `--risk` | `#F87171` | erro/risco real |
| `--unknown` | `#64748B` | desconhecido |

Tipografia self-hosted (OFL), subset woff2, sem CDN:
**Space Grotesk** (títulos e valores), **Inter** (UI), **JetBrains Mono** (números,
datas, hashes, IDs). Total alvo ≤ 140 KB.

Escala: 11/12/13/14/16/20/26/34 px. Espaçamento base 4. Raios 6/10/14. Uma sombra.
Altura de topbar 60 px; sidebar 244/72 px; conteúdo máximo 1400 px.

### 2.4 Movimento

120–260 ms, `ease-out` para entrada e `ease-in` para saída. Varredura do radar apenas em
logo e estados de carregamento. Contagem animada só em KPI. Nada anima em massa na
navegação. `prefers-reduced-motion: reduce` remove todas as animações e a varredura.

## 3. Arquitetura

```
web-react/
  index.html
  vite.config.ts          base '/', proxy /api em dev
  tsconfig.json           strict
  package.json
  src/
    main.tsx              bootstrap, Router, QueryClientProvider
    app/
      shell.tsx           sidebar + topbar + outlet
      router.tsx          rotas
      query.ts            QueryClient e políticas
      command-palette.tsx ⌘K
    features/
      overview/           página + hooks + componentes
      opportunities/      tabela, filtros, URL state
      dossier/            7 abas
      deadlines/
      studies/
      history/
      settings/
    components/
      ui/                 shadcn copiado
      charts/             svg: radar, area, bars, donut, sparkline, ring
      states/             loading, empty, error, offline
      layout/             page-header, section, kpi-card
    lib/
      api.ts              client tipado + ApiError
      types.ts            tipos derivados de docs/API.md
      format.ts           pt-BR (números, datas, duração)
      query-keys.ts
    styles/
      tailwind.css        @theme com os tokens
      fonts.css
  dist/                   build commitado
```

Regras de fronteira:

- `features/*` não importa de outra `feature/*`; compartilhado vai para `components`/`lib`.
- Nenhum `fetch` fora de `lib/api.ts`.
- Nenhum tipo duplicado: `lib/types.ts` é a fonte.
- Nenhum token de cor literal em componente; só classe/variável do tema.

## 4. Rotas e navegação

| Rota | Tela | Fonte de dados |
|---|---|---|
| `/` | Visão geral | carteira, cobertura, linha do tempo, prazos, estudos |
| `/oportunidades` | Lista | `/api/carteira` com filtros em query string |
| `/prazos` | Calendário | `/api/prazos/calendario` |
| `/estudos` | Estudos (abas) | `/api/estudos/*` |
| `/historico` | Histórico | `/api/linha-do-tempo` |
| `/configuracoes` | Preferências | `/api/preferencias` |
| `/dossie/:contestId` | Dossiê (abas) | `/api/carteira/dossie`, `/api/concursos/:id/detalhes` |
| `/operacao` | Lançador dos painéis técnicos | links para `/legacy/` |

`/operacao` no React é uma página de lançamento: lista os 21 painéis com descrição curta e
abre `/legacy/` (UI vanilla) no mesmo separador, com âncora para a seção escolhida. O
botão Voltar do navegador retorna ao React. Não há iframe.

Estado de filtros e abas **na URL** (search params), não em estado local — voltar/avançar
preserva contexto. `?tab=` nas telas com abas.

Command palette: `⌘K`/`Ctrl+K` abre; ações = navegar para as 7 telas, buscar oportunidade
por texto (chama `/api/carteira?search=`), abrir dossiê de resultado. `Esc` fecha; foco
volta ao gatilho.

## 5. Telas

### 5.1 Visão geral

- Cabeçalho: título, data local do navegador, ação primária "Explorar oportunidades".
- 4 KPIs: carteira (com anel de prontidão), concursos monitorados, prazos ≤30 dias,
  tempo estudado. Valor com contagem animada; subtítulo com contexto real.
- Varredura de atividade: 8 últimos ciclos, barras com eixo e tooltip.
- Funil de cobertura: 6 etapas com denominador explícito.
- Prioridades: 5 oportunidades com motivo e link.
- Prazos próximos: até 6, com data, evento e estado do documento.
- Prontidão: barra empilhada + legenda.
- Estudos: tempo, sessões, revisões ou estado vazio com CTA.

### 5.2 Oportunidades

Busca + filtros (UF, prontidão, SI, indígena, prazo, documental, conflito) + ordenação.
Tabela com TanStack: colunas Oportunidade, Local, Prazo, Formação, Reserva, Situação.
Paginação real; contagem do servidor; chips removíveis; estado vazio com limpar filtros.

### 5.3 Dossiê

Abas: Resumo, Cargo e requisitos, Vagas e modalidades, Prazos, Localização, Documentos,
Evidências. Regras de integridade herdadas: total agregado ≠ distribuição; reserva
unificada ≠ vaga exclusiva; ausência ≠ zero; data candidata ≠ prazo confirmado.

### 5.4 Estudos

Abas: Visão geral (cronômetro, tempo por disciplina, atividade 14 dias, revisões),
Sessões (disciplinas/tópicos + histórico), Questões (praticar + desempenho),
Flashcards (fila + revisão SM-2), Simulados (criar, responder, finalizar, resultado).

### 5.5 Prazos, Histórico, Configurações

Prazos: filtros por evento/urgência, tabela com estado do documento.
Histórico: KPIs de 24h, eventos por tipo, ciclos com fontes.
Configurações: preferências do backend + preferência local de sidebar.

## 6. Dados e estados

`lib/api.ts` expõe `get/post` tipados com `AbortSignal`, timeout de 20 s, `ApiError`
(`status`, `code`, `message`) e `no-store`. TanStack Query:

| Recurso | staleTime | retry |
|---|---|---|
| carteira, dossiê | 60 s | 1 |
| cobertura, prazos, histórico | 5 min | 1 |
| estudos | 30 s | 1 |
| preferências | ∞ até mutação | 0 |

Retry só em falha de rede, timeout ou 5xx; 4xx nunca é repetido (é erro de contrato).
Mutation não faz retry automático.

Estados obrigatórios por componente assíncrono: skeleton (só onde reproduz o layout),
vazio com motivo e ação, erro com mensagem do backend e "Tentar novamente". Erro de rede
não apaga dado já carregado (mantém com aviso).

## 7. Integridade dos dados (inegociável)

1. Nenhum dado simulado em produção; mocks só em teste.
2. `null`/ausente → "Não informado"; zero permanece zero.
3. Percentual só com denominador; sem `pct`, exibir "—" e a base textual do backend.
4. Reserva indígena, cadastro de reserva, vagas imediatas e total agregado em blocos
   separados, com nota de que não se somam.
5. Compatibilidade com SI usa o estado calculado; nunca afinidade temática.
6. Prazo mostra estado operacional e documento; candidato não vira "inscrição aberta".
7. Contrato v1 de `/api/concursos` não muda.
8. Nenhuma escrita silenciosa: toda mutação exige ação explícita do usuário.

## 8. Acessibilidade

- Um `h1` por página; `h2` de seção; `h3` de cartão.
- Landmarks: `header`, `nav`, `main`, `aside`, `footer`.
- Skip link; foco visível (anel âmbar 2 px + offset 2 px).
- Contraste ≥ 4,5:1 para texto normal e ≥ 3:1 para texto grande/ícones — medido no
  navegador, não estimado.
- Tabela com `caption`, `th scope`, ordenação anunciada por `aria-sort`.
- Gráficos: `role="img"` + `title`/`desc` + tabela equivalente em `<details>`.
- Diálogos Radix: foco preso, `Esc` fecha, foco retorna.
- Alvos de toque ≥ 32 px em mobile.
- `prefers-reduced-motion` respeitado.

## 9. Responsividade

| Largura | Comportamento |
|---|---|
| ≥1280 | sidebar expandida, grid de 2–3 colunas |
| 1024–1279 | sidebar expandida, grid de 2 colunas |
| 768–1023 | sidebar rail de ícones |
| <768 | sidebar em drawer; tabela vira lista de cartões |

Sem rolagem horizontal em nenhuma rota, em nenhuma das 4 resoluções de teste.

## 10. Servidor

Alterações mínimas e testadas em `radar/server.py`:

- `_serve_static` para `web-react/dist`, com `no-cache` para HTML e cache curto para
  assets com hash.
- Fallback SPA: caminho não-API e não-asset → `dist/index.html`.
- `/legacy/` e `/legacy/*` → UI vanilla atual (Operação), sem alteração de comportamento.
- `/api/*` intocado; contrato verificado por `api_contract.verify()`.
- Traversal bloqueado; allowlist de extensão.

## 11. Testes

- **Vitest + Testing Library**: format, api client (erro/timeout/abort), hooks de dados,
  KPI/estado vazio/erro, tabela (ordenação/paginação), dossiê (abas e regras de vagas),
  estudos (cronômetro e simulados).
- **Python**: `tests/test_frontend_react_f46.py` — `dist/index.html` existe, referencia
  assets construídos, `/` serve o app, `/legacy/` serve o vanilla, fallback SPA funciona,
  traversal bloqueado, contrato v1 e `api_contract` verdes.
- **Playwright**: 1440×900, 1280×800, 768×1024, 390×844; medir overflow, sobreposição,
  contraste, truncamento; navegação por teclado; command palette; voltar/avançar com
  filtros.
- Suíte Python completa continua obrigatória (hoje 1.925).

## 12. Riscos

| Risco | Mitigação |
|---|---|
| `dist/` versionado gera churn | build determinístico; commitar apenas quando o frontend mudar |
| Build obrigatório | script `npm run build` documentado no README e no AGENTS.md; `dist/` commitado junto com a mudança de frontend |
| Fontes somam peso | subset woff2, só pesos usados |
| Reescrita de 8 telas | etapas pequenas, cada uma validada no navegador |
| Regressão de integridade | testes que fixam as 8 regras da seção 7 |
| React Bits desejado | reimplementar efeitos com Motion; registrar a restrição de licença |

## 13. Fora de escopo

Operação reescrita em React; tema claro; autenticação; deploy; app móvel; PWA/offline;
i18n; testes E2E em CI remota.

## 14. Critério de aceitação

1. `python -m radar serve` serve o novo app sem Node.
2. 8 telas navegáveis por URL real, com voltar/avançar preservando filtros.
3. Identidade "Observatório" aplicada de forma consistente; nenhum token literal solto.
4. Zero rolagem horizontal e zero sobreposição nas 4 resoluções.
5. Contraste medido ≥ 4,5:1 nas telas auditadas.
6. Operação intacta em `/legacy/`.
7. Contrato HTTP e v1 inalterados.
8. Suíte Python verde + testes React verdes.
9. `docs/` atualizado com design, plano e prova real.
