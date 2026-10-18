# Prova real — Fase 34: mesa de revisão, dossiês e decisões auditáveis

Data: 2026-10-17/18. Python: `C:\Users\anton\Documents\OpenCode-PC\runtime\venv\Scripts\python.exe`.
Banco: `data/radar.sqlite3` — **v18 → v19**, sem perda. Backup de início:
`data/radar.sqlite3.bak-20261018-060423` (`integrity ok`, FK vazia, v18).

## Suíte de testes

- Baseline: **1.481 testes, OK** (skipped=1).
- Final: **1.531 testes, OK** (+50; 1 pulado quando há motor de OCR).
- Contrato `GET /api/concursos` v1 (18 campos): inalterado (testes de contrato verdes).

## Snapshot do diagnóstico (10:42Z, base em movimento)

| Métrica | Valor |
|---|---|
| Certames | 634 (+1 container) |
| Documentos | 950 (911 com versão) |
| Blocos | 14.823 |
| Propostas/evidências | 6.199 / 6.199 |
| Revisões humanas | **0** |
| Valores vigentes | **0** |
| Lotes de revisão | **0** |
| Oportunidades (concurso × cargo/rótulo) | **273** |
| Oportunidades com conflito | 31 |
| Oportunidades com evidência por página | 273 (100%) |
| Pendentes | 6.199 |
| Documentos nominais | 191 (35 sem conteúdo, 156 com conteúdo já extraído) |
| Conflitos entre versões | 24 (12 no mesmo documento, 10 de escopo, 2 retificações posteriores) |
| Estados documentais | `campos_candidatos` 27 · `oficial_sem_edital` 16 · `oficial_nao_importado` 86 · `apenas_agregador` 504 · `conflito` 1 |

Tempo: lista completa paginada (273 grupos, 2 páginas) **518 ms**; dossiê ~0,7 s; nominais ~0,02 s;
linha do tempo ~0,02 s.

## O que a mesa entrega

- **273 grupos** em vez de 6.199 propostas soltas. Cada linha mostra concurso, cargo
  (reconciliado ou rótulo do documento), estado documental, até 4 campos com estado, pendentes,
  conflitos, presença de página e próxima ação.
- **Dossiê** com documentos (tipo, data, versões, páginas), todos os campos decisivos com todas as
  evidências (documento, versão, página, trecho, hash), lacunas declaradas e conflitos.
- **Comparação de evidências** com contexto antes/depois do bloco, origem do conteúdo
  (`regex`, `tabela-quadrix-pdf`, `requisito-inline`, `cronograma`, OCR…), outras propostas para o
  mesmo campo e histórico de decisões.
- **Sessão** com progresso, pausa/retomada, restauração após recarregar e detecção de mudança.
- **Triagem de 191 nominais** com quatro eixos separados (identificação, natureza, acesso,
  armazenamento), sem download e sem copiar conteúdo.
- **Linha do tempo** com snapshot anterior, ciclos do agendador e atribuição por janela.

## Fluxo ponta a ponta (em cópia isolada)

Cópia: `radar-mesa-test.sqlite3` (v19). Servidor em porta separada, navegador real.

| Passo | Resultado |
|---|---|
| Abrir sessão (25 itens) | `estado: aberto · 0/25 decidido(s)` |
| Preencher justificativa e Confirmar | `Decisão registrada.` → `1/25 decidido(s)` |
| Pausar / Retomar | `pausado` → `aberto`, progresso preservado |
| Inserir proposta nova no mesmo escopo/cargo | sessão passa a `3 alterado(s)` |
| Abrir item alterado | aviso "Evidência mudou…" e **ações bloqueadas** |
| Base real | **0 revisões, 0 valores, 0 lotes** |

A decisão gravada na cópia: `validado`, revisor `operador local (não autenticado)`,
justificativa `teste automatizado em copia isolada`, origem `interface`, com `evidence_sha256`.
Nenhuma decisão foi criada na base real — o fluxo de decisão existe e funciona, mas a fase não
fabrica decisões humanas.

## Mudanças do ciclo agendado (transparência)

A linha do tempo desde 2026-10-17T12:00Z mostra **+314 documentos, +275 versões, +5.448 propostas**
e **5 ciclos** do agendador no período. A base mudou durante o trabalho: os números acima têm
data/hora de referência (10:42Z) e não devem ser lidos como estáticos.

Atribuição: documento descoberto dentro da janela de um ciclo é `ciclo_agendado`; se o ciclo
começou antes da referência, `ciclo_anterior_a_referencia`; fora de qualquer janela,
`fora_de_ciclo` (execução manual). A comparação de `since` normaliza o fuso para UTC — o mesmo
instante com offset `-03:00` e `UTC` devolve as mesmas contagens (teste dedicado).

## Privacidade e minimização

- Triagem nominal devolve **apenas metadados** (título, URL, tipo, fonte, contagens).
- **38 propostas** vêm de 19 documentos nominais: a mesa, a fila e a comparação de evidências
  **não reproduzem trecho nem contexto** desses documentos (`nominal: true`,
  `limitation: "documento nominal: trecho não reproduzido"`). Teste dedicado.
- Nenhum conteúdo nominal é copiado para logs, painéis ou exportações.

## Correções de honestidade encontradas nesta fase

| Correção | Efeito |
|---|---|
| Conflito entre cargos distintos | Deixou de ser "conflito": `multiplo_por_cargo` (31 grupos com conflito real, não 300) |
| Rótulo reconciliado | Passa a compartilhar o escopo da identidade canônica; conflito real deixa de ficar invisível |
| "Cargo não reconciliado" como ambiguidade | Deixou de marcar todo campo como ambíguo: o valor é candidato; a identidade é que está pendente |
| `a_divulgar` × local concreto | `ambiguo`, não `em_conflito` (escopos diferentes) |
| Snapshot de sessão | Por conjunto de propostas do escopo, não por valor nem por relógio |
| `since` com fuso | Normalizado para UTC |
| Lista nominal | Trecho e contexto redigidos na mesa, na fila e na evidência |

## Banco e contrato

- `PRAGMA integrity_check`: **ok**; `foreign_key_check`: **vazia**; schema **v19**.
- Migração v19 (2 colunas em `lote_revisao_itens`) aplicada na base real: idempotente,
  aditiva, sem perda (950 documentos, 6.199 propostas, 0 revisões antes e depois).
- Contrato v1 preservado.

## Limitações

1. **Identidade de revisor é local** ("operador local (não autenticado)"): não há autenticação.
2. **273 grupos são todos de rótulo não reconciliado**: nenhum cargo foi reconciliado por decisão
   humana ainda; a mesa mostra isso explicitamente.
3. **Sessão não cobre decisão fora de lote**: a revisão direta (painel antigo) continua possível
   sem snapshot; a proteção é do fluxo de sessão.
4. **`historico` continua não atribuído** (sem prova de encerramento).
5. **Base em movimento**: o ciclo de 6 h pode alterar contagens entre leituras.
