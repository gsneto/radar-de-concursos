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


def generate_alerts(db_path, *, cycle_id=None, since=None, now=None,
                    exemption_horizon_days: int = 7) -> dict:
    """Gera alertas persistentes a partir do estado atual (deduplicados por chave).

    ``since`` limita "novidades" (documentos/versões descobertos no ciclo). Alertas de
    prazo e de falha de fonte são reavaliados a cada ciclo, mas a dedup evita repetir.
    """
    now = now or _now()
    since = since or now
    created = {"novo_candidato": 0, "documento_recuperado": 0, "retificacao": 0,
               "falha_fonte": 0, "prazo_isencao": 0, "lote_confirmacao": 0}
    conn = connect_documents(db_path)
    try:
        conn.execute("BEGIN IMMEDIATE")
        # Novos documentos (descoberta) e retificações.
        for doc_id, kind, title, discovered_at, obs, contest in conn.execute(
                """SELECT id,kind,title,discovered_at,observation_id,contest_id FROM documentos
                WHERE discovered_at >= ? ORDER BY discovered_at DESC LIMIT 50""", (since,)):
            if _insert_alert(conn, kind="novo_candidato", severity="info",
                             dedup_key=f"novo_candidato:{doc_id}", title=f"Novo candidato: {title}",
                             contest_id=contest, observation_id=obs, event_at=discovered_at):
                created["novo_candidato"] += 1
            if kind == "retificacao" and _insert_alert(
                    conn, kind="retificacao", severity="atencao",
                    dedup_key=f"retificacao:{doc_id}", title=f"Retificação: {title}",
                    contest_id=contest, observation_id=obs, event_at=discovered_at):
                created["retificacao"] += 1
        # Documentos recuperados (versões novas).
        for doc_id, contest, fetched_at, byte_size in conn.execute(
                """SELECT v.document_id,d.contest_id,v.fetched_at,v.byte_size
                FROM versoes_documento v JOIN documentos d ON d.id=v.document_id
                WHERE v.fetched_at >= ? ORDER BY v.fetched_at DESC LIMIT 50""", (since,)):
            if _insert_alert(conn, kind="documento_recuperado", severity="info",
                             dedup_key=f"documento_recuperado:{doc_id}:{fetched_at}",
                             title="Documento oficial recuperado", detail=f"{byte_size} bytes",
                             contest_id=contest, event_at=fetched_at):
                created["documento_recuperado"] += 1
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
    return {"created": created, "total": sum(created.values())}


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


def mark_alert(db_path, alert_id: str, *, seen: bool | None = None,
               dismissed: bool | None = None) -> bool:
    """Marca um alerta como visto/descartado (não apaga o histórico)."""
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

        # 4) Alertas persistentes do ciclo.
        result["alerts"] = generate_alerts(db_path, cycle_id=cycle.get("cycle_id"), since=started, now=now)

        # 5) Estado final: concluído, parcial, falhou.
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
