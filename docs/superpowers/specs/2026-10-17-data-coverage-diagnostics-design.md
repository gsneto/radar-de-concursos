# Design — Fase 25: cobertura de dados, diagnóstico de lacunas e enriquecimento

Data: 2026-10-17. Base: Fase 24 publicada (`a2dbcf6`), schema v14, 1004 testes.

## Problema real medido

A Fase 20 registrou 581 de 593 concursos como `sem_dados_suficientes`. A auditoria desta fase
reexecutou a consulta no estado atual e o número **permanece**: 581 `sem_dados_suficientes`,
10 `exige_confirmacao`, 2 `compatibilidade_desfavoravel`.

O funil medido, com consultas ao banco real (somente leitura):

| Etapa | Quantidade | Observação |
|---|---|---|
| Concursos | 593 | identidades descobertas |
| Concursos com algum documento | 499 | 94 sem documento nenhum |
| Documentos | 636 | 594 `kind='outro'`, 27 `edital`, 15 `retificacao` |
| Documentos de notícia/agregador | ~370 | `pciconcursos.com.br/noticias/...` |
| Concursos com edital oficial | 16 | 2,7% |
| Concursos com propostas extraídas | 15 | propostas só nascem de edital |
| Propostas | 751 | **100% marcadas como ambíguas** |
| Campos validados por humano | 0 | `revisoes_campo` e `valores_atuais` vazios |
| `cargos_identidade` | 0 | nenhuma identidade de cargo criada |

Conclusão central: a insuficiência **não** vem do cálculo de ranking nem da falta de parser.
Vem de três causas independentes e comprovadas:

1. **Cobertura de fonte (dominante).** 577 concursos não têm edital oficial; a maior parte só tem
   páginas de notícia do PCI. Nenhum parser resolve isso — falta o documento oficial.
2. **Funil de confirmação parado.** 100% das propostas são ambíguas e não há nenhuma revisão
   humana registrada; `cargos_identidade` está vazio, então a própria ferramenta de reconciliação
   de cargo (`reconcile_role_label`) não tem alvo para receber decisão humana.
3. **Extração correta em documento errado.** Um concurso tem 9 documentos `kind='edital'` do DOU
   (atos avulsos, 900–5000 bytes) e zero propostas — o vínculo documento↔concurso é ruim, não a
   extração.

Por isso a fase **não** mexe em ranking, não relaxa confirmação e não inventa campo. Ela
(i) torna a cobertura medível e explicável, (ii) classifica a causa de cada insuficiência,
(iii) prioriza o que é resolvível, e (iv) desbloqueia o caminho de confirmação criando as
identidades de cargo que faltam — sem resolver ambiguidade por conta própria.

## Decisões

### 1. Nenhum schema novo (permanece v14)

Já existem as estruturas necessárias: `propostas_campo`, `evidencias`, `revisoes_campo`,
`valores_atuais`, `cargos_identidade`, `reconciliacoes_cargo`, `auditorias_cobertura`,
`ciclos_fontes`, `tentativas_download`, `fila_confirmacao`.

- Métricas são **calculadas sob demanda** (determinísticas, somente leitura). Persistir snapshot
  criaria uma segunda fonte de verdade que envelhece e conflita com o banco.
- `auditorias_cobertura` continua sendo **exclusivamente** o log de conferência humana
  (`record_coverage`), não um cache de métricas.
- Criar tabela para cada métrica foi rejeitado: violaria a regra de não duplicar cobertura.

### 2. Reutilizar os estados existentes

Estado de um campo é derivado exatamente como em `priority._proposal_rows`:
`revisoes_campo.decision` > `ambiguo` (se `ambiguity_reason`) > `extraido`.
Nada de um segundo vocabulário de estados.

Dimensões de dados usam os nomes de campo que o pipeline realmente grava:
`immediate_vacancies`, `reserve_vacancies`, `indigenous_vacancies`,
`indigenous_reserve_vacancies`, `education`, `accepted_courses`, `si_compatibility`,
`exam_location`/`exam_municipio`/`exam_uf`, `work_location`, `registration_start`,
`registration_end`, `exemption_start`, `exemption_end`, `exemption_result_preliminary`,
`exemption_appeal`, `exemption_result_final`, `conteudo_*`.

`payment` **não** existe no modelo. Em vez de fingir uma dimensão, o relatório declara
`nao_mapeado` e explica — ausência de campo não é ausência de dado no edital.

### 3. Denominadores explícitos e escopo separado

Cada dimensão informa:

- `denominador`: concursos em que a informação **poderia** ser conhecida (têm edital analisado);
- `fora_do_denominador`: concursos `nao_pesquisado` (sem documento/edição analisada);
- `pct_confirmado`: confirmados ÷ denominador;
- `pct_com_dado`: (confirmado + extraído + ambíguo + conflito) ÷ denominador.

Nunca se divide por 593 para falar de "cobertura de editais". `nao_pesquisado` é reportado
separado e jamais somado como zero.

### 4. Causa por concurso, com hipótese marcada

`classify_cause` devolve uma causa primária entre valores fechados e uma lista de evidências.
Quando não há prova suficiente, a causa é `inconclusivo` — não se inventa motivo.

### 5. Identidades de cargo a partir do rótulo do próprio documento

Hoje 256 propostas estão bloqueadas por `cargo do documento não reconciliado: <rótulo>`, e
`cargos_identidade` está vazio, então `reconcile_role_label` (que exige um `role_id` existente)
não tem para onde apontar.

Ação implementada: `materialize_document_roles` cria a identidade de cargo **com o nome exato
evidenciado no documento**, contextualizada pelo concurso, de forma idempotente.

O que isso **não** faz:
- não casa rótulos por similaridade;
- não reatribui propostas;
- não marca nada como validado;
- não resolve a ambiguidade.

Isso é deliberado: a regra do domínio é que reconciliação é decisão humana. A função apenas
cria o alvo que faltava, com `dry_run` padrão. O ganho é verificável: o caminho de confirmação
passa de "impossível" para "possível", e o número de propostas elegíveis a reconciliação sai de
0 para 256.

### 6. Fila de lacunas explicável

Critérios com pesos declarados (não há pontuação opaca):

| Critério | Pontos | Por quê |
|---|---|---|
| tem edital analisado | 3 | é onde há dado extraível |
| janela de inscrição aberta/desconhecida | 2 | oportunidade ainda acionável |
| prazo confirmado próximo | 2 | urgência real |
| propostas ambíguas pendentes | 2 | revisão humana destrava em lote |
| tem documento mas não é edital | 2 | falta só o documento certo |
| falha de extração | 1 | custo técnico conhecido |
| campos decisivos ausentes | 1 por campo (máx. 3) | impacto no ranking |

Cada item traz `acao` (`coletar_documento_oficial`, `processar_documento`,
`revisar_proposta`, `reconciliar_cargo`, `investigar_falha`) e `motivo` textual, distinguindo
trabalho automático de trabalho humano.

## Contratos

Aditivos, sem tocar `GET /api/concursos` (18 campos):

| Método | Rota | Efeito |
|---|---|---|
| GET | `/api/cobertura` | auditoria completa (dimensões, funil, causas, recortes) |
| GET | `/api/lacunas?limit=N` | fila priorizada de lacunas |
| POST | `/api/cobertura/papeis` | materializa identidades de cargo (`dry_run` padrão) |

CLI: `cobertura`, `lacunas`, `cobertura-papeis`.

## Riscos e mitigação

| Risco | Mitigação |
|---|---|
| Métrica virar número de vaidade | denominador explícito, `nao_pesquisado` separado, sem percentual sobre 593 |
| Tratar agregador como prova | `edital_oficial` só conta `kind='edital'`/`tipo_documental` de edital |
| Criar papel duplicado | idempotente por `(contest_id, name, specialty IS NULL)` |
| Resolver ambiguidade por conta própria | proibido: só cria alvo; reconciliação continua humana |
| Query pesada no servidor | uma passada por tabela, sem N+1 por concurso |
| Quebrar ranking/preferências | nenhuma alteração em `ranking.py`/`priority.py` além de expor `proposal_rows` |

## Critérios de aceite

- Auditoria reproduzível no banco real, com os mesmos números da tabela acima.
- Causa classificada para os 593 concursos, com `inconclusivo` onde não há prova.
- Fila de lacunas determinística e explicável.
- `materialize_document_roles` idempotente, com `dry_run` que não grava.
- Contrato v1 intacto; suíte completa verde; revisão independente sem críticos.
