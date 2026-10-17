# Design — Fase 29: catálogo universal de fontes, políticas e aquisição multicanal

Data: 2026-10-17. Base: Fase 28 + ajuste IBFC publicados (`c6be5ce`), schema v17, 1281 testes.

## Problema

O Radar cresceu por fases: cada fonte virou um módulo com regras próprias, sem um lugar único
que responda “o que esta fonte oferece, posso guardar isso, quanto custa, quando foi testada?”.
Isso cria três riscos concretos:

1. **persistência sem base**: um scraper MIT não autoriza armazenar o conteúdo de terceiros;
2. **custo invisível**: uma API com plano gratuito pode virar cobrança sem ninguém notar;
3. **falsa integração**: existir um arquivo de configuração não significa que a fonte funciona.

## Decisões

### 1. Catálogo em código, estado em banco

`radar/source_catalog.py` é a fonte de verdade das **políticas** (versionada no Git, revisável em
PR). O banco guarda apenas **fatos de execução**: estado, consumo, histórico de revisão. Assim a
política não muda por acidente e toda alteração tem diff.

Cada fonte declara: id, nome, fornecedor, categoria, natureza, domínios, entrada, documentação,
acesso, cobertura, **permissão por tipo de conteúdo**, exibição, redistribuição, cache, intervalo
mínimo, rate limit, limite mensal, custo (com `verified`), variável de credencial, retenção,
deduplicação, termos, estado, conector, confiança, data de revisão e responsável.

### 2. Permissão é por tipo de conteúdo, não por fonte

Metadado, URL, documento, questão, gabarito, notícia e dado aberto têm decisões independentes.
Exemplo real do catálogo: no PCI, `metadados` e `url` são persistíveis (fatos de descoberta), mas
`noticia` é `persistencia_nao_verificada` (conteúdo editorial de terceiro). Em uma fonte de notícia
como o JC Concursos, `noticia` é `uso_transitorio`: pode ser lida para descobrir, não pode ser
gravada.

`persistencia_permitida` exige **evidência** (URL + data) — o validador do catálogo recusa
permissão sem evidência. Termos ambíguos ⇒ `persistencia_nao_verificada`, tratada como proibida.

### 3. Política como porta única (`radar/source_policy.py`)

`require_persist(fonte, tipo)` é a única forma de autorizar gravação. Ela também considera o
**estado da fonte**: `aguardando_credencial`, `bloqueada` ou `aguardando_validacao_de_uso`
bloqueiam mesmo quando o tipo tem permissão. `redact_for_log` remove corpo de conteúdo
transitório de logs/relatórios.

Rejeitado: confiar em convenção (“o módulo X só grava coisa boa”); permissão global por fonte;
herdar permissão de metadado para documento.

### 4. Orçamento explícito (`radar/budget.py`)

Cada execução grava seus limites em `fontes_consumo.limits_json` e verifica **antes** de cada
chamada: chamadas, itens, créditos e valor. Custo pago exige `cost.verified` **e**
`cost.authorized`; sem isso, a chamada é recusada com `custo_nao_verificado` — nunca se inventa
preço. O consumo real é registrado depois da resposta; falha não cobra. Checkpoint permite
retomar paginação.

### 5. Conector declara capacidade, não finge equivalência

`radar/connectors.py` define a interface (identidade, categoria, capacidades, requisitos,
tipos de conteúdo, política, disponibilidade, descoberta, detalhes, paginação, falhas, custos).
Os conectores existentes são **adaptados** por um invólucro que reutiliza
`monitoring.default_sources()` — nenhuma lógica duplicada. Agregador declara só `descobrir` e
`metadados`; nunca `edital`.

`normalize()` preserva identificador original, URL, fonte, datas, oficialidade, incerteza e
evidência; `raw` só existe se a política permitir. `guard_persistence()` separa o que pode ser
gravado do que não pode.

### 6. Integração real escolhida: IBGE Localidades

O Portal de Dados Abertos respondeu **401** sem credencial e o Conecta é catálogo HTML; as APIs
comunitárias de concursos apenas raspam o ConcursosNoBrasil (código MIT, conteúdo de terceiro).
A fonte estruturada que passou em licença, acesso e uso concreto foi o **IBGE**:

- API pública, sem chave, dados abertos oficiais;
- 5.570 municípios + 27 UFs;
- uso concreto: conferir `exam_location`/`exam_municipio`/`exam_uf` contra a lista oficial.

O parecer (`confere_ibge`, `uf_divergente`, `nao_encontrado`, `sem_snapshot`) **não altera
propostas**: é insumo de revisão. Na base real, encontrou `Taboão/SP` (município inexistente;
o correto é Taboão da Serra) — sinal real de extração a revisar.

### 7. Migração v18 aditiva

Quatro tabelas novas (`fontes_estado`, `fontes_consumo`, `fontes_revisoes`, `localidades_ibge`)
e nenhuma alteração em tabelas históricas. `fontes_consumo.limits_json` guarda os limites da
execução para que `check_call` não recalcule com defaults diferentes.

## Contratos

| Método | Rota | Efeito |
|---|---|---|
| GET | `/api/fontes` | catálogo + estado operacional + revisão vencida |
| GET | `/api/fontes/<id>` | conector, política por tipo e histórico de revisão |
| GET | `/api/fontes-consumo` | consumo por execução (filtro por fonte) |

CLI: `fontes [--validar]`, `fontes-consumo`, `fontes-revisar`, `fontes-politica`,
`localidades [--validar] [--force]`.

Mutações (revisão de política, snapshot IBGE) ficam na CLI local; não há rota que gaste dinheiro.
`GET /api/concursos` permanece com 18 campos.

## Critérios de aceite

- Catálogo válido e auditável, com permissão por tipo e evidência obrigatória.
- Persistência proibida/não verificada nunca grava (teste).
- Custo não verificado nunca é cobrado (teste).
- Orçamento por execução respeita chamadas/itens/créditos/valor.
- Conectores existentes registrados sem duplicar lógica.
- Uma fonte estruturada real integrada com uso concreto e parecer que não confirma campo.
- Migração sem perda, contrato v1 intacto, suíte e revisão aprovadas.
