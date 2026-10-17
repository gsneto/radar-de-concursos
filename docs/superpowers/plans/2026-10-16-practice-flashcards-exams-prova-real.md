# Prova real - Fase 23: flashcards, questões e simulados

Data: 2026-10-17. Python validado: `C:\Users\anton\Documents\OpenCode-PC\runtime\venv\Scripts\python.exe`.

## Suíte de testes

- Baseline observada (antes de implementar): **829 testes, OK**.
- Final: **912 testes, OK** (83 novos). Novos: `test_flashcards.py` (16), `test_questions.py` (16),
  `test_exams.py` (14), `test_practice.py` (30), ampliação de `test_study_backup.py` (21) e de
  `test_ui.py`. Ajuste: 5 asserções de versão de esquema (11 → 13).

## Migração da base habitual (v12 → v13)

Backups consistentes via API do SQLite (integridade `ok`):
`data/radar.sqlite3.bak-20261016-235632` (pré-v12) e `data/radar.sqlite3.bak-20261017-005453`
(pré-v13).

| Momento | integrity | user_version | concursos | documentos | alertas | propostas |
|---|---|---|---|---|---|---|
| antes (v12) | ok | 12 | 593 | 636 | 290 | 751 |
| depois (v13) | ok | 13 | 593 | 636 | 290 | 751 |

Observação honesta: a base já havia sido migrada para **v12** pelo **ciclo agendado**
(`ops-ciclo` chama `migrate_document_schema`; log `run=f10cf44d...` às 23:19:59). O caminho
**v11 → v12** foi provado separadamente, em cópia da base real: reconstituído v11 (drop das
tabelas `pratica_*` + `user_version=11`) → `migrate` → `user_version=12`, `integrity ok`,
7 tabelas criadas, 593/636/290 preservados.

## Prova funcional (cópia da base real, v13)

```
flashcard: ['algoritmos'] | revisao: 1 dia(s), proxima 2026-10-18
simulado: total 3 acertos 1 brancos 2 pct 33
basis: 33% de acerto sobre 3 questão(ões) aplicada(s); 2 em branco contam no denominador
desempenho: 100% sobre 1 tentativa(s) respondida(s)
fila pendente: 0
```

## HTTP (servidor loopback real, base temporária)

```
GET /api/estudos/flashcards|fila|estatisticas|questoes|tentativas|desempenho|simulados -> 200
GET /api/concursos -> 200   (contrato v1 inalterado)
GET /api/prioridades?limit=2 -> 200
GET /api/estudos/painel -> 200
```

Fluxo de simulado (após as correções da revisão):

```
listagem de questões sem gabarito: True
GET /simulados/<id>/questoes -> 200, sem gabarito, com restante_segundos
GET /simulados/<id>/resultado (em andamento) -> 409
GET /simulados/nao-existe -> 404
POST /simulados/<id>/responder sem `ordem` -> 400
POST /simulados/<id>/finalizar (1ª e 2ª vez) -> 200, 200
tentativas após finalizar duas vezes -> 3 (não duplicou)
```

## Exportação / importação (formato v2)

```
export -> counts {flashcards: 1, flashcard_revisoes: 1, questoes: 4, questao_versoes: 4,
                  tentativas: 4, simulados: 1, simulado_questoes: 3}
import em banco novo -> ok True created 18 conflicts 0
reimport             -> created 0 skipped 18   (idempotente)
arquivo v1           -> validate [] e import ok True  (compatível)
```

## Revisão independente (delegação via `task`/code-reviewer)

**3 críticos + 5 importantes + 11 menores**. Corrigidos:

- **C1** `finish_exam` não era idempotente (prova expirada duplicava tentativas e inflava o
  desempenho). Corrigido com transição condicional atômica (`tentativas_gravadas`, schema v13) e
  releitura dentro da transação. Regressões: `test_finish_idempotente`,
  `test_finish_idempotente_quando_expirado`.
- **C2** importação de `questao_versoes` usava o id da linha em vez de `(questao_id, versao)`,
  corrompendo a cadeia (a questão ficava não editável) ou abortando. Corrigido com checagem por
  `(questao_id, versao)`, conflito em divergência e reconciliação de `pratica_questoes.versao`.
  Regressão: `test_versao_divergente_nao_corrompe_a_cadeia`.
- **C3** `GET /simulados/<id>/resultado` revelava o **gabarito de prova em andamento**. Agora
  responde 409; criado `GET /simulados/<id>/questoes` (sem gabarito) para retomada; a UI só
  oferece "Ver resultado" fora de andamento. Regressões:
  `test_resultado_nao_vaza_gabarito_em_andamento`, `test_resultado_apos_finalizar_tem_gabarito`.
- **Importantes:** I1 snapshot de disciplina/tópico na questão aplicada (schema v13) — editar a
  questão não reatribui o escopo da prova antiga; I2 validação de **domínios** no export/import e
  `IntegrityError` convertido em erro de arquivo (não mais 503); I3 UI de realização do simulado
  (cronômetro do servidor, salvamento progressivo, retomada, finalizar); I4 `ordem` ausente → 400;
  I5 simulado inexistente → 404.
- **Menores:** gabarito fora da listagem de questões; `tipo` persistido; alternativas com texto
  duplicado rejeitadas; limite de 26 alternativas; `tags` string normalizada; `limit: 0` não vira
  10; query em rota dinâmica → 400; limite de corpo maior nas rotas de prática; export tolerante a
  base v11.

Suíte após as correções: **912 testes, OK**; contrato v1 inalterado.

## Limitações honestas

- A UI do simulado cobre responder/retomar/finalizar e o cronômetro; navegação avançada
  (marcar para revisão, pular, mapa de questões) fica para fase futura.
- Sem importação de pacotes de questões de terceiros (licenciamento de conteúdo).
- Percentual de acerto não é probabilidade de aprovação.
