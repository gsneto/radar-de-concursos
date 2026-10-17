# Design — Fase 28: revisão humana, confirmação e recuperação documental

Data: 2026-10-17. Base: Fase 27 publicada (`9de3573`), schema v15, 1185 testes.

## Diagnóstico que orientou a fase

A infraestrutura documental estava completa, mas o **fluxo de confirmação** não existia:

- **2023 propostas**, todas com `ambiguity_reason` e **0 revisões**, **0 valores vigentes**;
- a revisão só existia por CLI (`documents-review`, `documents-select`), uma proposta por vez,
  sem fila, sem prioridade, sem comparação de evidências e sem lote;
- **10 associações pendentes** (documentos do DOU sem certame) sem nenhuma experiência de revisão:
  a rota existia, a tela não;
- **48 anexos do IBFC** registrados sem byte (CDN com `Disallow: /`), sem estado explícito por
  documento e sem caminho legítimo de obtenção;
- nenhuma forma de exportar um lote de revisão nem de importar decisões com validação de versão.

O gargalo deixou de ser coleta/extração: é **decisão humana rastreável**.

## Decisões

### 1. Uma única semântica de decisão (sem mecanismo concorrente)

`revisoes_campo` já era append-only. A fase **estende** a tabela em vez de criar outra:

- `previous_decision`, `origin` (`interface`/`cli`/`importacao`), `value_json` (correção),
  `evidence_sha256` (impressão da evidência revisada);
- o `CHECK` original só aceitava `validado`/`rejeitado`; SQLite não altera `CHECK`, então a
  tabela é **reconstruída preservando todas as linhas** dentro da transação;
- `document_review.review_proposal`/`select_current_value` passam a **delegar** à central de
  revisão — o CLI antigo continua funcionando, mas não há dois caminhos de decisão.

Alternativas rejeitadas: tabela nova de decisões (duas verdades); reescrever a decisão anterior
(perde histórico); guardar o estado só na proposta (quebra a auditoria).

### 2. Fila como consulta, prioridade declarada

`radar/review.py` deriva a fila do estado real das propostas (última revisão + valor vigente),
com paginação e filtros. A prioridade é determinística e **cada ponto tem motivo na resposta**:

| Fator | Pontos | Quando |
|---|---|---|
| `edital_oficial` | +2 | concurso tem edital de abertura/retificado registrado |
| `prazo_proximo` | +3 | prazo documentado nos próximos 30 dias |
| `campo_decisivo` | +3 | campo muda a decisão do candidato |
| `conflito` | +2 | há valores divergentes para o mesmo campo |
| `evidencia_curta` | +1 | trecho ≤ 240 caracteres (revisão rápida) |
| `documento_mais_recente` | +1 | é o documento mais novo do conflito |
| `trecho_fraco` | −2 | trecho < 20 caracteres |
| `sem_pagina` | −1 | evidência sem página |

Desempate: `(−pontuação, campo, proposal_id)`. Conflito **eleva** a prioridade, mas não torna a
proposta mais recente automaticamente correta.

Rejeitado: pontuação opaca, ML sem dados de treino, aprovação em massa (proibida nesta fase).

### 3. Lote é navegação, não autorização

`lotes_revisao` + `lote_revisao_itens` guardam um recorte com cursor. Permite abrir o próximo,
voltar, pausar e retomar **sem perder progresso** (as decisões já gravadas são o progresso).
Não existe endpoint de aprovação em massa; cada item continua exigindo decisão própria.

### 4. Corrigir mantém a evidência original

Correção cria uma **proposta derivada** (`extraction_method='correcao_humana'`) que aponta para a
**mesma evidência** da proposta original, já marcada como `validado` (a correção é a decisão).
A original permanece com estado `corrigido` e valor intacto. Assim o valor vigente tem uma
proposta rastreável e a evidência não é reescrita nem duplicada.

### 5. Idempotência de decisão e de seleção

Repetir a mesma decisão (mesmo estado, motivo, origem e valor) devolve `duplicada: true` sem
inserir. `select_current_value` devolve a seleção existente quando o valor vigente já é aquela
proposta — antes, reenviar criava outra linha em `valores_atuais`.

### 6. Associação: confirmar não valida campos

A tela de associações usa a fila existente. Confirmar exige evidência visível e justificativa, e
**não** toca propostas: `revisoes_campo`/`valores_atuais` continuam intactos (teste dedicado).
Não há candidato automático por título/órgão/data — só igualdade exata; quando não há candidato,
a tela diz isso e exige o id do certame com evidência.

### 7. Documento bloqueado tem estado, não silêncio

Cada bloqueio vira evento `download_bloqueado` (idempotente por documento+motivo+host) com
evidência do `robots.txt`. O relatório classifica: `obtido`, `importado_manualmente`,
`bloqueado`, `indisponivel`, `pendente_download`. Alternativas só por **igualdade exata de
caminho** em host autorizado, página de origem acessível e pesquisa humana (portal do órgão/DOU).

### 8. Ingestão manual com procedência, nunca “oficial por declaração”

`ingestoes_documentais` guarda origem declarada, URL original, canal, responsável, data, SHA-256
local, tipo detectado por assinatura, validação e estado de revisão. O arquivo é validado
(PDF/ZIP/HTML por magic bytes, limite de 20 MiB) antes de virar versão; nada é executado; a
proposta continua pendente e a confirmação oficial segue as regras documentais.

### 9. Exportar/importar com impressão de evidência

A exportação leva `proposal_id` estável + `evidence_sha256` (valor + citação + versão + offsets).
A importação rejeita item cuja evidência mudou (`evidência desatualizada`) ou que já foi decidido.
Nada é aprovado por estar no arquivo.

## Contratos (aditivos)

| Método | Rota | Efeito |
|---|---|---|
| GET | `/api/revisao/fila` | fila priorizada e paginada (filtros e `state`) |
| GET | `/api/revisao/proposta/<id>` | comparação completa de evidências e histórico |
| POST | `/api/revisao/proposta/<id>` | decisão append-only (idempotente) |
| POST | `/api/revisao/selecionar` | valor vigente (idempotente) |
| POST | `/api/revisao/lotes` | abre lote persistido |
| GET | `/api/revisao/lotes/<id>` | estado/cursor do lote |
| POST | `/api/revisao/lotes/<id>` | próximo/anterior/pausar/retomar/concluir |
| GET | `/api/revisao/lotes/<id>/exportar` | lote com impressão de evidência |
| POST | `/api/revisao/importar` | importa decisões com validação (`dry_run` padrão) |
| GET | `/api/documentos/bloqueados` | estado de aquisição e alternativas |
| POST | `/api/documentos/importar` | ingestão manual com procedência (`dry_run` padrão) |

CLI: `revisao-fila`, `revisao-decidir`, `revisao-selecionar`, `revisao-lote`,
`revisao-exportar`, `revisao-importar`, `documentos-bloqueados`, `documentos-importar`.

`GET /api/concursos` permanece com os 18 campos e a mesma semântica.

## Critérios de aceite

- Fila funcional com filtros, paginação e prioridade explicada.
- Aprovar/rejeitar/adiar/corrigir/reabrir auditáveis, com estado anterior, origem e justificativa.
- Confirmar associação **não** confirma campos.
- Lote pausa e retoma sem perder progresso; sem aprovação em massa.
- Decisão repetida não duplica; seleção repetida não duplica.
- Importação rejeita evidência desatualizada.
- Bloqueio registrado e alternativas legítimas; nenhum contorno de `robots.txt`.
- Ingestão manual com hash/procedência e sem confirmação automática.
- Base íntegra, contrato v1 intacto, testes e revisão independente aprovados.
