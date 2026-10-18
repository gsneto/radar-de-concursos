# Pesquisa — Fase 35: identidades de cargo, conflitos, prazos e destino nominal

Data: 2026-10-18. Base real: `data/radar.sqlite3` (v20, 950 documentos, 911 versões,
14.823 blocos, 6.199 propostas, 0 revisões). Diagnóstico sempre sobre a base real; decisões
de escrita validadas em cópia isolada.

## 1. Universo de rótulos de cargo

A Fase 34 agrupou oportunidades por concurso × cargo, mas sem identidade canônica. O rótulo
vem do texto do documento e chega como `cargo do documento não reconciliado: <texto>`.

Medição (`label_inventory`, 120 ms): **246 rótulos distintos em 28 concursos**.

| Natureza | Rótulos | Leitura |
|---|---|---|
| `cargo_com_codigo` | 89 | `412 Terapeuta Ocupacional Escolar Nível Superior` |
| `nao_e_cargo` | 85 | `conteúdo programático candidato (conteudo_disciplina)` |
| `cargo_literal` | 34 | `AGENTE DE APOIO EDUCACIONAL` |
| `codigo_sem_nome` | 18 | `200` |
| `abreviacao` | 12 | `PROFESSOR PII – EDUCAÇÃO FÍSICA` |
| `especialidade` | 8 | `TÉCNICO DE NÍVEL SUPERIOR – ÁREA DE ATUAÇÃO EM ADMINISTRAÇÃO` |

O achado que mais reduz trabalho: **85 dos 246 rótulos não são cargos**. São conteúdo
programático, local de prova, escolaridade declarada e total do cronograma que entraram no
campo de requisito durante a extração. Tratá-los como cargo criaria 85 identidades falsas.

Estados após sugestão estrutural:

| Estado | Rótulos | Ação proposta |
|---|---|---|
| `exata` | 89 | `confirmar_correspondencia` |
| `duplicata_de_identidade` | 36 | `consolidar_identidade_duplicada` |
| `evidencia_insuficiente` | 36 | `revisar_documento` (18) / `criar_identidade_a_partir_do_rotulo` (18) |
| `nao_e_cargo` | 85 | `nao_reconciliar_como_cargo` |

Exemplo de duplicata: `207 PROFISSIONAL DE SUPORTE TÉCNICO (PST)-ASSISTENTE ESPECIALIZADO`
aponta para 16 identidades duplicadas no mesmo concurso. Fundir automaticamente perderia
histórico e vínculo de 16 linhas; por isso a fase apenas **sinaliza**.

Exemplo de evidência insuficiente: `PROFESSOR ORIENTADOR DE ESTÁGIO EM SAÚDE ...` é
`cargo_literal`, mas o concurso tem **0 cargos** cadastrados — não há candidato. A ação é
criar identidade (decisão humana), não sugerir um cargo inexistente.

## 2. Por que a sugestão não pode ser probabilística

Tentamos, na fase anterior, ordenar por semelhança textual. O resultado é instável: nomes
longos e truncados (por extração de tabela) produzem similaridade alta com cargos errados.
A alternativa adotada é **evidência estrutural auditável**: nome idêntico, nome idêntico
sem código, código oficial, prefixo de nome e especialidade — cada um com pontos declarados
e exibidos. Código igual com nome incompatível não supera um nome compatível: recebe fator
de alerta e fica `provavel`. Empate na maior pontuação com identidades distintas vira `ambigua`.

Consequência: 89 rótulos têm correspondência `exata` (nome normalizado idêntico), não
"provável". O que não tem marcador fica `evidencia_insuficiente` em vez de receber um
palpite com aparência de certeza.

## 3. Conflitos: 53 grupos, 6 causas

A Fase 34 listava valores divergentes, mas não dizia **por quê**. Reclassificando os 53
grupos (`conflict_groups`, 115 ms):

| Causa | Grupos |
|---|---|
| `retificacao_posterior` | 6 |
| `mesmo_documento_valores_distintos` | 13 |
| `documentos_diferentes_sem_ordem` | 17 |
| `escopo_diferente` | 8 |
| `cargos_diferentes_sem_identificacao` | 5 |
| `documentos_com_data_distinta` | 4 |

Prioridade: 15 grupos em P2, 24 em P3, 14 em P4.

O achado importante: **só 6 dos 53 são retificação posterior** — onde o documento mais novo
altera de fato o campo. Outros 17 não têm ordem temporal confiável (e 7 deles são
retificações que **repetem** o valor do edital de abertura: repetir não é alterar). Outros 8 são escopo diferente (cargos distintos
comparados como se fossem o mesmo). Só 13 são divergência real no mesmo documento.

Um grupo P2 típico (`cargos_diferentes_sem_identificacao`, campo `education`) tem três
valores: `Licenciatura Plena com habilitação específica para a disciplina`,
`Licenciatura Plena com habilitação para o magistério...`, etc. Os trechos descrevem
requisitos de cargos diferentes; a próxima ação correta é identificar o cargo de cada
requisito, não escolher um valor.

## 4. Prazos: 104 candidatos, 16 futuros

`deadline_report` (120 ms): **104 itens** em 28 concursos.

| Estado | Itens |
|---|---|
| `expirado` | 74 |
| `futuro` | 16 |
| `sem_data` | 14 |

Por grupo: `inscricao_fim` 22, `inscricao_inicio` 22, `recurso_isencao` 15,
`resultado_isencao_final` 13, `resultado_isencao_preliminar` 13, `isencao_inicio` 12,
`isencao_fim` 7.

Os 16 futuros (referência 2026-10-18) incluem:

- 2026-10-21/22 — resultado preliminar e recurso de isenção (2 concursos);
- 2026-10-27/28 — resultado e recurso de isenção (cronograma);
- 2026-10-30 — resultado final de isenção (3 concursos);
- 2026-11-05 — resultado final de isenção;
- 2026-11-13 e 2026-11-26 — fim de inscrições;
- 2027-02-21, 2027-04-04, 2027-04-11, 2027-04-18 — início/fim de inscrições de concursos
  com cronograma longo.

Verificação dos 7 candidatos a `inscricao_fim` levantados na Fase 33: **todos estão no
passado** (2026-10-08, 2026-08-07, 2026-08-12, 2023-03-06, 2023-03-16, 2026-04-16,
2026-02-03). Nenhum era prazo aberto — o que confirma a decisão de não tratar data extraída
como vigência.

Os 14 `sem_data` são concursos cujo único documento com o campo é resultado/comunicado, ou
cujo edital não foi importado. Aparecem com próxima ação explícita em vez de desaparecer.

## 5. Documentos nominais: 191, dois destinos dominantes

`nominal_destinations` (29 ms): 191 documentos.

| Destino | Documentos |
|---|---|
| `retirar_da_fila_operacional` | 156 (já têm conteúdo extraído) |
| `manter_metadados_na_fila` | 35 (só metadados) |

Não houve `reconciliar_identidade` nem `revisar_politica_antes_de_agir` nesta base: todos os
191 têm concurso associado e política de fonte conhecida. O destino é **simulação**: nada é
arquivado, apagado ou movido.

Privacidade: listas nominais são dados pessoais. O relatório não copia conteúdo, não baixa
para exibir e não sugere publicar. `retirar_da_fila_operacional` significa "não precisa de
ação operacional", não "apagar".

## 6. Dois defeitos encontrados na validação real

1. **Sombra de parâmetro em `deadline_report`**: o laço de documentos usava
   `for contest_id, ...`, sobrescrevendo o parâmetro de filtro. Com filtro por concurso o
   relatório devolvia **0 itens** na base real. Corrigido renomeando a variável do laço e
   coberto por teste de regressão (`test_filtro_por_concurso_nao_e_sobrescrito`).
2. **`confirmada` fora do vocabulário**: após uma decisão, `label_inventory` levantava
   `KeyError` em `MATCH_LABELS`, e `GET /api/reconciliacao` respondia **400** — a UI não
   atualizava e o histórico ficava vazio na tela. O HTML e o JS já previam o estado; faltava
   no Python. Corrigido e coberto por dois testes (fila e API).

Ambos apareceram só na validação de ponta a ponta com dados reais — os testes de unidade
originais usavam um concurso só e nenhuma decisão prévia.

## 7. O que foi rejeitado

- **Fusão automática de duplicatas**: muda vínculo de 16 identidades sem decisão humana.
- **Distribuir `vagas_total_publicado` entre cargos**: é agregado do edital, não soma
  derivável (decisão herdada da Fase 32).
- **Tratar data futura como prazo vigente**: a fonte pode ter sido retificada depois.
- **Baixar listas nominais para exibir**: dados pessoais; metadados bastam para triagem.
- **Similaridade textual como ranking**: instável com nomes truncados; substituída por
  marcadores estruturais.
