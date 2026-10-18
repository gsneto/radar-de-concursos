# Design — Fase 33: cobertura oficial, aquisição controlada e campos decisivos

Data: 2026-10-17. Base: Fase 32 (`767ca31`), schema v18, 1.434 testes.

## Problema

A base tinha **789 documentos**, mas a maior parte era página de agregador. O relatório da
Fase 30 dizia "85% dos concursos com documento"; o número real de concursos com **documento
oficial** era 36 de 634 (5,7%) e com **edital** 21 (3,3%). Além disso, 94 certames tinham
fonte oficial conhecida (FGV) e nenhum documento importado. Sem separar isso, qualquer avanço
de cobertura era ilusório.

## Decisões

### 1. Cobertura por certame com estado único e próxima ação

Onze estados mutuamente exclusivos, do mais completo ao menos completo:

`campos_confirmados` → `conflito` → `campos_candidatos` → `edital_extraido` →
`oficial_sem_extracao` → `oficial_sem_edital` → `identidade_pendente` →
`obtencao_nao_autorizada` → `oficial_nao_importado` → `apenas_agregador` → `sem_documento`.

- **Agregador não é documento oficial**: o funil tem `com_documento_qualquer` **e**
  `com_documento_oficial`, com denominador explícito.
- **Container de fonte não entra no denominador** (é área de retenção).
- **`historico` não é atribuído automaticamente**: não há prova de encerramento no modelo;
  presumir seria inventar. Fica documentado como limitação.
- `identidade_pendente` é medido à parte (`documentos_sem_identidade`), porque documento sem
  identidade não pertence a um certame e não pode inflar estado por concurso.

### 2. Aquisição controlada usando o conector existente

`radar/acquisition.py` não cria conector novo: usa a política (`source_policy`), o orçamento
(`budget`), o registro de documentos e o download já existentes.

- **Alvo**: certame sem documento, com observação de fonte **oficial habilitada**.
- **Filtro**: só `edital_abertura`, `edital_retificado`, `retificacao`.
- **Lista nominal é recusada por título**, mesmo rotulada "Retificação" (nomes/notas de
  candidatos não são regra do certame).
- **Simulação por padrão**: `plan_acquisition` mostra o que seria registrado/baixado.
- **Limite e retomada**: `max_contests`, `max_documents_per_contest`, checkpoint JSON,
  `next_index` no `fontes_consumo`.
- **Idempotência**: URL já registrada é ignorada; versão já baixada não é baixada de novo.
- **Custo**: zero; `budget.check_call` recusa qualquer chamada fora do orçamento.

Prioridade é **conservadora**: sem documento não há evidência de vagas indígenas, SI ou prazo.
A ordem usa apenas fonte oficial habilitada + identificador do certame + ausência de documento.
Nenhuma relevância temática é presumida.

### 3. Quatro campos decisivos com estados explícitos

- **Indígenas**: `explicito_imediato`, `apenas_reserva`, `explicito_sem_vaga_imediata`,
  `mencao_sem_quantidade`, `agregado_sem_modalidade`, `nao_mencionado`, `nao_pesquisado`.
  Total agregado **nunca** vira vaga indígena (`derivado_de_agregado=false` sempre).
- **Sistemas de Informação**: mapeia o vocabulário existente (`aceito_expressamente`,
  `abrangido_por_categoria`, `ambiguo`, `incompativel_com_requisito_explicito`) para
  `explicito`, `categoria_inclui_curso`, `area_correlata_interpretacao`, `outras_formacoes`,
  `nao_encontrado`, `extracao_incompleta`. Agrupa por **cargo reconciliado ou rótulo do próprio
  documento**, para um cargo de TI não contaminar os demais.
- **Prazos**: só documento autoritativo (edital/retificado/retificação/cronograma). O valor do
  documento mais recente é candidato; se o próprio documento mais recente tem mais de um valor,
  o estado é `ambiguo` e há `candidato_majoritario` (contagem de ocorrências, não decisão).
- **Local de prova**: `location.resolve_location` separa prova e lotação; `a_divulgar` é
  declaração; município de lotação nunca vira prova.

### 4. Conflitos entre versões

`radar/version_conflicts.py` compara propostas do mesmo concurso/campo/escopo:

- `retificacao_posterior` (documento mais recente difere do anterior; guarda vigente e
  substituídos);
- `divergencia_mesmo_documento` (o documento mais recente traz mais de um valor);
- `divergencia_sem_ordem` (sem data confiável);
- `escopo_diferente` (`a_divulgar` × local concreto);
- `equivalente` (ex.: `Salvador` × `Salvador/BA`; não é conflito).

Campos de concurso só comparam entre si; campos por cargo só quando o cargo está reconciliado.
Prazo de documento de resultado **não** compete com edital.

### 5. Correções de extração encontradas na prova real

- `exam_location` perdia a UF em "cidade de Porto Alegre – RS" (travessão não era separador) e
  aceitava o valor truncado. Corrigido: travessão é separador, UF vem do trecho e há teste.
- `location.parse_location` recusava "Rio de Janeiro/RJ" e "São Paulo/SP" porque o nome do
  município coincide com o estado. Corrigido **só** quando há UF explícita; sem UF, o nome
  continua tratado como estado.
- `_registration_dates` capturava período de **isenção** como prazo de inscrição. Corrigido:
  `_TEXT_PERIOD` exige contexto de inscrição e rejeita isenção mais próxima.

### 6. Lista nominal é visível, não apagada

Documento já persistido não é excluído (política do projeto). `documentos-nominais` lista os
documentos de lista nominal (206 na base) para decisão humana; aquisição e monitoramento novos
**não baixam** esse tipo. O caso real desta fase ("Retificação - Relação de inscritos
provisórios", 106 páginas) está registrado na prova real.

## Contratos

- `coverage_states.coverage_report(db)` → universo, estados, funil, fontes, restritas, nominais.
- `coverage_states.nominal_documents(db)` → documentos de lista nominal.
- `acquisition.targets(db)` / `plan_acquisition(...)` / `execute_acquisition(...)`.
- `decisive_fields.decisive_report(db, contest_ids=None, limit=200)`.
- `version_conflicts.conflicts(db, fields=None, contest_id=None, limit=500)`.

## Não objetivos

- Não criar conector novo, nem conta/credencial/pagamento.
- Não coletar em massa; lote pequeno, com limite, simulação e checkpoint.
- Não confirmar campo automaticamente.
- Não apagar documento, versão, evidência, proposta ou decisão humana.
- Não mudar o contrato de `GET /api/concursos` (18 campos).
