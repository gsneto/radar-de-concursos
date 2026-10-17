# Design — Fase 27: identidade canônica de certame e piloto oficial (IBFC)

Data: 2026-10-17. Base: Fase 26 publicada (`c7cb1a3`), schema v14, 1120 testes.

## Diagnóstico que orientou a fase

A Fase 26 deixou três fatos medidos:

1. **A associação do DOU está errada por construção.** `radar/dou_source.py:27` define
   `DOU_COMPETITION_ID = "DOU-S3"` — a **seção** do diário — e `discover()` entrega todos os atos
   da edição com a mesma `observation_id`. Medido no banco real: o concurso `54568dbc…` tem 10
   documentos de **10 órgãos distintos** (UFMA, UFSCar, Hemobrás, IFAM, TCU, UnB, Marinha/Amazônia
   Azul, CRI-15, CRECI-ES, Prefeitura de Sinop) e **zero propostas**. Não é falha de extração: é
   identidade artificial.
2. **O funil trava antes da extração.** 597 certames, 503 com documento, **18 com edital
   oficial**, 16 com propostas, **0 confirmados**. A causa dominante é `apenas_agregador` (477):
   a maior parte dos "concursos" só tem página de agregador, que nunca é ato oficial.
3. **Volume não era o gargalo.** As fases anteriores já rejeitaram quatro scrapers por isso. O
   que faltava era (a) separar identidade de certame de identidade de fonte e (b) provar, com uma
   fonte oficial de verdade, que a integração ponta a ponta funciona.

## Decisões

### 1. Container de fonte, não `documentos.contest_id` nulo

Um identificador externo que descreve **publicação** (seção de diário) ou **catálogo** (lista de
certames) não é um certame. A fase introduz um estado explícito na identidade:

- `concursos_identidade.estado_identidade ∈ {'certame','container_fonte'}` (padrão `certame`);
- `observacoes_concurso.tipo_identidade ∈ {'certame','secao_publicacao','catalogo','desconhecida'}`.

O container é uma **área de retenção**: recebe documentos, nunca propostas, e fica fora de toda
métrica de certame (cobertura, prioridade, saúde, associações suspeitas).

Alternativas rejeitadas:

| Alternativa | Por que não |
|---|---|
| Tornar `documentos.contest_id` anulável | exige reconstruir a tabela (SQLite não altera nulidade), quebrando FKs e o caminho de leitura v1 |
| Tabela paralela `documento_concurso` | duplica o modelo existente (`observation_id` + `contest_id`) e cria duas verdades |
| Criar um certame por documento do DOU | inventa identidade sem evidência — proibido pelo domínio |

`classify_external_id()` decide por regra explícita (regex de seção, prefixo de catálogo), nunca
por heurística de título.

### 2. Associação append-only, com decisão humana preservada

Nova tabela `associacoes_documento` (id, document_id, contest_id, state, evidence_json, score,
decided_by, decided_at, note, supersedes_id). Estados: `pendente`, `candidata`, `ambigua`,
`confirmada`, `rejeitada`.

- `register_document` grava `pendente` automaticamente para documento que entra em container —
  o vínculo não fica implícito nem silencioso.
- `record_association` exige `decided_by` e `note`; nunca sobrescreve: insere nova linha e aponta
  `supersedes_id` para a anterior.
- Container **não é alvo** de associação (`ValueError`): associar a um container reproduziria o
  defeito original.
- `apply_repair` só age sobre associações `pendente`. Decisão humana (`confirmada`, `rejeitada`)
  nunca é desfeita por reexecução — regressão coberta por teste.

### 3. Reparação idempotente e auditável

`repair_plan()` é somente leitura e só emite ação para concurso que **ainda precisa** mudar.
`apply_repair()` reaplica o plano dentro de `BEGIN IMMEDIATE`, com `decided_by` e `note`
obrigatórios, e devolve contagens. Segunda execução: zero ações.

Nenhum certame é criado automaticamente. Nenhuma proposta é apagada: as 0 propostas do container
DOU permanecem 0 porque nunca existiram.

### 4. Piloto IBFC com identidade por certame

Fonte escolhida por critérios medidos, não por preferência:

- HTML estático no catálogo e no detalhe (sem navegador);
- identidade externa `ibfc-<id>` **por certame** — o oposto do DOU;
- anexos em `anexos-r2.selecao.net.br`, host **já autorizado** pelo projeto (mesma plataforma do
  Quadrix): nenhuma nova autorização de rede;
- publica edital de abertura, retificações, convocações e resultados com data.

**Limite de robôs respeitado.** `anexos.cdn.selecao.net.br/robots.txt` responde `Disallow: /`.
O documento é registrado com URL, título, tipo e data — o usuário chega ao original — mas o byte
**não** é baixado (`fetch_allowed=False`, motivo `robots_disallow_anexos_cdn`) e nenhuma versão é
criada. O resumo do ciclo expõe `downloads_bloqueados` para que o bloqueio seja visível, não
silencioso.

`download_new_only=True` no ciclo: sem isso a rotação de versões rebaixaria páginas de banca a
cada execução. O refresh de certame conhecido atualiza `last_checked_at`, para a rotação não
congelar.

### 5. Bug latente encontrado e corrigido

`document_store._FIELDS` não continha `exam_municipio`/`exam_uf` (nem `work_municipio`/`work_uf`).
Consequência real: `record_analysis` levantava `ValueError: escopo ou campo inválido` e **abortava
a versão inteira** de qualquer documento novo com local de prova — defeito herdado da Fase 26 que
só apareceria na próxima coleta com edital. Corrigido e coberto por `PersistenceTest`.

## Contratos (aditivos)

| Método | Rota | Efeito |
|---|---|---|
| GET | `/api/identidade` | auditoria de identidade + plano de reparação (somente leitura) |
| GET | `/api/associacoes/fila?state=&limit=` | fila de documentos que precisam de decisão |
| POST | `/api/associacoes/<document_id>` | registra decisão (append-only; `dry_run` padrão falso) |
| POST | `/api/identidade/reparar` | aplica o plano (`dry_run` padrão **verdadeiro**) |

CLI: `identidade`, `identidade-reparar --decided-by --note [--apply]`, `associacoes-fila`,
`associacao-revisar`, `ibfc-piloto [--apply] [--analyze]`.

`GET /api/concursos` permanece com os **18 campos** — teste agora confere os nomes, não só a
contagem.

## Critérios de aceite

- Concurso de seção do DOU deixa de ser certame e passa a container, sem perder documento.
- Documentos do container ficam com associação `pendente` rastreável; nenhum certame inventado.
- Reparar duas vezes não altera nada e não desfaz decisão humana.
- Container fora de cobertura, prioridade, saúde e diagnóstico de associação.
- Um certame oficial novo (IBFC) entra ponta a ponta: identidade, documentos, versões, propostas
  ambíguas — e **0** confirmações automáticas.
- Anexo com `robots.txt` restritivo não é baixado, e isso aparece no resumo do ciclo.
- Nenhuma mudança no contrato v1.
