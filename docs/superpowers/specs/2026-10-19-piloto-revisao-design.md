# Design — Fase 43: piloto operacional de revisão e reconciliação assistida

Data: 2026-10-19. Base: Fase 42 (`7f758d9`), schema v21 (inalterado). 1.833 testes.

## Problema

A Fase 42 entregou a revisão agrupada, mas ainda faltava provar a operação: um lote pequeno,
com casos difíceis, progresso por decisão real, reconciliação assistida e proteção contra
dados obsoletos. Também faltava explicitar a granularidade do Anexo II da SEDUC-PA — 381
linhas não são 381 cargos.

## Decisões

### 1. Piloto determinístico, com casos e não com conveniência

`radar/pilot.py` seleciona 16 linhas (faixa 10–20) com cotas explícitas:

- 1 linha com PI > 0 (vaga exclusiva indígena);
- 1 com PPIQ > 0 e 1 com PI/PQ > 0 (unificadas);
- 2 linhas com zero explícito nas três colunas indígenas;
- 2 linhas que atravessam página (rótulo completado);
- diversidade de cargo, formação e regional, com no máximo duas linhas por regional;
- completa com as primeiras linhas restantes, na ordem documental.

A seleção é estável: a mesma base produz os mesmos `linha_id`. A ordem de coleta é
documental (página, offset), nunca por valor ou prioridade.

Cada ficha explica por que a linha entrou, qual documento/versão/hash a sustenta, os campos
com evidência, os campos incertos, o estado da identidade e o efeito de cada decisão.

### 2. Granularidade: cargo + formação é identidade; regional é dimensão

`radar/identity_suggestions.py` lê o contexto do parser (não o rótulo achatado) e propõe:

- **26 identidades candidatas** (7 cargos × formações) para 381 linhas em 24 regionais;
- **regional** como dimensão da oportunidade, nunca parte da identidade;
- **linha documental** como oportunidade individual.

Recomposição de palavra partida só ocorre quando a forma reconstruída **existe no edital**
(vocabulário dos blocos). "Administraçã" + "o" → "Administração" (19 ocorrências no
documento); "Especialista" + "em" nunca é juntado. Cargo terminando em conectivo recebe a
formação como continuação do nome (não como especialidade). Formação igual/prefixo/sufixo do
cargo é repetição, não especialidade.

Nada é gravado: a sugestão exibe texto, trecho e avisos; a reconciliação continua exigindo a
decisão humana de `role_identity`.

### 3. Decisão por campo, sem confirmação da linha

A UI do piloto reusa o detalhe do grupo: cada botão envia **um** `proposal_id` para o
endpoint existente, com justificativa e `evidence_sha256`. Não existe ação de linha inteira;
o progresso conta apenas decisões registradas (`validado`/`rejeitado`), não linhas abertas.

### 4. Contexto preservado e retomável

O piloto grava concurso e linha no `location.hash` (`#piloto=…&linha=…`); recarregar a
página restaura painel e linha aberta. O `evidence_sha256` de cada proposta é enviado na
decisão, e o servidor revalida dentro da transação — evidência alterada é recusada.

### 5. Concorrência de servidor

O servidor passou a usar `ThreadingHTTPServer` (cada requisição com sua conexão SQLite).
Antes, um painel lento bloqueava todos os outros e a revisão parecia travada. Escritas
continuam serializadas pelo `BEGIN IMMEDIATE`.

### 6. Desempenho medido, cache opcional

- `groups` frio: **3,45 s**; quente: **0,33 s** (cache em processo por versão + parser).
- `pilot.report` frio: **3,6 s**; quente: **0,37 s** (uma leitura de grupos + vocabulário
  em cache).
- `python -m radar revisao-prewarm --contest-id …` aquece sem gravar (`gravacoes: 0`).

## Limites declarados

- Sugestão de identidade não é reconciliação; confirmar campos não confirma identidade.
- Soma correta não valida semântica; divergência não autoriza trocar o total.
- Vaga unificada nunca é contada como exclusiva indígena.
- Nenhuma decisão humana é criada pelo piloto, pela UI ou pelos testes na base real.
