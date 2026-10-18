# Prova real — Fase 35: identidades, conflitos, prazos e destino nominal

Data: 2026-10-18. Python: `C:\Users\anton\Documents\OpenCode-PC\runtime\venv\Scripts\python.exe`.
Banco: `data/radar.sqlite3` — **v19 → v20**, sem perda. Backup de início:
`data/radar.sqlite3.bak-20261018-084417` (55.936 KB, `integrity ok`, FK vazia, v19).

## Suíte de testes

- Baseline: **1.531 testes, OK** (skipped=1).
- Final: **1.587 testes, OK** (+56; 1 pulado quando há motor de OCR).
- Contrato `GET /api/concursos` v1 (18 campos): inalterado (testes de contrato verdes).

## Estado da base ao final

| Métrica | Base real | Backup v19 |
|---|---|---|
| Schema | **v20** | v19 |
| Documentos / com versão | 950 / 911 | 950 / 911 |
| Blocos | 14.823 | 14.823 |
| Propostas | 6.199 | 6.199 |
| Revisões de campo | **0** | 0 |
| Valores vigentes | **0** | 0 |
| Lotes de revisão | 0 | 0 |
| Reconciliações de cargo | **0** | 0 |
| Identidades / cargos | 635 / 125 | 635 / 125 |
| `integrity_check` | ok | ok |

A migração v20 preservou todas as contagens. Nenhuma decisão humana foi fabricada na base
real: todas as decisões de teste foram gravadas em cópias isoladas.

## Diagnóstico (base real, referência 2026-10-18)

| Relatório | Total | Distribuição |
|---|---|---|
| Rótulos de cargo | **246** em 28 concursos | natureza: `cargo_com_codigo` 89 · `nao_e_cargo` 85 · `cargo_literal` 34 · `codigo_sem_nome` 18 · `abreviacao` 12 · `especialidade` 8 |
| Estados de correspondência | 246 | `exata` 89 · `nao_e_cargo` 85 · `duplicata_de_identidade` 36 · `evidencia_insuficiente` 36 |
| Conflitos reais | **53** | `documentos_diferentes_sem_ordem` 17 · `mesmo_documento_valores_distintos` 13 · `escopo_diferente` 8 · `retificacao_posterior` 6 · `cargos_diferentes_sem_identificacao` 5 · `documentos_com_data_distinta` 4 |
| Prazos candidatos | **104** | `expirado` 74 · `futuro` 16 · `sem_data` 14 |
| Destino nominal | **191** | `retirar_da_fila_operacional` 156 · `manter_metadados_na_fila` 35 |

Ações propostas nos rótulos: `confirmar_correspondencia` 89 ·
`nao_reconciliar_como_cargo` 85 · `consolidar_identidade_duplicada` 36 ·
`criar_identidade_a_partir_do_rotulo` 18 · `revisar_documento` 18.

Prioridade dos conflitos: P2 15 · P3 24 · P4 14.

## Tempos medidos (base real)

| Operação | Tempo |
|---|---|
| Inventário de rótulos (246) | 120 ms |
| Fila de reconciliação (paginada) | 116 ms |
| Grupos de conflito (53) | 115 ms |
| Relatório de prazos (104) | 120 ms |
| Destino nominal (191) | 29 ms |

## Verificação de ponta a ponta na UI

Servidor local sobre **cópia isolada** (`f35-ui2.sqlite3`, porta 8769), Chromium via
Playwright:

- fila de identidades: **25 linhas** na página 1 de **246**;
- conflitos: **50 linhas** de **53** grupos;
- prazos: **100 linhas** de **104**;
- destino nominal: **191 linhas** com destino, motivo e "documento continua visível na
  triagem, sem download novo";
- detalhe de identidade `PROFESSOR PII – EDUCAÇÃO FÍSICA`: natureza "Abreviação de cargo",
  candidato com pontuação 40 (`nome_identico`), botões confirmar/rejeitar/ambíguo/reabrir;
- decisão "Usar esta identidade" com responsável e justificativa: **200**, histórico passa a
  mostrar `confirmada · Anton (teste UI) · <timestamp> · justificativa`;
- detalhe de conflito: valores rivais com documento, tipo, data, página e "Ver evidência";
- detalhe de prazo: grupo, estado temporal, trecho/página e próxima ação.

Após a correção, nenhuma requisição das quatro rotas respondeu 400 (antes: `GET
/api/reconciliacao` 400 imediatamente após a primeira decisão).

## Defeitos encontrados e corrigidos nesta fase

1. **Filtro por concurso anulado** — `deadline_report` reutilizava `contest_id` no laço de
   documentos; o relatório devolvia 0 itens na base real. Correção: variável `doc_contest_id`.
   Regressão: `test_filtro_por_concurso_nao_e_sobrescrito`.
2. **`confirmada` ausente do vocabulário** — `label_inventory` levantava `KeyError` e a API
   devolvia 400 após a primeira decisão; a UI não atualizava o histórico. Correção: estado e
   rótulo em `MATCH_STATES`/`MATCH_LABELS`; a fila já aceitava o estado. Regressões:
   `test_fila_reconhece_estado_confirmada`, `test_fila_reflete_decisao_confirmada`.
3. **Histórico não atualizava na tela** — após decidir, o detalhe continuava "Nenhuma decisão
   registrada". Correção em `web/app.js`: reabrir o detalhe do rótulo após a atualização.
   Verificado na UI (histórico visível após a decisão).

## Correções da revisão independente (verificadas)

A revisão independente encontrou quatro violações de invariante e cinco riscos importantes.
Todas foram corrigidas e cobertas por teste:

| Correção | Teste |
|---|---|
| Guarda de concorrência lê o histórico **dentro** da transação de escrita | `test_decisao_avalia_historico_dentro_da_transacao` |
| Dossiê não vincula cargo rejeitado/ambíguo/reaberto | `test_rejeicao_nao_vincula_no_dossie` |
| Seleção de valor vigente não usa cargo rejeitado | `test_selecao_de_valor_nao_usa_cargo_rejeitado` |
| `reconcile_role_label` legado respeita estado e só confirma `confirmada` | `test_reconcile_role_label_respeita_estado`, `test_reconcile_role_label_idempotente_apenas_confirmada` |
| v19 deixa de ser legível (leitura exige v20) | `test_v19_nao_e_legivel` |
| Prazo separado por cargo | `test_prazo_por_cargo_nao_mistura_identidades` |
| Proposta rejeitada não sustenta prazo | `test_prazo_ignora_proposta_rejeitada` |
| Retificação atribuída ao documento que alterou | `test_retificacao_atribuida_ao_documento_que_alterou` |
| Retificação que repete valor não é causa de conflito | `test_retificacao_que_repete_valor_nao_e_causa` |
| Código não supera nome compatível na sugestão | `test_codigo_nao_supera_nome_compativel` |
| Criar identidade exige rótulo evidenciado e respeita especialidade | `test_criar_cargo_exige_evidencia`, `test_criar_cargo_respeita_especialidade` |
| `dry_run` só aplica com `false` explícito | `test_post_dry_run_null_nao_grava` |

Efeito nos números reais: a classificação de conflitos ficou mais honesta —
`retificacao_posterior` caiu de 13 para 6 e `documentos_diferentes_sem_ordem` subiu de 10 para
17, porque retificações que repetem o valor do edital de abertura deixaram de ser tratadas
como causa de divergência. Prazos e rótulos não mudaram de total.

## Decisões exercitadas (somente em cópia)

- confirmar correspondência com `role_id` do mesmo concurso → grava `state='confirmada'`,
  `nature`, `evidence_json`, `reviewer`, `reason`, `previous_id`;
- rejeitar/reabrir preservam histórico e só `confirmada` conta como vínculo;
- decisão concorrente com `expected_previous_id` divergente é recusada;
- `dry_run` (padrão) não grava;
- destino nominal permanece `modo: simulacao` — nada arquivado, apagado ou movido.

## Limites verificados

- 36 rótulos seguem `evidencia_insuficiente` (sem identidade candidata ou concurso sem
  cargos) — não foram inventados cargos.
- 36 duplicatas de identidade seguem sinalizadas, não fundidas.
- 74 prazos expirados continuam no relatório como histórico, não como vigência.
- 14 prazos `sem_data` aparecem com próxima ação, não omitidos.
- 35 documentos nominais permanecem na fila apenas como metadados; 156 marcados para retirada
  operacional, sem exclusão.
