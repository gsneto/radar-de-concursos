# Design — Fase 34: mesa de revisão, dossiês de oportunidades e decisões auditáveis

Data: 2026-10-17. Base: Fase 33 (`1679159`), schema v18 → **v19**. 1.481 testes.

## Problema

A base tem 6.199 propostas candidatas em 273 escopos (concurso × cargo), **0 revisões** e
**0 valores vigentes**. A fila existente (`/api/revisao/fila`) lista propostas soltas: o
operador vê `education = "Diploma..."` sem saber de que cargo, em que documento, com que
outras propostas conflitantes. Não havia dossiê, comparação de evidências, sessão retomável
com detecção de mudança, triagem dos documentos nominais nem visão temporal do ciclo.

## Decisões

### 1. Agrupar por oportunidade, não por proposta

`radar/opportunities.py` agrupa as propostas por **(concurso, cargo)**. Quando não há cargo
reconciliado, usa o **rótulo do próprio documento** (`cargo do documento não reconciliado: X`),
exibido como **não reconciliado**. Sem isso, todos os cargos de um edital viriam juntos e a
mesa seria inútil; com isso, 28 concursos viram **273 grupos acionáveis**.

Cada grupo traz: estado documental (reutiliza `coverage_states`), estado de cada campo
decisivo, pendentes, conflitos, presença de página, última atualização, prioridade com
motivos e próxima ação.

### 2. Estado de campo honesto

Estados derivados do modelo existente (não um enum paralelo):

`confirmado` (decisão validado) · `corrigido` · `em_conflito` · `ambiguo` · `candidato` ·
`multiplo_por_cargo` · `rejeitado` (só se **todas** rejeitadas) · `nao_extraido`.

`multiplo_por_cargo` existe porque, sem cargo reconciliado, valores distintos podem ser
**cargos diferentes** — chamar de conflito inventaria divergência. Local com `a_divulgar` +
local concreto é `ambiguo` (escopos diferentes), mesma regra da Fase 33.

### 3. Dossiê

`opportunity_dossier` reúne identidade, documentos (edital/retificação/resultado com versões e
páginas), campos com **todas** as evidências (documento, versão, página, trecho, hash), campos
ausentes (declarados como ausentes, nunca zero), conflitos entre versões e os quatro grupos
prioritários (reutiliza `decisive_fields`).

### 4. Comparação de evidências

`proposal_evidence` amplia `review.proposal_detail` com:

- **contexto anterior/posterior** extraído do texto real do bloco (ou limitação declarada);
- **origem** do conteúdo (regex, tabela, reconstrução regional, requisitos, cronograma, OCR);
- **confiança estrutural** quando a evidência vem de quadro multipágina (Fase 32), com página
  de cabeçalho/linhas/total — e `aplicavel: false` com motivo quando não vem;
- outras propostas do mesmo campo e histórico de decisões (já existiam).

### 5. Sessão retomável com detecção de mudança

Migração **v19** adiciona a `lote_revisao_itens`:

- `snapshot_sha256`: impressão da evidência no momento da abertura;
- `scope_snapshot`: conjunto de valores do escopo (concurso, cargo, campo) na abertura.

Na leitura da sessão, cada item recebe `alterado` + `motivo_alteracao`
(`evidencia` ou `nova_proposta`). A comparação de escopo é por **conjunto de valores**, não
por relógio: imune a timestamps iguais ou fora de ordem.

Na decisão com `lote_id`, o núcleo recusa quando:
1. o hash da evidência difere do snapshot;
2. o conjunto de valores do escopo mudou (surgiu proposta nova com outro valor);
3. a proposta não pertence ao lote.

O frontend **bloqueia** as ações e mostra o aviso quando `alterado` — decisão sobre o que o
operador não viu é o erro que a fase proíbe.

### 6. Prioridade reutilizada, não reescrita

A mesa usa `review._priority` (fatores e pesos já documentados na Fase 28–31). Não há segunda
política: a ordem é reproduzível para a mesma base, filtros e versão do código. A prioridade
do grupo é a do item mais prioritário, e os motivos são exibidos.

### 7. Triagem de documentos nominais

`radar/nominal_triage.py` mostra os 191 documentos nominais com: título, concurso, tipo,
fonte, **política** (permite persistir documento?), estado e próxima ação. Separa:

- identificação (o documento é deste certame?);
- natureza (lista nominal × ato de regra);
- acesso (fonte permite obter?);
- armazenamento (política permite persistir?).

Nada é baixado para exibir a fila e **nenhum trecho de lista de pessoas é copiado**.

### 8. Linha do tempo sem contabilidade paralela

`radar/timeline.py` usa `ciclos_monitoramento`, `ciclos_fontes` e `eventos_documentais`.
Mostra snapshot anterior (por timestamp real), novos, ciclos, documentos descobertos e falhas.
Atribuição de documento a ciclo é **por janela de tempo**, declarada como tal; fora de janela
é "execução manual".

## Contratos

- `opportunities.opportunity_list(db, field, conflict, document_state, has_page, search, min_priority, contest_id, limit, offset)`
- `opportunities.opportunity_dossier(db, contest_id, role_id=None)`
- `opportunities.proposal_evidence(db, proposal_id)`
- `nominal_triage.nominal_triage(db, limit, offset)` / `nominal_summary(db)`
- `timeline.timeline(db, since=None, limit=200)`
- `review.open_batch` agora grava snapshot e escopo; `review.batch_status` devolve
  `alterado`/`motivo_alteracao`/`progresso.alterados`.

API aditiva: `/api/oportunidades`, `/api/oportunidades/<id>`, `/api/revisao/evidencia/<id>`,
`/api/documentos/nominais`, `/api/linha-do-tempo`.

## Não objetivos

- Nenhum endpoint de edição/exclusão de decisão (append-only).
- Nenhuma aprovação em massa.
- Nenhuma decisão automática ou "marcar como revisado por abrir".
- Não trocar a stack de frontend.
- Não apagar documentos, propostas, evidências ou decisões.
- Não alterar o contrato de `GET /api/concursos` (18 campos).
