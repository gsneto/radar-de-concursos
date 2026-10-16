# Prova real — Fase 18: operação autônoma, agendamento e alertas

Data: 2026-10-16. Base **habitual**: `data/radar.sqlite3` (criada pelo próprio ciclo).
Python validado: `C:\Users\anton\Documents\OpenCode-PC\runtime\venv\Scripts\python.exe`.
Conta: `gsn\anton`.

## Ciclos reais executados (`python -m radar ops-ciclo`)

| Ciclo | Estado | Fontes (resultado) |
|---|---|---|
| 1 | parcial | Quadrix 40 novos; PCI 477 novos; Guajará `nao_verificada` (base nova) |
| 2 | parcial | DOU 10, FGV 6, Quadrix 70 novos; **PCI 0 (idempotente)**; Guajará `nao_verificada` |

- `run_cycle` validou config, adquiriu instância única, executou as 5 fontes, reconciliou,
  enfileirou (477) e processou lote de 5, gerou alertas e terminou `parcial` (Guajará não
  tem observação v1 na base nova — limitação registrada, não falha inventada).
- Alerts do ciclo 2: `novo_candidato` 50, `documento_recuperado` 50, `retificacao` 4,
  `prazo_isencao` 3 (prazos reais de isenção detectados).

## Agendamento (Windows Task Scheduler)

Tarefa **"Radar de Concursos - Ciclo"** registrada por `scripts/install_tasks.ps1`:

- Ação: `C:\Users\anton\Documents\OpenCode-PC\runtime\venv\Scripts\python.exe -m radar ops-ciclo --config "...\radar_ops.json"`.
- Disparador: a cada 6 h, com `StartWhenAvailable` (recupera após reinício).
- Instância: `IgnoreNew` (não sobrepõe). Conta: usuário, **sem senha armazenada**.

`scripts/verify_tasks.ps1` (após instalar): `Estado=Ready`, `Próxima exec.=2026-10-16 17:17`.

**Execução controlada** (`Start-ScheduledTask`): a tarefa rodou e terminou com
**`LastTaskResult=0`** (sucesso). O log confirma um ciclo real iniciado e concluído
(`run=fbdcb664…` 17:19:11 → 17:21:15, estado `parcial`, 5 fontes).

## Base de dados

- Caminho efetivo: `C:\Users\anton\OneDrive\Desktop\radar-de-concursos\data\radar.sqlite3`
  (o mesmo configurado para coleta, tarefa e interface). Esquema **v8**.
- A tarefa agendada, o CLI e o servidor apontam para **esta** base (não há cópia
  temporária). Nenhum banco de prova foi copiado para a base habitual.

## Saúde (`ops-saude` / `GET /api/saude`)

```
status=funcionando_com_limitacoes ready=True last_cycle=parcial
alerts={total:283, unseen:283} queue={pending:457}
sources: fgv=concluido, guajara=nao_verificada, pci=concluido, in.gov.br=concluido, quadrix=concluido
```

## Interface

Servidor local (`python -m radar serve --host 127.0.0.1 --port 8766`) respondeu:
`/api/saude` 200, `/api/alertas` 200 (total 283), `/api/concursos` 200 (v1 intacta).
No navegador, a seção **Alertas** exibiu "283 não visto(s) de 283 alerta(s)" com as linhas
renderizadas. A atualização periódica (60 s, configurável) foi validada no harness Node.

## Resiliência

- Ciclo concorrente → `ignorado` (lock) — testado.
- Falha de fonte isolada → `parcial`, demais seguem — testado e observado (Guajará).
- Alertas deduplicados por chave; marcação visto/descartado preserva histórico.

## Limitações

- Guajará-Mirim não tem observação v1 na base nova → `nao_verificada` (não é falha de
  fonte; é ausência de dado v1, registrada).
- `generate_alerts` limita 50 alertas por tipo por ciclo (evita spam); os demais novos
  documentos ficam sem alerta individual naquele ciclo.
- A operação depende de o Windows estar ligado e com rede; a tarefa retoma no próximo
  disparador, sem rodar ciclos atrasados em cascata.
- Notificação local no Windows não foi habilitada (opcional; alertas ficam na interface).
