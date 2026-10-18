# Pesquisa — Fase 34: mesa de revisão, dossiês e decisões auditáveis

Data da consulta: 2026-10-17. Objetivo: decidir como construir uma mesa de revisão humana
eficiente sobre uma base SQLite + frontend JS sem framework, sem criar um segundo fluxo de
decisão.

## Critérios

1. Reaproveitar o modelo existente (proposta → evidência → decisão append-only).
2. Não introduzir dependência de UI (framework, componente, serviço).
3. Padrões que reduzam erro do operador: contexto suficiente na linha, comparação de
   evidências, detecção de item alterado.
4. Acessibilidade por teclado e estados não dependentes de cor.
5. Licença compatível; nada de copiar código sem examinar.

## Padrões examinados

| Referência | Padrão | Decisão |
|---|---|---|
| `pete-builds/agent-desk` — <https://github.com/pete-builds/agent-desk> | Fila de aprovação com veredito **append-only**: a API não oferece edição/exclusão; o banco recusa segundo veredito; status mutável é só o reflexo. | **Adotado como princípio** (já é o do projeto: `revisoes_campo` só insere). Reforçou a decisão de **não** criar endpoint de edição de decisão nesta fase. |
| Review queue UX Pattern — <https://uxpatternsguide.com/patterns/review-queue/> | Cada linha mostra **por que está na fila**; abrir preserva filtro/posição; verificar se o item mudou antes de decidir; anúncio de contagens por status; ações de linha acessíveis por teclado. | **Adotado**: motivos de prioridade na linha (tooltip e texto), filtros persistidos, `alterado` com bloqueio, contagem em região `aria-live`, linha focável com Enter/Espaço. |
| Talonic — Review Queue — <https://talonic.com/docs/platform/review-queue> | Fila é **consulta sobre o estado canônico**, não lista paralela; decisão grava célula de promoção + log append-only; revisão posterior mantém as anteriores. | **Adotado**: a mesa deriva de `propostas_campo` a cada requisição; não há tabela de fila própria. Revisão posterior continua append-only. |
| `beomwookang/deliberate` — <https://github.com/beomwookang/deliberate> | Ledger append-only com hash; identidade do aprovador; métricas de decisão. | **Parcial**: hash de evidência por decisão já existe (`evidence_sha256`); identidade continua local (operador não autenticado), declarada como limitação. Não se adotou o produto. |
| withHuman — Review queue — <https://withhuman.ai/docs/web-app/review-queue> | Detalhe ao lado da fila; aprovar não é "ação executada"; histórico junto do item. | **Adotado em espírito**: dossiê e evidência abrem abaixo/ao lado, com a ressalva de que confirmar não executa nada. |

## O que foi rejeitado

- **Framework de UI** (React/Vue/Svelte): o app é vanilla JS com testes em Node. Trocar a stack
  por causa de uma tela seria custo desproporcional e risco de regressão em 12 painéis.
- **Biblioteca de tabela virtualizada**: 273 grupos (não 6.199 linhas) cabem em paginação de 25
  sem virtualização. Virtualizar adicionaria dependência sem ganho mensurável.
- **Bulk approve**: nenhuma referência séria permite aprovar centenas de candidatos; a fase
  proíbe e o projeto mantém decisão uma a uma.

## Limitações da pesquisa

- Não há benchmark público de "mesa de revisão de editais"; as referências são de domínios
  diferentes (aprovação de agentes, dados de produto). O que se aproveitou foram **padrões de
  interação e auditoria**, não código.
- A comparação de evidências é específica do domínio (página, trecho, versão, hash) e foi
  implementada sobre o modelo existente, sem equivalente externo direto.
