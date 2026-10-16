# Prova real - Fase 19: notificações nativas e central de triagem

Data: 2026-10-16. Base **habitual**: `data/radar.sqlite3`
(`C:\Users\anton\OneDrive\Desktop\radar-de-concursos\data\radar.sqlite3`), agora **v9**.
Python validado: `C:\Users\anton\Documents\OpenCode-PC\runtime\venv\Scripts\python.exe`.
Máquina: Windows 11 Pro (build 26200). Conta: `gsn\anton`.

## Suíte de testes

`605 testes, OK` (baseline da Fase 18: 563). Novos: `tests/test_notifications.py` (18),
`tests/test_triage.py` (18) e ampliações em `test_ops.py`, `test_ops_api.py`, `test_ui.py`
(inclui o harness Node do `app.js` cobrindo `renderTriage`).

## Identidade de app e toast entregue (prova forte)

1. `scripts/install_app_identity.ps1` criou/atualizou o atalho no Menu Iniciar com
   `System.AppUserModel.ID = RadarDeConcursos.Radar` (idempotente; `ensure_app_identity()`
   retorna `ok: true` nas duas chamadas).
2. `dispatch` real com `notifications.local = true` (opt-in) e `limit = 1` na base habitual:

   ```json
   {"enabled": true, "sent": 1, "errors": 0, "considered": 23, "suppressed": 266, "backlog": 22,
    "results": [{"id": "c4b92920-...", "kind": "prazo_isencao", "state": "enviada", "error": null}]}
   ```

3. **Leitura pelo `UserNotificationListener`** (fonte independente do emissor),
   `ACCESS=Allowed`, confirmando o toast real na central de notificações do Windows:

   ```
   APP=RadarDeConcursos.Radar | Prazo de isenção da taxa
       Isenção da taxa expirado - Fim da solicitação: 2026-10-06
   ```

   > `Show()` aceitar (`accepted:true`) **não** é prova: um AUMID inválido também é aceito.
   > A prova é a leitura de volta pelo listener, com o AUMID e o texto corretos.

## Central de triagem (base real)

`python -m radar ops-triagem --limit 5` sobre a base habitual: 290 alertas, 290 não vistos,
agrupados **por `contest_id`**, com `urgency` a partir das datas documentais. Exemplo real
(recorte):

```
contest=6ae3cd17-... urgency=hoje exemption_end=2026-08-18 kind=prazo_isencao severity=critico
contest=c76d40be-... urgency=hoje exemption_end=2026-09-02 kind=prazo_isencao severity=critico
```

`GET /api/triagem?limit=3` via servidor loopback real
(`python -m radar serve --db .../radar.sqlite3 --port 8123`):

```
STATUS=200 groups=3 counts_total=290 unseen=290 first_group urgency=hoje
```

`ops-saude` real: `status=funcionando_com_limitacoes`, `schema_version=9`,
`contests=593`, `queue.pending=457`, `alerts={total:290, unseen:290}`,
`notifications={pending:288, enviada:2}` (as 2 `enviada` são os toasts reais acima).

## Backlog incremental (execução real do código, DB real)

Base nova com 120 documentos reais registrados; `generate_alerts(max_new_alerts=50)`:

```
ciclo 1: novos=50 backlog=70 acumulado=50
ciclo 2: novos=50 backlog=20 acumulado=100
ciclo 3: novos=20 backlog=0  acumulado=120
ciclo 4: novos=0  backlog=0  acumulado=120
distintos: 120
```

Drenagem incremental sem duplicar (120 chaves distintas) e sem descartar o excedente.

## Migração da base habitual

A base estava em v8 (criada na F18); `python -m radar documents-migrate --db data/radar.sqlite3`
aplicou a v9 (`user_version=9`, colunas `notified_at/notify_state/notify_attempts/notify_error/
snoozed_until` e tabela `ops_state` presentes). O `run_cycle` também migra no início, então o
ciclo agendado a manteria atualizada.

**Regressão crítica corrigida (revisão independente).** A migração passou a **semear** os
*watermarks* de alertas com o cursor atual quando ausentes: sem isso, o primeiro ciclo
pós-migração reprocessaria todo o histórico e, como a chave de dedup de
`documento_recuperado` mudou (de `fetched_at` para `version_id`), criaria alertas
duplicados. Verificação real na base habitual: antes `290` alertas, migração semeia os
watermarks, `generate_alerts` real cria `0` e o total **permanece 290** (kinds inalterados:
`documento_recuperado` 133, `novo_candidato` 133, `prazo_isencao` 14, `retificacao` 10).

## Revisão independente (delegação via `task`/code-reviewer)

**Achado crítico corrigido:** C1 (duplicação de alertas na migração) — resolvido pelo
semeadura de watermarks acima, com regressões dedicadas (`test_triage.MigrationSeedingTest`).

**Importantes corrigidos:** (I1) intervalo mínimo entre notificações (`min_interval_seconds`,
persistido em `ops_state`); (I2) chaves de configuração antes mortas agora aplicadas
(`max_new_alerts_per_cycle` no ciclo; `triage_horizon_days` na API/CLI); (I3) `snooze`
normalizado para UTC (a comparação em SQL é lexicográfica); (I4) UI ganhou **Reabrir**,
"Abrir concurso" navega por `#concurso=<id>` e "Ver fonte" quando HTTPS; (I5) teste de
identidade isolado em diretório temporário e canal nativo com *skip* fora do Windows.

**Menores corrigidos:** (M1) varredura por watermark no SQL + índices por
`discovered_at`/`fetched_at`; (M2) semeadura evita reprocessar o histórico; (M3) prazo de
isenção usa o valor vigente/proposta mais recente (nunca a mais antiga); (M4) `limit`
negativo não descarta o último elegível; (M5) `base_url` restrito a `http(s)`. NITs: imports
e variáveis mortos removidos, comentário duplicado, caracteres de controle filtrados antes do
XML do toast.

Suíte após as correções: **605 testes, OK**. Contrato v1 de 18 campos confirmado inalterado
(bytes de `/api/concursos` iguais antes/depois; `tests/test_contract.py` intacto).

## Auditoria de segurança (registro)

- **OneDrive**: base em pasta sincronizada. Recomendação documentada (não destrutiva):
  manter a base fora de sincronização em tempo real; backup + verificação + rollback; **não**
  excluir a cópia antiga. Sem alteração de comportamento nesta fase.
- **Prioridade geográfica** (Bahia/Pernambuco, prova vs lotação, Paulo Afonso) e
  **inteligência de conteúdo** (perfil pessoal × conteúdo programático): **lacunas
  identificadas**, não implementadas nesta fase.

## Limitações honestas

- A exibição visual do toast depende das configurações de foco/notificação do Windows; o
  `Show()` sozinho não garante nem prova exibição (por isso a leitura pelo listener).
- Guajará segue `nao_verificada` (`sem_observacao_v1`) na base nova — limitação registrada,
  não falha inventada.
- Operação depende de Windows ligado e rede para a coleta.
