# Design — Fase 35: identidades de cargo, conflitos reais, prazos e destino nominal

Data: 2026-10-18. Base: Fase 34 (`0489ce6`), schema v19 → **v20**. 1.531 testes.

## Problema

A mesa da Fase 34 mostrou 273 grupos, mas **0 cargos reconciliados**: 246 rótulos de cargo
distintos em 28 concursos, cada um vindo do texto do documento (`cargo do documento não
reconciliado: X`). Sem identidade canônica, o mesmo cargo aparece como "MERENDEIRO",
"MERENDEIRO ESCOLAR" e "400 Merendeiro" em grupos separados, e os campos herdados
(`education`, `requirements`) não podem ser atribuídos com honestidade.

Além disso: 53 grupos de valores divergentes sem causa declarada (retificação? escopo?
documento diferente?), 191 documentos nominais sem destino operacional definido, e prazos
extraídos sem verificação de que a data ainda vale.

A fase responde quatro perguntas — sem confirmar nada automaticamente:

1. Que **tipo de rótulo** é este (cargo, código, abreviação, especialidade, ou não é cargo)?
2. Ele corresponde a alguma **identidade canônica** já existente?
3. Quando dois documentos divergem, **por quê**?
4. Um prazo extraído ainda é **aplicável**? E qual o destino de um documento nominal?

## Decisões

### 1. Natureza vem de marcador explícito, não de julgamento

`radar/role_identity.py:classify_label` reconhece sete naturezas por marcadores no próprio
texto:

| Natureza | Marcador | Exemplo |
|---|---|---|
| `cargo_com_codigo` | prefixo numérico + nome | `400 Assistente Administrativo` |
| `codigo_sem_nome` | só número | `400` |
| `abreviacao` | sigla/romano + área | `PROFESSOR PII – EDUCAÇÃO FÍSICA` |
| `especialidade` | "ÁREA DE ATUAÇÃO", "ESPECIALIDADE" | `TÉCNICO ... ÁREA DE ATUAÇÃO EM ADMINISTRAÇÃO` |
| `nao_e_cargo` | rótulo de outro campo | `local de prova candidato`, `conteúdo programático candidato` |
| `generico_sem_cargo` | genérico sem nome | `cargo não informado` |
| `cargo_literal` | resto | `MERENDEIRO ESCOLAR` |

O classificador não decide se o rótulo é "o mesmo" cargo: só descreve o que o texto mostra.
Um nome longo em maiúsculas **não** é abreviação (regressão coberta por teste: a regra
antiga classificava qualquer nome iniciado por "P" como abreviação).

### 2. Sugestão é estrutural, não probabilística

`_suggest` compara o rótulo com as identidades **do mesmo concurso** e pontua por evidência
estrutural explícita:

- `nome_identico` (+40), `nome_identico_sem_codigo` (+35), `codigo_oficial` (+40),
  `prefixo_de_nome` (+25), `especialidade_confere` (+15).

Regras: só candidatos com pontuação **≥ 25**; no máximo **5**; o candidato é ordenado por
nível de evidência (exata → alias → provável), depois por pontuação; empate no melhor nível
com identidades distintas rebaixa os empatados para `ambigua` (empate não é escolha). Código
igual com nome incompatível não vira `alias`; recebe fator de alerta e fica `provavel`.
A pontuação é chamada de "pontuação estrutural" em toda a UI e API — nunca "probabilidade".

Estados de correspondência: `exata`, `alias`, `provavel`, `ambigua`,
`duplicata_de_identidade`, `rejeitada`, `confirmada`, `evidencia_insuficiente`, `nao_e_cargo`.

### 3. Duplicata de identidade é decisão, não fusão automática

Se o concurso tem duas linhas canônicas com o mesmo nome normalizado e código, os rótulos
que apontam para elas recebem `duplicata_de_identidade` e ação
`consolidar_identidade_duplicada`. O sistema **não** escolhe qual linha manter nem funde
dados: consolidar muda vínculos e histórico, então é decisão humana registrada.

### 4. Decisão de reconciliação é append-only, com estado e vínculo

`decide_reconciliation` grava em `reconciliacoes_cargo` com `state`
(`confirmada|rejeitada|ambigua|reaberta`), `nature`, `evidence_json`, `reviewer`, `reason`,
`reconciled_at` e `previous_id`. Regras:

- `confirmada` exige `role_id` do **mesmo** concurso e evidência do rótulo;
- mudar o vínculo de uma confirmação vigente exige uma decisão `reaberta` anterior;
- `expected_previous_id` protege contra decisão concorrente (quem decidiu primeiro vence);
- `dry_run` é o padrão em API e CLI; nada grava sem `dry_run: false` explícito;
- o histórico é lido por `reconciliation_history` e mostra a decisão vigente + anteriores.

`review._reconciled_map` passou a considerar **apenas** `confirmada` — antes qualquer linha
na tabela contava como vínculo, o que tratava rejeição como confirmação.

### 5. Criar identidade a partir do rótulo é ação separada

`create_role_for_label` só aceita naturezas "cargolike" (`cargo_literal`,
`cargo_com_codigo`, `abreviacao`, `especialidade`) e exige observação de origem do concurso.
Rótulo que não é cargo (`nao_e_cargo`, `generico_sem_cargo`, `codigo_sem_nome`) é recusado —
criar identidade a partir de "local de prova" poluiria o catálogo.

### 6. Conflito tem causa declarada antes de ter vencedor

`radar/conflict_review.py:classify_group` classifica o grupo de propostas divergentes:

| Causa | Critério |
|---|---|
| `escopo_diferente` | propostas de cargos/escopos distintos |
| `cargos_diferentes_sem_identificacao` | rótulos de cargo diferentes sem identidade |
| `variacao_de_extracao` | mesmo documento, mesma página, texto normalizado equivalente |
| `retificacao_posterior` | documento posterior retifica e altera o campo |
| `documentos_com_data_distinta` | documentos com datas distintas e valores distintos |
| `documentos_diferentes_sem_ordem` | documentos sem ordem temporal confiável |
| `mesmo_documento_valores_distintos` | mesmo documento, valores realmente distintos |
| `evidencia_insuficiente` | falta documento/evidência para decidir |

Prioridade 1..4 (`FIELD_PRIORITY`) ordena por impacto decisório (vagas, requisitos, prazos,
demais). Retificação só conta como alteração quando **sua própria proposta** difere do valor
do edital de abertura; retificação que não menciona o campo não muda nada.

### 7. Prazo é candidato temporal, não vigência

`radar/deadline_review.py` agrupa oito prazos (`inscricao_inicio/fim`, `isencao_inicio/fim`,
`recurso_isencao`, `resultado_isencao_preliminar/final`, `data_prova`) e classifica:
`futuro`, `hoje`, `expirado`, `data_invalida`, `sem_data`.

- Só documentos **autoritativos** (`edital_abertura`, `edital_retificado`, `retificacao`,
  `cronograma`) sustentam prazo; resultado/comunicado não.
- Data futura **não comprova vigência**: a fonte precisa sustentar aplicabilidade.
- Sem documento autoritativo, o item aparece como `sem_data` com próxima ação
  "buscar edital/cronograma" — não é omitido.
- Cada item carrega trecho, página, versão, sha256, publicação, coleta e decisão anterior.
- Prazos de **cargos diferentes** são itens separados (`escopo`/`escopo_rotulo`): um prazo de
  cargo não é o prazo do concurso. Valor escolhido por humano vence a data de publicação, e
  proposta rejeitada não sustenta prazo.

### 8. Destino nominal é simulação

`radar/nominal_destination.py` propõe um destino por documento nominal, sem executar nada:

| Destino | Critério |
|---|---|
| `reconciliar_identidade` | documento sem identidade de concurso |
| `revisar_politica_antes_de_agir` | política de fonte não verificada/desconhecida |
| `retirar_da_fila_operacional` | já tem arquivo baixado (privacidade: não exibir) |
| `manter_metadados_na_fila` | sem conteúdo: metadados bastam, sem download novo |

O relatório é `modo: simulacao` e declara que nenhum documento é arquivado, apagado ou
movido — o projeto ainda não tem arquivamento reversível. Listas nominais são dados
pessoais: nada é baixado para exibição nem copiado para a base.

### 9. Schema v20

`reconciliacoes_cargo` foi reconstruída: `role_id` nullable (rejeição não tem cargo),
`state`, `nature`, `evidence_json`, `previous_id`, índice `idx_reconciliacoes_contest`.
Estados válidos: `confirmada|rejeitada|ambigua|reaberta`. Migração v19→v20 preserva linhas
existentes como `confirmada` (o comportamento antigo só gravava vínculo) e é idempotente.
`_READABLE_VERSIONS` deixou de aceitar v18 e v19: as rotas de leitura exigem v20, e a
migração v19→v20 continua disponível em `migrate_document_schema`.

## Limites declarados

- 246 rótulos é o universo atual; a fase não inventa cargos que o documento não nomeia.
- 36 rótulos com evidência insuficiente continuam pendentes — não há identidade candidata.
- 36 duplicatas de identidade não são fundidas automaticamente.
- 74 prazos expirados continuam listados (histórico é útil), mas não são "vigentes".
- Nenhum destino nominal foi executado; nenhuma decisão humana foi fabricada.
- O contrato `GET /api/concursos` v1 (18 campos) não mudou.
