"""Operação autônoma do Radar: ciclo, alertas persistentes, saúde e instância única.

Orquestra os componentes já existentes (monitoramento, confirmação documental, alertas)
num fluxo único, recuperável e observável, sem criar um pipeline paralelo:

1. valida a configuração;
2. garante instância única (bloqueio de arquivo com validade de processo);
3. executa as fontes habilitadas (``monitoring.run_cycle``);
4. reconcilia candidatos (``confirmation.reconcile``);
5. enfileira e processa um lote limitado da fila documental;
6. gera alertas persistentes;
7. registra métricas e termina com estado explícito.

Nada é promovido a validado sem revisão humana; falha de uma fonte não impede as outras.
"""

from __future__ import annotations

import json
import logging
import os
import socket
import sys
from contextlib import closing
from datetime import datetime, timedelta, timezone
from logging.handlers import RotatingFileHandler
from pathlib import Path
from uuid import uuid4

from radar.document_store import SCHEMA_VERSION, connect_documents, migrate_document_schema

LOGGER_NAME = "radar.ops"
LOCK_FILENAME = "radar_ops.lock"
LOG_FILENAME = "radar_ops.log"

# Chave de configuração -> `id` do descritor em `monitoring.default_sources()`.
_CONFIG_TO_SOURCE_ID = {
    "guajara": None,               # fonte base (sem id; mapeada pelo source_url)
    "dou": "dou-secao-3",
    "fgv": "fgv-conhecimento",
    "quadrix": "quadrix",
    "pci": "pci",
}

SEVERITY = ("info", "atencao", "critico")


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _schema_version(db_path) -> int:
    with closing(connect_documents(db_path)) as conn:
        return conn.execute("PRAGMA user_version").fetchone()[0]


def _parse(ts):
    if not ts:
        return None
    try:
        return datetime.fromisoformat(ts)
    except (TypeError, ValueError):
        return None


# --- Logs --------------------------------------------------------------------

def setup_logging(logs_dir: str, *, level: int = logging.INFO) -> logging.Logger:
    """Configura logger com rotação (tamanho controlado). Não registra segredos."""
    logger = logging.getLogger(LOGGER_NAME)
    logger.setLevel(level)
    logger.propagate = False
    target = str(Path(logs_dir) / LOG_FILENAME)
    for handler in list(logger.handlers):
        if getattr(handler, "baseFilename", None) == target:
            return logger  # já configurado para este diretório
        logger.removeHandler(handler)
        handler.close()
    Path(logs_dir).mkdir(parents=True, exist_ok=True)
    handler = RotatingFileHandler(target, maxBytes=2 * 1024 * 1024, backupCount=3,
                                  encoding="utf-8")
    handler.setFormatter(logging.Formatter(
        "%(asctime)s %(levelname)s %(message)s", datefmt="%Y-%m-%dT%H:%M:%S%z"))
    logger.addHandler(handler)
    return logger


# --- Instância única ---------------------------------------------------------

class InstanceLock:
    """Bloqueio de instância única compatível com Windows.

    Usa ``msvcrt.locking`` (bloqueio não-bloqueante) sobre um arquivo mantido aberto: o
    sistema operacional **libera o bloqueio quando o processo termina**, o que distingue
    um processo ativo de um marcador abandonado (após uma queda, o próximo ciclo adquire
    o bloqueio). Em plataformas sem ``msvcrt``, cai para criação exclusiva de arquivo com
    verificação de validade do PID.
    """

    def __init__(self, lock_path: str, *, now=None):
        self.path = str(lock_path)
        self._now = now or _now
        self._fd = None

    def _write_meta(self):
        try:
            meta = json.dumps({"pid": os.getpid(), "started_at": self._now()})
            os.write(self._fd, meta.encode("utf-8"))
            os.lseek(self._fd, 0, os.SEEK_SET)
        except OSError:
            pass

    def acquire(self) -> bool:
        Path(self.path).parent.mkdir(parents=True, exist_ok=True)
        try:
            import msvcrt
        except ImportError:
            return self._acquire_exclusive()
        # Windows: cria/abre o arquivo e tenta o bloqueio não-bloqueante do byte 0.
        self._fd = os.open(self.path, os.O_RDWR | os.O_CREAT, 0o600)
        try:
            msvcrt.locking(self._fd, msvcrt.LK_NBLCK, 1)
        except OSError:
            os.close(self._fd)
            self._fd = None
            return False
        self._write_meta()
        return True

    def _acquire_exclusive(self) -> bool:
        # Fallback POSIX: criação exclusiva do arquivo (sem pré-criar) + PID válido.
        try:
            self._fd = os.open(self.path, os.O_RDWR | os.O_CREAT | os.O_EXCL, 0o600)
            self._write_meta()
            return True
        except FileExistsError:
            pid = self._read_pid()
            if pid and _pid_alive(pid):
                return False
            try:
                os.unlink(self.path)
            except OSError:
                return False
            return self._acquire_exclusive()

    def _read_pid(self):
        try:
            data = json.loads(Path(self.path).read_text(encoding="utf-8") or "{}")
            return int(data.get("pid"))
        except (OSError, ValueError, TypeError):
            return None

    def release(self):
        if self._fd is None:
            return
        try:
            import msvcrt
            try:
                os.lseek(self._fd, 0, os.SEEK_SET)
                msvcrt.locking(self._fd, msvcrt.LK_UNLCK, 1)
            except OSError:
                pass
        except ImportError:
            pass
        try:
            os.close(self._fd)
        finally:
            self._fd = None

    def __enter__(self):
        if not self.acquire():
            raise RuntimeError("outra execução já está ativa")
        return self

    def __exit__(self, *exc):
        self.release()
        return False


def _pid_alive(pid: int) -> bool:
    """Verifica se o PID está ativo, sem efeitos colaterais.

    No Windows, `os.kill(pid, 0)` **encerra** o processo (TerminateProcess), por isso
    usamos `OpenProcess` (consulta) via ctypes. Em POSIX, `os.kill(pid, 0)` é seguro.
    """
    if pid <= 0:
        return False
    if os.name == "nt":
        import ctypes
        from ctypes import wintypes
        PROCESS_QUERY_LIMITED_INFORMATION = 0x1000
        kernel32 = ctypes.windll.kernel32
        handle = kernel32.OpenProcess(PROCESS_QUERY_LIMITED_INFORMATION, False, pid)
        if not handle:
            return False
        try:
            exit_code = wintypes.DWORD()
            if kernel32.GetExitCodeProcess(handle, ctypes.byref(exit_code)):
                STILL_ACTIVE = 259
                return exit_code.value == STILL_ACTIVE
            return True
        finally:
            kernel32.CloseHandle(handle)
    try:
        os.kill(pid, 0)
        return True
    except OSError:
        return False


# --- Alertas -----------------------------------------------------------------

def _insert_alert(conn, *, kind, severity, dedup_key, title, detail=None, contest_id=None,
                  observation_id=None, source_id=None, event_at=None, payload=None) -> bool:
    if severity not in SEVERITY:
        severity = "info"
    before = conn.total_changes
    conn.execute(
        """INSERT OR IGNORE INTO alertas
        (id,kind,severity,contest_id,observation_id,source_id,dedup_key,title,detail,
         event_at,created_at,payload_json)
        VALUES (?,?,?,?,?,?,?,?,?,?,?,?)""",
        (str(uuid4()), kind, severity, contest_id, observation_id, source_id, dedup_key,
         title, detail, event_at or _now(), _now(),
         json.dumps(payload, ensure_ascii=False) if payload else None))
    return conn.total_changes > before


def _state_get(conn, key, default=None):
    row = conn.execute("SELECT value FROM ops_state WHERE key=?", (key,)).fetchone()
    return row[0] if row else default


def _state_set(conn, key, value):
    conn.execute(
        """INSERT INTO ops_state (key,value,updated_at) VALUES (?,?,?)
        ON CONFLICT(key) DO UPDATE SET value=excluded.value, updated_at=excluded.updated_at""",
        (key, value, _now()))


def _cursor_key(discovered_at, row_id) -> str:
    return json.dumps([discovered_at, row_id])


def _wm_parts(watermark: str | None):
    """(ts, id) do watermark, ou None se ausente/ilegível (processa tudo)."""
    if not watermark:
        return None
    try:
        last_at, last_id = json.loads(watermark)
    except (ValueError, TypeError):
        return None
    return (last_at, last_id)


def generate_alerts(db_path, *, cycle_id=None, now=None,
                    exemption_horizon_days: int = 7, max_new_alerts: int = 200) -> dict:
    """Gera alertas persistentes a partir do estado atual (deduplicados por chave).

    Streams de documentos usam um **watermark** persistido (`ops_state`) e processam em
    ordem ascendente até `max_new_alerts` por ciclo: o excedente fica como **backlog** e é
    drenado nos ciclos seguintes (nada é descartado em silêncio). Alertas de prazo e de
    falha de fonte são reavaliados a cada ciclo; a dedup evita repetir.
    """
    now = now or _now()
    created = {"novo_candidato": 0, "documento_recuperado": 0, "retificacao": 0,
               "falha_fonte": 0, "prazo_isencao": 0, "lote_confirmacao": 0}
    backlog = {"documentos": 0, "versoes": 0}
    conn = connect_documents(db_path)
    try:
        conn.execute("BEGIN IMMEDIATE")
        budget = max(0, int(max_new_alerts))
        # --- Documentos (novo candidato / retificação) por watermark ascendente ---
        wm_docs = _wm_parts(_state_get(conn, "alerts.watermark.documentos"))
        doc_sql = ("SELECT id,kind,title,discovered_at,observation_id,contest_id FROM documentos")
        if wm_docs:
            rows = conn.execute(
                doc_sql + " WHERE (discovered_at, id) > (?, ?) ORDER BY discovered_at ASC, id ASC",
                wm_docs).fetchall()
        else:
            rows = conn.execute(doc_sql + " ORDER BY discovered_at ASC, id ASC").fetchall()
        last_cursor = None
        for doc_id, kind, title, discovered_at, obs, contest in rows:
            if budget <= 0:
                backlog["documentos"] += 1
                continue
            inserted = 0
            if _insert_alert(conn, kind="novo_candidato", severity="info",
                             dedup_key=f"novo_candidato:{doc_id}", title=f"Novo candidato: {title}",
                             contest_id=contest, observation_id=obs, event_at=discovered_at):
                created["novo_candidato"] += 1
                inserted += 1
            if kind == "retificacao" and _insert_alert(
                    conn, kind="retificacao", severity="atencao",
                    dedup_key=f"retificacao:{doc_id}", title=f"Retificação: {title}",
                    contest_id=contest, observation_id=obs, event_at=discovered_at):
                created["retificacao"] += 1
                inserted += 1
            budget -= inserted
            last_cursor = _cursor_key(discovered_at, doc_id)
        if last_cursor is not None:
            _state_set(conn, "alerts.watermark.documentos", last_cursor)
        # --- Versões recuperadas por watermark ascendente ---
        wm_vers = _wm_parts(_state_get(conn, "alerts.watermark.versoes"))
        vers_sql = ("SELECT v.id,v.document_id,d.contest_id,v.fetched_at,v.byte_size "
                    "FROM versoes_documento v JOIN documentos d ON d.id=v.document_id")
        if wm_vers:
            vrows = conn.execute(
                vers_sql + " WHERE (v.fetched_at, v.id) > (?, ?) ORDER BY v.fetched_at ASC, v.id ASC",
                wm_vers).fetchall()
        else:
            vrows = conn.execute(vers_sql + " ORDER BY v.fetched_at ASC, v.id ASC").fetchall()
        last_vers = None
        for version_id, doc_id, contest, fetched_at, byte_size in vrows:
            if budget <= 0:
                backlog["versoes"] += 1
                continue
            if _insert_alert(conn, kind="documento_recuperado", severity="info",
                             dedup_key=f"documento_recuperado:{doc_id}:{version_id}",
                             title="Documento oficial recuperado", detail=f"{byte_size} bytes",
                             contest_id=contest, event_at=fetched_at):
                created["documento_recuperado"] += 1
                budget -= 1
            last_vers = _cursor_key(fetched_at, version_id)
        if last_vers is not None:
            _state_set(conn, "alerts.watermark.versoes", last_vers)
        # Falha de fonte no ciclo atual.
        if cycle_id:
            for source_url, state, error in conn.execute(
                    "SELECT source_url,state,error_code FROM ciclos_fontes WHERE cycle_id=?",
                    (cycle_id,)):
                if state == "falhou":
                    day = (now or "")[:10]
                    if _insert_alert(conn, kind="falha_fonte", severity="atencao",
                                     dedup_key=f"falha_fonte:{source_url}:{day}",
                                     title="Fonte indisponível", detail=error or state,
                                     source_id=source_url, event_at=now):
                        created["falha_fonte"] += 1
        # Prazos de isenção (fim da solicitação) próximos ou expirados.
        now_dt = _parse(now)
        horizon = (now_dt + timedelta(days=exemption_horizon_days)).date()
        today = now_dt.date()
        for contest, value_json, proposal_id in conn.execute(
                """SELECT contest_id,value_json,id FROM propostas_campo
                WHERE field_name='exemption_end'"""):
            try:
                raw = json.loads(value_json)
            except (TypeError, ValueError):
                continue
            if not isinstance(raw, str):
                continue  # data desconhecida/malformada não gera alerta
            deadline_dt = _parse(raw if len(raw) > 10 else raw + "T00:00:00+00:00")
            if deadline_dt is None:
                continue
            deadline = deadline_dt.date()
            state = "expirado" if deadline < today else ("proximo" if deadline <= horizon else None)
            if state is None:
                continue
            severity = "critico" if state == "expirado" else "atencao"
            if _insert_alert(conn, kind="prazo_isencao", severity=severity,
                             dedup_key=f"prazo_isencao:{contest}:{value_json}:{state}",
                             title=f"Isenção da taxa {state}",
                             detail=f"Fim da solicitação: {deadline.isoformat()}",
                             contest_id=contest, event_at=now, payload={"proposal_id": proposal_id}):
                created["prazo_isencao"] += 1
        conn.commit()
    except BaseException:
        conn.rollback()
        raise
    finally:
        conn.close()
    return {"created": created, "total": sum(created.values()), "backlog": backlog}


def list_alerts(db_path, *, unseen_only: bool = False, limit: int = 50) -> list[dict]:
    conn = connect_documents(db_path)
    try:
        where = "WHERE seen_at IS NULL AND dismissed_at IS NULL" if unseen_only else ""
        rows = conn.execute(
            f"""SELECT id,kind,severity,contest_id,observation_id,source_id,title,detail,
            event_at,created_at,seen_at,dismissed_at FROM alertas {where}
            ORDER BY created_at DESC, id DESC LIMIT ?""", (max(0, int(limit)),)).fetchall()
        keys = ("id", "kind", "severity", "contest_id", "observation_id", "source_id",
                "title", "detail", "event_at", "created_at", "seen_at", "dismissed_at")
        return [dict(zip(keys, row)) for row in rows]
    finally:
        conn.close()


def alert_counts(db_path) -> dict:
    conn = connect_documents(db_path)
    try:
        total = conn.execute("SELECT count(*) FROM alertas").fetchone()[0]
        unseen = conn.execute(
            "SELECT count(*) FROM alertas WHERE seen_at IS NULL AND dismissed_at IS NULL").fetchone()[0]
        return {"total": total, "unseen": unseen}
    finally:
        conn.close()


# Ordem das categorias de urgência na triagem (menor = mais urgente).
TRIAGE_BUCKETS = ("hoje", "proximos", "retificacoes", "novos", "falhas", "outros")


def _alert_urgency(alert, exemption_end, today, horizon):
    if alert["kind"] == "prazo_isencao" and exemption_end is not None:
        if exemption_end <= today:
            return "hoje"
        if exemption_end <= horizon:
            return "proximos"
    if alert["kind"] == "retificacao":
        return "retificacoes"
    if alert["kind"] in ("novo_candidato", "documento_recuperado"):
        return "novos"
    if alert["kind"] == "falha_fonte":
        return "falhas"
    return "outros"


def triage(db_path, *, now=None, include_seen: bool = False, horizon_days: int = 7,
           limit: int = 200) -> dict:
    """Agrupa alertas por concurso, com urgência calculada a partir de datas documentais.

    Agrupa apenas pelo `contest_id` comprovado — nunca por similaridade de título. Cada
    grupo traz metadados reais do concurso (fonte, prazo de isenção, fila) e os alertas
    individuais (o histórico é preservado). Adiados ficam ocultos até a data; vistos/
    dispensados só aparecem com ``include_seen``.
    """
    now = now or _now()
    now_dt = _parse(now)
    today = now_dt.date()
    horizon = (now_dt + timedelta(days=horizon_days)).date()
    conn = connect_documents(db_path)
    try:
        where = ["(snoozed_until IS NULL OR snoozed_until <= ?)"]
        params = [now]
        if not include_seen:
            where.append("seen_at IS NULL AND dismissed_at IS NULL")
        alerts = conn.execute(
            f"""SELECT id,kind,severity,contest_id,observation_id,source_id,title,detail,
            event_at,created_at,seen_at,dismissed_at,snoozed_until FROM alertas
            WHERE {' AND '.join(where)}
            ORDER BY created_at DESC, id DESC LIMIT ?""", (*params, max(0, int(limit)))).fetchall()
        keys = ("id", "kind", "severity", "contest_id", "observation_id", "source_id", "title",
                "detail", "event_at", "created_at", "seen_at", "dismissed_at", "snoozed_until")
        alerts = [dict(zip(keys, r)) for r in alerts]

        # Prazo de isenção por concurso (data documental; None quando desconhecido).
        # Precedência: valor vigente (`valores_atuais`) > proposta mais recente. Nunca a
        # proposta mais antiga (uma retificação de data não pode rejuvenescer/envelhecer o prazo).
        deadlines = {}
        for contest, value_json in conn.execute(
                "SELECT contest_id, value_json FROM propostas_campo WHERE field_name='exemption_end' "
                "ORDER BY extracted_at ASC, rowid ASC"):
            try:
                raw = json.loads(value_json)
            except (TypeError, ValueError):
                continue
            if isinstance(raw, str) and len(raw) >= 10:
                deadlines[contest] = raw[:10]  # última = mais recente
        for contest, value_json in conn.execute(
                "SELECT v.contest_id, p.value_json FROM valores_atuais v "
                "JOIN propostas_campo p ON p.id=v.proposal_id WHERE v.field_name='exemption_end' "
                "ORDER BY v.selected_at ASC"):
            try:
                raw = json.loads(value_json)
            except (TypeError, ValueError):
                continue
            if isinstance(raw, str) and len(raw) >= 10:
                deadlines[contest] = raw[:10]  # valor vigente sobrepõe

        groups = {}
        for alert in alerts:
            contest = alert["contest_id"] or "sem_concurso"
            group = groups.setdefault(contest, {
                "contest_id": alert["contest_id"], "alerts": [], "kinds": {},
                "sources": set(), "observation_ids": set()})
            group["alerts"].append(alert)
            group["kinds"][alert["kind"]] = group["kinds"].get(alert["kind"], 0) + 1
            if alert["source_id"]:
                group["sources"].add(alert["source_id"])
            if alert["observation_id"]:
                group["observation_ids"].add(alert["observation_id"])

        out = []
        for contest, group in groups.items():
            exemption_end = deadlines.get(contest)
            end_date = None
            if exemption_end:
                parsed = _parse(exemption_end + "T00:00:00+00:00")
                end_date = parsed.date() if parsed else None
            urgency = "outros"
            for alert in group["alerts"]:
                bucket = _alert_urgency(alert, end_date, today, horizon)
                if TRIAGE_BUCKETS.index(bucket) < TRIAGE_BUCKETS.index(urgency):
                    urgency = bucket
            out.append({
                "contest_id": group["contest_id"],
                "alerts": group["alerts"],
                "alert_count": len(group["alerts"]),
                "kinds": group["kinds"],
                "sources": sorted(group["sources"]),
                "observation_ids": sorted(group["observation_ids"]),
                "exemption_end": exemption_end,
                "urgency": urgency,
                "latest_event_at": max((a["event_at"] or a["created_at"]) for a in group["alerts"]),
            })
        out.sort(key=lambda g: g["latest_event_at"], reverse=True)
        out.sort(key=lambda g: TRIAGE_BUCKETS.index(g["urgency"]))
        return {"generated_at": now, "groups": out, "counts": alert_counts(db_path)}
    finally:
        conn.close()


def mark_alert(db_path, alert_id: str, *, seen: bool | None = None,
               dismissed: bool | None = None, snooze_until: str | None = None) -> bool:
    """Marca um alerta como visto/descartado/adiado (não apaga o histórico).

    ``snooze_until`` (ISO) adia a atenção até a data; a triagem o oculta até lá, mas o
    evento permanece registrado. Adiar **não** altera o documento nem o concurso.
    """
    conn = connect_documents(db_path)
    try:
        conn.execute("BEGIN IMMEDIATE")
        row = conn.execute("SELECT id FROM alertas WHERE id=?", (alert_id,)).fetchone()
        if not row:
            conn.rollback()
            return False
        now = _now()
        if seen is not None:
            conn.execute("UPDATE alertas SET seen_at=? WHERE id=?", (now if seen else None, alert_id))
        if dismissed is not None:
            conn.execute("UPDATE alertas SET dismissed_at=? WHERE id=?",
                         (now if dismissed else None, alert_id))
        if snooze_until is not None:
            value = snooze_until or None
            if value is not None:
                parsed = _parse(value)
                if parsed is None:
                    conn.rollback()
                    raise ValueError("data de adiamento inválida")
                # Normaliza para UTC: a comparação em SQL é lexicográfica, então offsets
                # diferentes quebrariam a semântica ("adiar até a data").
                if parsed.tzinfo is None:
                    parsed = parsed.replace(tzinfo=timezone.utc)
                value = parsed.astimezone(timezone.utc).isoformat()
            conn.execute("UPDATE alertas SET snoozed_until=? WHERE id=?", (value, alert_id))
        conn.commit()
        return True
    except BaseException:
        conn.rollback()
        raise
    finally:
        conn.close()


# --- Ciclo operacional -------------------------------------------------------

def _select_sources(cfg):
    """Descritores de fonte habilitados, reutilizando ``monitoring.default_sources``."""
    from radar.monitoring import default_sources
    enabled = cfg["sources"]
    # Mapa inverso: id do descritor -> chave de configuração.
    id_to_key = {sid: key for key, sid in _CONFIG_TO_SOURCE_ID.items() if sid}
    picked = []
    for source in default_sources():
        sid = source.get("id")
        key = id_to_key.get(sid) if sid else "guajara"
        if key is None:
            continue  # descritor desconhecido: não liga por engano
        opts = enabled.get(key)
        if opts and opts.get("enabled"):
            picked.append(source)
    return picked


def run_cycle(config, *, sources=None, transport=None, now=None, logger=None) -> dict:
    """Executa um ciclo operacional completo e devolve um resumo verificável."""
    now = now or _now()
    logger = logger or logging.getLogger(LOGGER_NAME)
    run_id = str(uuid4())
    started = now
    result = {"run_id": run_id, "started_at": started, "state": "falhou", "config_errors": [],
              "sources": [], "confirmation": {}, "alerts": {}, "errors": []}

    from radar.ops_config import validate_config
    errors = validate_config(config)
    result["config_errors"] = errors
    if errors:
        result["state"] = "falhou"
        logger.error("run=%s configuração inválida: %s", run_id, "; ".join(errors))
        return result

    db_path = config["db_path"]
    Path(db_path).parent.mkdir(parents=True, exist_ok=True)
    if not Path(db_path).exists() or _schema_version(db_path) != SCHEMA_VERSION:
        migrate_document_schema(db_path)

    lock = InstanceLock(str(Path(db_path).parent / LOCK_FILENAME), now=lambda: started)
    try:
        acquired = lock.acquire()
    except OSError as error:
        result["state"] = "falhou"
        result["errors"].append({"stage": "lock", "error_code": type(error).__name__})
        logger.error("run=%s falha ao adquirir o bloqueio: %s", run_id, type(error).__name__)
        result["finished_at"] = _now()
        return result
    if not acquired:
        result["state"] = "ignorado"
        logger.warning("run=%s ignorado: outra execução ativa", run_id)
        result["finished_at"] = _now()
        return result
    try:
        logger.info("run=%s início db=%s", run_id, db_path)
        # 1) Coleta das fontes habilitadas (falha isolada por fonte, já tratada no ciclo).
        from radar.monitoring import run_cycle as monitoring_cycle
        cycle = monitoring_cycle(db_path, sources=sources if sources is not None else _select_sources(config),
                                 transport=transport, analyze=config.get("analyze", True))
        result["sources"] = cycle.get("sources", [])
        result["cycle_id"] = cycle.get("cycle_id")
        result["cycle_state"] = cycle.get("state")

        # 2) Reconciliação multifonte (conservadora).
        from radar import confirmation
        result["confirmation"]["reconcile"] = confirmation.reconcile(db_path)

        # 3) Fila: enfileirar candidatos elegíveis e processar um lote limitado.
        result["confirmation"]["enqueued"] = confirmation.enqueue_pending(db_path)
        batch = confirmation.process_batch(
            db_path, limit=int(config.get("batch_limit", 10)), now=now)
        result["confirmation"]["batch"] = batch

        # 4) Alertas persistentes do ciclo (orçamento configurável; excedente vira backlog).
        result["alerts"] = generate_alerts(
            db_path, cycle_id=cycle.get("cycle_id"), now=now,
            max_new_alerts=int(config.get("max_new_alerts_per_cycle", 200)))

        # 5) Notificações nativas (opcional; falha não derruba o ciclo).
        try:
            from radar import notifications
            result["notifications"] = notifications.dispatch(db_path, config, now=now)
        except Exception as error:
            result["notifications"] = {"error": type(error).__name__}
            logger.warning("run=%s notificações: %s", run_id, type(error).__name__)

        # 6) Estado final: concluído, parcial, falhou.
        states = [s.get("state") for s in result["sources"]]
        if states and all(s == "falhou" for s in states):
            result["state"] = "falhou"
        elif states and all(s == "concluido" for s in states):
            result["state"] = "concluido"
        else:
            result["state"] = "parcial"
        logger.info("run=%s fim estado=%s fontes=%s", run_id, result["state"],
                    [(s.get("source_url"), s.get("state")) for s in result["sources"]])
    except Exception as error:  # nunca deixa o ciclo sem estado explícito
        result["state"] = "falhou"
        result["errors"].append({"stage": "cycle", "error_code": type(error).__name__})
        logger.exception("run=%s falhou: %s", run_id, type(error).__name__)
    finally:
        lock.release()
    result["finished_at"] = _now()
    return result


# --- Saúde -------------------------------------------------------------------

def _server_up(host: str = "127.0.0.1", port: int = 8000, timeout: float = 0.5) -> bool:
    try:
        with socket.create_connection((host, port), timeout=timeout):
            return True
    except OSError:
        return False


def health(config, *, check_server: bool = True, now=None) -> dict:
    """Estado real do sistema: config, banco, leitura, servidor, ciclos, fila e alertas."""
    now_dt = _parse(now or _now())
    out = {"ready": False, "status": "indisponivel", "config_errors": [], "database": {},
           "sources": [], "queue": {}, "alerts": {}, "server": {"checked": check_server,
           "up": None}, "last_cycle": None, "next_run_at": None, "stuck_runs": 0,
           "limitations": []}
    from radar.ops_config import validate_config
    errors = validate_config(config)
    out["config_errors"] = errors
    if errors:
        out["status"] = "configuracao_invalida"
        return out

    db_path = config["db_path"]
    out["database"]["path"] = db_path
    out["database"]["exists"] = Path(db_path).exists()
    if not out["database"]["exists"]:
        out["status"] = "banco_indisponivel"
        out["limitations"].append("banco ainda não criado; rode um ciclo")
        return out
    conn = None
    try:
        conn = connect_documents(db_path)
        version = conn.execute("PRAGMA user_version").fetchone()[0]
        out["database"]["schema_version"] = version
        records = conn.execute("SELECT count(*) FROM concursos_identidade").fetchone()[0]
        out["database"]["readable"] = True
        out["database"]["contests"] = records
        out["alerts"] = alert_counts(db_path)
        out["queue"] = _queue_health(conn, now_dt)
        last = conn.execute(
            """SELECT id,started_at,finished_at,state FROM ciclos_monitoramento
            ORDER BY started_at DESC, id DESC LIMIT 1""").fetchone()
        if last:
            out["last_cycle"] = {"id": last[0], "started_at": last[1], "finished_at": last[2],
                                 "state": last[3]}
            out["sources"] = [dict(zip(("source_url", "state", "checked_at", "error_code"), row))
                              for row in conn.execute(
                                  """SELECT source_url,state,checked_at,error_code FROM ciclos_fontes
                                  WHERE cycle_id=? ORDER BY source_url""", (last[0],))]
        out["stuck_runs"] = conn.execute(
            "SELECT count(*) FROM ciclos_monitoramento WHERE state='em_andamento'").fetchone()[0]
        try:
            from radar import notifications
            out["notifications"] = notifications.notification_state(db_path)
        except Exception:
            out["notifications"] = {}
    except Exception as error:
        out["database"]["error"] = type(error).__name__
        out["status"] = "banco_indisponivel"
        return out
    finally:
        if conn is not None:
            conn.close()

    if check_server:
        out["server"]["up"] = _server_up()
    out["ready"] = True
    out["status"] = _health_status(out, now_dt)
    return out


def _queue_health(conn, now_dt) -> dict:
    counts = {"pendente": 0, "em_processamento": 0}
    for state, total in conn.execute("SELECT state,count(*) FROM fila_confirmacao GROUP BY state"):
        counts[state] = total
    return {"pending": counts.get("pendente", 0), "processing": counts.get("em_processamento", 0),
            "by_state": counts}


def _health_status(out, now_dt) -> str:
    cycle = out.get("last_cycle")
    if cycle is None:
        return "sem_ciclo"
    if cycle["state"] == "em_andamento" or out.get("stuck_runs"):
        return "execucao_atrasada"
    failed = [s for s in out.get("sources", []) if s.get("state") == "falhou"]
    if failed and len(failed) == len(out.get("sources", [])):
        return "fontes_indisponiveis"
    if failed or (cycle.get("state") in ("parcial", "falhou", "interrompido")):
        return "funcionando_com_limitacoes"
    return "pronto"
