# Prova real — frontend de produto (Fase 45)

Data: 2026-10-19/20. Base: `5660a11`. Branch `radar-configuracao`. Schema v21.

## Estado inicial

| Item | Resultado |
|---|---|
| Repositório / branch | `radar-de-concursos` / `radar-configuracao` |
| HEAD | `5660a11`, árvore limpa, sincronizada com `origin` |
| Suíte inicial | **1.906 testes, OK** (1 ignorado) |
| Base | 1.276 documentos, 1.110 versões, 9.340 propostas/evidências, 0 decisões humanas |
| UI anterior | `index.html` 53 KB, `styles.css` 31 KB, `app.js` 290 KB, sem navegação por telas |

## Validação no navegador (Chromium via Playwright, servidor real)

Resoluções inspecionadas: **1440×900, 1280×800, 768×1024, 390×844**.
Capturas salvas em `%TEMP%\opencode\f45-shots\` (fora do repositório):
`1440-visao-geral.png`, `1440-oportunidades.png`, `1440-dossie.png`,
`1440-estudos.png`, `768-visao-geral.png`, `390-visao-geral.png`, `390-drawer.png`.

> O modelo desta sessão é textual e **não interpreta imagens**. A validação visual foi
> feita por medição objetiva no DOM (geometria, overflow, sobreposição, contraste WCAG,
> alvos de toque, truncamento) e as capturas ficam disponíveis para inspeção humana.

### Medições (após refinamento)

| Tela | 1440 | 1280 | 768 | 390 |
|---|---|---|---|---|
| Rolagem horizontal | não | não | não | não |
| Texto cortado sem reticências | 0 | 0 | 0 | 0 |
| Sobreposição de cartões | 0 | 0 | 0 | 0 |
| Texto com contraste < 4,5:1 | 0 | 0 | 0 | 0 |
| Erro de API visível | 0 | 0 | 0 | 0 |

## Refinamentos concretos feitos após observar o resultado

1. **`.card__body` inexistente** quando o cartão era criado sem corpo → vários cartões
   ficavam vazios (prazos, estudos, histórico). Corrigido em `components/ui.js`.
2. **`[hidden]` não vencia `display:flex`** dos componentes → estados “carregando/erro/
   vazio” apareciam juntos e a Operação exibia todos os painéis ocultos. Adicionada regra
   global `[hidden] { display: none !important; }`.
3. **`edital is not defined`** no resumo do dossiê (variável não declarada na aba). Corrigido.
4. **429 ao navegar** entre telas: o semáforo de consultas pesadas incluía `/api/carteira`
   e recusava em vez de esperar. Removido da lista e trocado para `acquire(timeout=5)`.
5. **Contraste 4,4:1** em texto secundário e rótulos de filtro → paleta de `--muted`
   escurecida; nenhum texto abaixo de 4,5:1 agora.
6. **Overflow horizontal no mobile** no Histórico (URLs longas) e no dossiê (lacunas) →
   `overflow-wrap:anywhere` e `min-width:0` nos blocos de lista/painel.
7. **Tabela de prazos duplicando o mesmo evento** (mesmo grupo/data/concurso vindo de
   documento e cronograma) → deduplicação na apresentação, sem alterar dados.
8. **Operação com 48 mil px** → cada painel técnico virou `<details>` (2 abertos por
   padrão, atalhos do topo abrem o bloco correspondente), preservando todos os controles.
9. **Atalhos da Operação mudavam a rota** (`#sources-title` virava Visão geral) →
   `preventDefault`, abre o bloco e rola até a seção.
10. **Alvos de clique pequenos** (links de cartão e títulos de lista com 17–19 px) →
    altura mínima 24–28 px.
11. **Breakpoint de tablet**: drawer passou a valer até 900 px (antes 760), evitando rail
    de 76 px sem rótulos em tablet.

## Testes funcionais executados no navegador

| Fluxo | Resultado |
|---|---|
| Visão geral com dados reais | 685 oportunidades, 635 concursos, 81 prazos, 0 min estudados |
| Gráfico de ciclos | 4 colunas com data+hora, tabela equivalente em `<details>` |
| Oportunidades: filtro UF=TO | 18 resultados, chip “UF: TO”, hash `?uf=TO` |
| Oportunidades: busca sem resultado | estado vazio com ação “Limpar filtros” |
| Oportunidades: paginação | “Página 2 de 35 · 685 resultado(s)”, hash `?offset=20` |
| Oportunidades: ordenação | `?sort=prazo`, volta ao offset 0 |
| Abrir dossiê a partir da lista | 7 abas, todas sem erro |
| Voltar do dossiê | filtros e UF preservados (`18` resultados) |
| Avançar | dossiê restaurado |
| Sidebar recolhida | 248 → 76 px, rótulos ocultos, `aria-label` “Expandir menu”, preferência salva |
| Drawer no celular | abre, bloqueia rolagem, foca “Fechar”, fecha ao navegar e com `Esc` |
| Estudos | 5 abas, cronômetro 00:00:00, estados vazios corretos |
| Configurações | preferências reais carregadas (BA, PE, 300 km) |
| Operação | 21 blocos recolhíveis, atalhos abrem a seção, painéis legados ativos |

## Testes automatizados

- Novos: `tests/test_frontend_f45.py` (19 testes) — shell, tokens, breakpoints, views,
  endpoints reais, acessibilidade de gráficos, serviço HTTP, store local, assets servidos,
  cache `no-cache`, traversal em subdiretórios e allowlist de extensões.
- Suíte final: **1.925 testes, OK** (1 ignorado).
- Contrato: `GET /api/concursos` v1 preservado (18 campos, `test_contract.py`).
- Contrato HTTP: 129 entradas método+rota verificadas (`api_contract.verify()`).

## Base de dados

Nenhuma migração, nenhuma exclusão e nenhuma decisão humana criada pela interface.
`PRAGMA integrity_check` = `ok`; `PRAGMA foreign_key_check` = 0.

## Pendências conhecidas (não bloqueantes)

- Conteúdo programático e “plano de estudos” aparecem apenas via painéis técnicos; não há
  tela de plano dedicada nesta fase.
- Não há “salvos/favoritos”: a funcionalidade não existe no backend, então não há link.
- A lista “Concursos monitorados” do legado usa o contrato v1 (tabela de coleta), que está
  vazia; a base documental aparece em Oportunidades, Cobertura e Carteira.
- Gráficos usam SVG próprio; sem zoom/pan (não necessário para as séries atuais).
