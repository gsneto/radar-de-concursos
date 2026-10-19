# Fechamento integral do backend — design (Fase 44)

Data: 2026-10-19. Base: `b2fddc2` (Fase 43), branch `radar-configuracao`, schema v21.

## Objetivo

Fechar o backend do produto antes do frontend, sem transformar pendências documentais em
bloqueio. A fase entrega: inventário classificado, correções P0/P1, contrato de API
verificável, relatório único de prontidão, endurecimento de segurança, medição de
desempenho e gate objetivo.

## Decisões

### 1. Contrato de API verificável, sem OpenAPI formal

O servidor é stdlib; introduzir um gerador OpenAPI adicionaria dependência e divergência.
`radar/api_contract.py` mantém um registro explícito de **método + rota + query + corpo +
escrita + idempotência + resumo** e `verify()` extrai as rotas do AST de `server.py`.
A comparação é por método+rota, não por caminho: uma rota documentada com método errado
falha. Rotas declaradas por sufixo (`/detalhes`, `/resultado`, `/questoes`, `/resumo`,
verbos de simulado) têm marcadores conferidos no código-fonte. `docs/API.md` é gerado do
mesmo registro.

Consequências:
- rota nova sem contrato quebra o teste;
- contrato não lista rota inexistente;
- `GET /api/concursos` v1 permanece intacto (18 campos).

### 2. Prontidão como relatório, não como semáforo simplista

`radar/readiness.py` lê banco, catálogo e contrato. Checks bloqueantes: schema legível,
integridade, chaves estrangeiras, proveniência (proposta↔evidência), hash documental,
tabelas obrigatórias, contrato de API e serviços de estudo. Pendências não bloqueantes:
documentos sem versão, extrações parciais/falhas, conflitos, prazos a revalidar,
credenciais externas e último ciclo não concluído.

Regras:
- banco inexistente, schema pendente ou tabela obrigatória ausente → `bloqueado` sem
  consultar tabelas que não existem;
- qualquer check `reprovado` → `bloqueado`;
- pendência isolada → `pronto_com_pendencias`, nunca `indisponivel`;
- cache de 60 s por fingerprint do banco + configuração de fontes, com geração
  single-flight; `full=True` no CLI ignora o cache;
- HTTP redige caminho absoluto do banco.

### 3. Estados de extração com semântica real

Antes, toda análise com blocos virava `parcial`, então `concluida` nunca existia.
Agora:
- `concluida`: extração integral (não truncada, sem camada derivada);
- `parcial`: prefixo declarado (`truncated`), OCR derivado ou lote intermediário;
- `falhou`: sem texto/bloco ou erro de extração.

`record_analysis(partial=...)` permite declarar; sem declaração, o `note` é interpretado
(`truncated`, `pages`, `derived_layer`). `append_page_analysis(partial=...)` e
`page_batches` marcam o último lote como concluído; `mark_extraction_complete` fecha
lotes sem texto novo. Versões históricas sem nota permanecem `parcial` (conservador) e
são contadas como pendência.

### 4. Configuração de fontes é a fonte da verdade

`budget.state_report(config=...)` combina a linha persistida com
`sources.<chave>.enabled`/`min_interval_hours`. Sem isso, `/api/fontes` e o relatório
mostravam todas as fontes desligadas mesmo com 5 habilitadas no `radar_ops.json`.
`configured` distingue “desligada por configuração” de “nunca configurada”.

### 5. Segurança de escrita local

- `Origin`, quando presente, precisa ser loopback na mesma porta (403).
- `Content-Type: application/json` obrigatório quando há corpo (415).
- `Host` precisa ser loopback na mesma porta (403) — defesa contra DNS rebinding, que
  permitiria ler dados locais por um domínio externo resolvido para 127.0.0.1.
- `X-Content-Type-Options: nosniff`; `Cache-Control: no-store` em JSON.
- GETs pesados (`carteira`, `revisao/grupos`, `saude/prontidao`, `quadro-vagas`,
  `cobertura`, `elegibilidade`, `pipeline/parciais`, `revisao/piloto`) limitados a 2
  concorrentes; excedente recebe 429.
- Não há autenticação de rede: o produto é local em 127.0.0.1.

### 6. Desempenho por medição

Medido antes de otimizar:
- carteira: 4,07 s frio / 4,20 s quente;
- quadro de vagas: 2,83 s por chamada;
- prontidão: 0,63–0,78 s por chamada;
- revisão agrupada: 5,28 s frio / 1,03 s quente.

Correções:
- pré-agrupar propostas por concurso em `decisive_fields` (O(n×m) → O(n));
- varredura única `bulk` em `opportunities` (4 páginas → 1);
- cache em processo com fingerprint (mtime/tamanho/contagens/max timestamp) para
  carteira e quadro de vagas; invalidação por novo documento, versão, proposta, decisão
  ou revalidação; limite de entradas; chave por hora local para não envelhecer prazos;
- cache curto e single-flight na prontidão.

Resultado: carteira 1,09 s frio / 0,016 s quente; quadro 2,88 s frio / 0,009 s quente;
prontidão 0,64 s frio com cache de 60 s. Revisão agrupada mantém `revisao-prewarm`.

### 7. Estudos

Auditoria confirmou o domínio completo no escopo planejado: perfil, disciplinas,
tópicos, sessões com cronômetro server-side, progresso, revisão espaçada, flashcards com
imagem, questões, tentativas, simulados com tempo/retomada/finalização idempotente,
desempenho, exportação/importação, pacotes e mídia. Correção: conclusão de sessão
idempotente por id. “Caderno de erros” não existe no planejamento; o modo
`revisao_erros` cobre o caso. Nenhum endpoint depende de chave de fornecedor.

## Fora de escopo

Redesign/SPA, framework frontend, landing pages, assinatura/pagamento, app móvel,
integração forçada de APIs comerciais, cobertura universal, revisão manual em massa,
microsserviços, infraestrutura externa.

## Critério de encerramento

Todos os P0/P1 do inventário corrigidos; suíte verde; contrato verificado; prontidão
`ready` com pendências explícitas; gate aprovado; commit e push em
`radar-configuracao`. Itens P2 documentados, não bloqueantes.
