# Plano — Fase 18: operação autônoma e alertas programados

TDD; ciclo com fontes injetáveis (sem rede nos testes). Prova real separada.

## Task 1 — Configuração central
- [x] `radar/ops_config.py` (defaults → arquivo → env; python/db/logs resolvidos;
      `validate_config`; `save_default_config`). `radar_ops.json.example` versionado;
      `radar_ops.json` e `logs/` no `.gitignore`.

## Task 2 — Ciclo operacional e instância única
- [x] `radar/ops.py`: `run_cycle` (valida → lock → fontes → reconcilia → fila em lote →
      alertas → estado); `InstanceLock` (msvcrt, validade de processo, recuperação).

## Task 3 — Alertas persistentes (schema v8)
- [x] Tabela `alertas` aditiva; `generate_alerts` (dedup por chave), `list_alerts`,
      `alert_counts`, `mark_alert`.

## Task 4 — Saúde e logs
- [x] `ops.health` + `GET /api/saude`; `setup_logging` com rotação.

## Task 5 — CLI e API
- [x] `ops-ciclo`, `ops-saude`, `ops-alertas`, `ops-alerta-marcar`, `ops-config`;
      `GET /api/alertas`; v1 intacta.

## Task 6 — Interface
- [x] Seção Alertas + `renderAlerts` + atualização periódica (`startAutoRefresh`).

## Task 7 — Scripts de agendamento
- [x] `scripts/install_tasks.ps1`, `uninstall_tasks.ps1`, `verify_tasks.ps1`,
      `run_cycle.ps1`, `serve.ps1`.

## Task 8 — Testes
- [x] `tests/test_ops.py` (29) + `tests/test_ops_api.py` (6) + ampliações em `test_ui.py`.
      Suíte: **560 testes, OK**.

## Task 9 — Prova real (execução, agendamento, saúde, interface)
- [x] `docs/superpowers/plans/2026-10-16-autonomous-operation-prova-real.md`.

## Task 10 — Documentação, revisão independente, commit e push.
- [x] README + log; revisão independente (code-reviewer) e correções; commit/push.

## Revisão independente — achados e correções

| # | Severidade | Achado | Correção |
|---|---|---|---|
| 1 | importante | fallback POSIX do `InstanceLock` pré-criava o arquivo e nunca adquiria (recursão/erro) | não pré-cria no fallback; `O_EXCL` só no caminho sem `msvcrt`; recuperação de marcador abandonado (regressão `test_exclusive_fallback...`) |
| 2 | importante | alerta de isenção não escalava de `atencao` para `critico` (chave de dedup sem estado) | chave inclui o estado (`…:{state}`); regressão `test_deadline_escalates...` |
| 3 | menor | `_pid_alive` usava `os.kill(pid,0)` — no Windows **encerra** o processo | `OpenProcess`/`GetExitCodeProcess` via ctypes no Windows; `os.kill` só em POSIX |
| 4 | menor | `health()` não fechava a conexão no caminho de erro | `try/finally` |
| 5 | menor | `generate_alerts` podia abortar com `value_json` não-string | guarda `isinstance(raw, str)` antes da data |
| 6 | menor | `run_cycle` chamava `lock.acquire()` fora do `try` | `try/except OSError` → estado `falhou` |
| 7 | menor | `validate_config` aceitava `project_root` vazio e `batch_limit` booleano | checagens explícitas |

Sem achados críticos. Suíte após correções: **563 testes, OK**. Prova real reexecutada:
`generate_alerts` na base real sem crash (7 alertas de isenção escalados); saúde `ready=True`,
esquema 8.
