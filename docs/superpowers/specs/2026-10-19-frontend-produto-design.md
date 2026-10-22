# Frontend de produto — design e arquitetura (Fase 45)

Data: 2026-10-19. Base: `5660a11` (Fase 44), branch `radar-configuracao`. Schema v21.

## Objetivo

Entregar a primeira versão visual do Radar com padrão de SaaS: shell próprio, sidebar,
dashboards, busca de oportunidades, dossiê e estudos, tudo conectado aos contratos reais
de `docs/API.md` e sem dependências externas de frontend.

## Pesquisa consultada

| Referência | O que foi aproveitado | Licença/uso |
|---|---|---|
| [shadcn.io — Sidebar Analytics Dashboard](https://www.shadcn.io/blocks/sidebar-analytics-dashboard) | Agrupamento do menu (Overview/Acquisition/Engagement/Settings) e ícones consistentes por item | Documentação pública; nenhum código copiado |
| [Coreview — B2B SaaS Dashboard](https://medley.ltd/ui-ux/coreview-b2b-saas-dashboard/) | Hierarquia “KPIs → tendências → detalhe operacional”, densidade e respiro | Referência de composição |
| [Analytica — Case Study](https://codalyst-tech.com/work/analytica) | Sidebar persistente entre telas, CSS custom properties para gráficos, tema claro | Referência de arquitetura |
| [SaaS Analytics Platform (Zorvia)](https://zorvia.framer.website/work/saas-analytics-platform) | “Layered intelligence”: KPI alto nível + detalhe expansível; alerta com contraste alto | Referência conceitual |
| [W3C Wiki — ARIA roles for charts](https://www.w3.org/wiki/SVG_Accessibility/ARIA_roles_for_charts) | `role="img"`, `title`/`desc` e alternativa tabular | Padrão de acessibilidade |
| [USWDS — Data visualizations](https://designsystem.digital.gov/components/data-visualizations/) | Tabela equivalente, evitar interação obrigatória, poucas cores por gráfico | Padrão público (US Government) |
| [Data Europa — SVG acessível](https://data.europa.eu/apps/data-visualisation-guide/making-svg-content-fully-accessible) | Ordem de leitura e uso de `title`/`desc` | Padrão público |
| [NVIDIA Elements — Design tokens](https://nvidia.github.io/elements/docs/foundations/themes/tokens/) | Três camadas (primitivo → semântico → componente), escala de espaço e tipografia | Referência de tokens |
| [Interface Cheat Sheet](https://interfaces.dev/cheat-sheet) | `tabular-nums` em números, `text-wrap: balance`, `overflow-wrap` | Referência de detalhe |

Decisões motivadas pela pesquisa:

- **Sem framework e sem build.** O projeto é stdlib + HTML/CSS/JS; a composição foi feita
  com CSS Grid/Flex, SVG inline e módulos IIFE. Nenhuma dependência nova.
- **Tokens em três camadas** (primitivos → semânticos → uso), como no Elements, para que a
  paleta mude em um lugar.
- **Gráficos em SVG próprio** com `role="img"`, `title`/`desc` e `<details>` com tabela
  equivalente (USWDS/W3C). Sem Chart.js/Recharts: peso e dependência não se justificam.
- **Sidebar persistente e recolhível**, com preferência em `localStorage`; no celular vira
  drawer com foco controlado, como nos dashboards analisados.
- **Números tabulares** em KPIs, tabelas e cronômetro.

## Direção visual

- Sidebar grafite-azulada (`#0e1830`) com marca própria em SVG (radar: anéis + varredura
  em teal), item ativo com barra lateral índigo e fundo translúcido.
- Área principal em cinza frio (`#f4f6fb`), superfícies brancas, bordas `#e3e8f1` e sombra
  única e discreta.
- Primária índigo (`#4f46e5`), secundária teal (`#0f8f8d`) usada com parcimônia (marca,
  estados “reserva” e séries de estudo).
- Funcionais: verde (confirmado), âmbar (atenção), vermelho (risco), cinza (desconhecido).
- Tipografia de sistema (`-apple-system`/`Segoe UI`), escala 11–34 px, pesos 500–700,
  entrelinha 1.2–1.55.
- Espaçamento base 4 px (`--space-1..10`), raios 6–18 px, topbar 64 px, sidebar 248/76 px,
  conteúdo máximo 1360 px.

## Arquitetura

```
web/
  index.html          shell + markup legado preservado em #view-operation
  product.css         design system e layout (carregado depois de styles.css)
  shell.js            rotas por hash, sidebar/topbar, drawer, operação
  app.js              legado preservado (painéis técnicos), init adiado
  core/dom.js         criação segura de nós + ícones SVG
  core/format.js      números/datas/duração pt-BR
  core/api.js         fetch com timeout, erros tipados, sequenciador anti-corrida
  core/store.js       preferências locais (localStorage/sessionStorage)
  components/ui.js    badge, card, KPI, progresso, estados, tabela acessível
  components/charts.js colunas, barras e sparkline em SVG
  views/overview.js   dashboard principal
  views/opportunities.js busca, filtros, ordenação, paginação
  views/dossier.js    dossiê em 7 abas
  views/studies.js    estudos (5 abas)
  views/deadlines.js  calendário de prazos
  views/history.js    histórico e ciclos
  views/settings.js   preferências reais + interface
```

Rotas: `#/visao-geral`, `#/oportunidades`, `#/prazos`, `#/estudos?tab=…`,
`#/historico`, `#/configuracoes`, `#/operacao`, `#/dossie/<uuid>?scope=&role_id=`.
Filtros e paginação vivem na query do hash, então voltar/avançar preserva o estado.

`shell.js` chama `Radar.init()` (legado) apenas na primeira visita à Operação; o legado
foi mantido intacto e cada seção virou um bloco recolhível (`<details>`), preservando ids,
botões e rotas internas.

## Integridade de dados na interface

- Nada de dado fictício: todas as telas leem rotas reais e mostram erro/vazio quando a
  resposta é vazia ou falha.
- `null`/ausente vira “Não informado”; zero permanece zero.
- Percentual só aparece com denominador (`pct` nulo → “—”, com `basis` do servidor).
- Reserva indígena, cadastro de reserva, vagas imediatas e total agregado são apresentados
  em cartões separados, com texto explicando que não se somam.
- Compatibilidade com SI usa o estado calculado e a explicação do backend.
- Prazos mostram estado operacional e documento; datas candidatas não viram “inscrição
  aberta”.
- Todo texto de API é inserido via `textContent`/`createElement`; URLs externas passam por
  allowlist de protocolo e `rel="noopener noreferrer"`.

## Acessibilidade

- Um `<h1>` (marca), `h2` por tela, `h3` em cartões; landmarks `aside/nav/main/header/footer`.
- Skip link, foco visível (`:focus-visible` com anel índigo), `aria-current="page"`.
- Drawer: `aria-expanded`, foco no botão de fechar, fechamento por `Esc` e clique no fundo,
  `body` sem rolagem enquanto aberto.
- Gráficos com `role="img"` + `title`/`desc` e tabela equivalente em `<details>`.
- `prefers-reduced-motion` desliga animações; alvos de toque ≥ 24–36 px.
- Contraste medido no navegador: nenhum texto abaixo de 4,5:1 nas telas auditadas.

## Segurança

- Escritas usam `RadarApi.post` (JSON, sem CORS), respeitando `Origin`/`Host` do backend.
- Nenhum `innerHTML` com dado de API; sem `eval`; sem CDN.
- Exportação de estudos gera Blob local; importação exige prévia (`dry_run`) e confirmação.
- Links de documentos exigem `http(s)` e abrem com `noopener noreferrer`.
