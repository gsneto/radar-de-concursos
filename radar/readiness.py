"""Relatório único de prontidão do backend (Fase 44).

O objetivo é responder, com evidência e sem otimismo, se o backend pode sustentar o
frontend de produto. O relatório **não** executa a suíte de testes nem baixa documentos:
ele lê o banco, o catálogo e o contrato de API. Pendências documentais isoladas não
tornam o backend indisponível; falha de integridade, schema ou proveniência torna.
"""

from __future__ import annotations

import json
import sqlite3
import threading
import time
from contextlib import closing
from datetime import datetime, timezone
from pathlib import Path

from radar.document_store import connect_documents, is_readable_schema

VERSION = "readiness_v1"
SCHEMA_MIN = 21
_CACHE = {}
_CACHE_LOCK = threading.Lock()
_COMPUTE_LOCK = threading.Lock()
_CACHE_TTL_SECONDS = 60
_CACHE_MAX = 4


def _cache_key(db_path, config, full):
    if full:
        return None
    path = Path(db_path)
    try:
        stat = path.stat()
    except OSError:
        return None
    sources = json.dumps((config or {}).get("sources") or {}, sort_keys=True)
    interval = (config or {}).get("monitor_interval_hours")
    return (str(path.resolve()), stat.st_mtime_ns, stat.st_size, sources, interval)


def _now(now=None) -> str:
    if now is None:
        return datetime.now(timezone.utc).isoformat()
    if isinstance(now, datetime):
        return (now if now.tzinfo else now.replace(tzinfo=timezone.utc)).isoformat()
    return str(now)


def _scalar(conn, sql, params=(), default=0):
    try:
        row = conn.execute(sql, params).fetchone()
    except sqlite3.Error:
        return default
    return row[0] if row and row[0] is not None else default


def _table_exists(conn, name: str) -> bool:
    return bool(conn.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?", (name,)).fetchone())


def _count(conn, name: str) -> int:
    return int(_scalar(conn, f'SELECT COUNT(*) FROM "{name}"')) if _table_exists(conn, name) else 0


def _last_backup(db_path: str) -> dict | None:
    path = Path(db_path)
    candidates = sorted(path.parent.glob(path.name + ".bak-*"))
    if not candidates:
        return None
    latest = candidates[-1]
    return {"path": latest.name,
            "size": latest.stat().st_size,
            "modified_at": datetime.fromtimestamp(
                latest.stat().st_mtime, tz=timezone.utc).isoformat()}


def _build_report(db_path: str, *, config: dict | None = None, now=None) -> dict:
    """Monta o relatório de prontidão com checks explícitos e pendências reais."""
    generated = _now(now)
    checks: list[dict] = []
    pending: list[dict] = []

    def check(identifier: str, label: str, status: str, evidence, *, blocking=False):
        checks.append({"id": identifier, "label": label, "status": status,
                       "evidence": evidence, "blocking": bool(blocking)})

    path = Path(db_path)
    if not path.exists():
        check("banco_existe", "Banco SQLite existe", "reprovado",
              {"path": db_path}, blocking=True)
        return {"version": VERSION, "generated_at": generated, "status": "bloqueado",
                "ready": False, "checks": checks, "pendencias": pending,
                "database": {}, "pipeline": {}, "domain": {}, "sources": {},
                "monitoring": {}, "studies": {}, "api": {}, "backup": None,
                "limitations": ["banco inexistente; nenhuma leitura foi feita"]}
    check("banco_existe", "Banco SQLite existe", "aprovado", {"path": db_path})

    try:
        conn = connect_documents(db_path)
    except Exception as error:  # schema incompatível ou arquivo ilegível
        check("schema", "Schema legível", "reprovado", {"error": type(error).__name__},
              blocking=True)
        return {"version": VERSION, "generated_at": generated, "status": "bloqueado",
                "ready": False, "checks": checks, "pendencias": pending,
                "database": {}, "pipeline": {}, "domain": {}, "sources": {},
                "monitoring": {}, "studies": {}, "api": {}, "backup": None,
                "limitations": ["schema não pôde ser aberto"]}

    with closing(conn):
        schema = int(conn.execute("PRAGMA user_version").fetchone()[0])
        if not is_readable_schema(conn):
            check("schema", "Schema documental legível", "reprovado",
                  {"version": schema, "minimo": SCHEMA_MIN}, blocking=True)
            return {"version": VERSION, "generated_at": generated, "status": "bloqueado",
                    "ready": False, "checks": checks, "pendencias": pending,
                    "database": {"path": db_path, "schema_version": schema},
                    "pipeline": {}, "domain": {}, "sources": {}, "monitoring": {},
                    "studies": {}, "api": {}, "backup": None,
                    "limitations": ["schema pendente: nenhuma consulta de domínio foi feita"]}
        check("schema", "Schema documental atual", "aprovado" if schema >= SCHEMA_MIN
              else "reprovado", {"version": schema, "minimo": SCHEMA_MIN},
              blocking=schema < SCHEMA_MIN)

        integrity = conn.execute("PRAGMA integrity_check").fetchone()[0]
        check("integridade", "Integridade SQLite", "aprovado" if integrity == "ok"
              else "reprovado", {"integrity_check": integrity},
              blocking=integrity != "ok")

        fk = conn.execute("PRAGMA foreign_key_check").fetchall()
        check("chaves_estrangeiras", "Chaves estrangeiras", "aprovado" if not fk
              else "reprovado", {"violacoes": len(fk)}, blocking=bool(fk))

        journal = conn.execute("PRAGMA journal_mode").fetchone()[0]
        tables = {row[0] for row in conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table'")}
        required = {"documentos", "versoes_documento", "blocos_documento",
                    "propostas_campo", "evidencias", "revisoes_campo",
                    "valores_atuais", "concursos_identidade"}
        missing = sorted(required - tables)
        if missing:
            check("tabelas", "Tabelas obrigatórias", "reprovado",
                  {"faltando": missing}, blocking=True)
            return {"version": VERSION, "generated_at": generated, "status": "bloqueado",
                    "ready": False, "checks": checks, "pendencias": pending,
                    "database": {"path": db_path, "schema_version": schema,
                                 "tables": len(tables)},
                    "pipeline": {}, "domain": {}, "sources": {}, "monitoring": {},
                    "studies": {}, "api": {}, "backup": _last_backup(db_path),
                    "limitations": ["tabelas obrigatórias ausentes: schema incompleto"]}

        documentos = _count(conn, "documentos")
        versoes = _count(conn, "versoes_documento")
        blocos = _count(conn, "blocos_documento")
        propostas = _count(conn, "propostas_campo")
        evidencias = _count(conn, "evidencias")
        revisoes = _count(conn, "revisoes_campo")
        valores = _count(conn, "valores_atuais")
        reconciliacoes = _count(conn, "reconciliacoes_cargo")
        lotes = _count(conn, "lotes_revisao")

        sem_versao = int(_scalar(
            conn, "SELECT COUNT(*) FROM documentos d WHERE NOT EXISTS "
                  "(SELECT 1 FROM versoes_documento v WHERE v.document_id=d.id)"))
        por_estado = {state: total for state, total in conn.execute(
            "SELECT extraction_state, COUNT(*) FROM versoes_documento GROUP BY 1")}
        sem_blocos = int(_scalar(
            conn, "SELECT COUNT(*) FROM versoes_documento v WHERE NOT EXISTS "
                  "(SELECT 1 FROM blocos_documento b WHERE b.version_id=v.id)"))
        propostas_sem_evidencia = int(_scalar(
            conn, "SELECT COUNT(*) FROM propostas_campo p WHERE NOT EXISTS "
                  "(SELECT 1 FROM evidencias e WHERE e.id=p.evidence_id)"))
        evidencias_vazias = int(_scalar(
            conn, "SELECT COUNT(*) FROM evidencias WHERE quote IS NULL OR TRIM(quote)=''"))
        versoes_sem_hash = int(_scalar(
            conn, "SELECT COUNT(*) FROM versoes_documento "
                  "WHERE sha256 IS NULL OR LENGTH(sha256) != 64"))
        versoes_falhas = {code or "(sem código)": total for code, total in conn.execute(
            "SELECT error_code, COUNT(*) FROM versoes_documento "
            "WHERE extraction_state='falhou' GROUP BY 1")}

        check("proveniencia", "Toda proposta tem evidência", "aprovado"
              if propostas_sem_evidencia == 0 else "reprovado",
              {"propostas": propostas, "evidencias": evidencias,
               "propostas_sem_evidencia": propostas_sem_evidencia},
              blocking=propostas_sem_evidencia > 0)
        check("evidencia_literal", "Evidência não vazia", "aprovado"
              if evidencias_vazias == 0 else "pendente",
              {"evidencias_vazias": evidencias_vazias})
        if evidencias_vazias:
            pending.append({"codigo": "evidencias_vazias", "total": evidencias_vazias,
                            "texto": "evidência sem trecho literal; revisar a extração"})
        check("hash_documental", "Versões com SHA-256", "aprovado"
              if versoes_sem_hash == 0 else "reprovado",
              {"versoes": versoes, "sem_hash": versoes_sem_hash},
              blocking=versoes_sem_hash > 0)

        conflicts_total = 0
        try:
            from radar import conflict_review
            conflicts_total = int(conflict_review.conflict_groups(db_path, limit=1)["total"])
        except Exception as error:
            check("conflitos", "Conflitos classificáveis", "pendente",
                  {"error": type(error).__name__})
        else:
            check("conflitos", "Conflitos classificáveis", "aprovado",
                  {"total": conflicts_total, "nota": "pendência, não bloqueio"})

        revalidacao = {"total": None}
        try:
            from radar import deadline_revalidation
            revalidacao = deadline_revalidation.plan(db_path, limit=1)
        except Exception as error:
            revalidacao = {"total": None, "error": type(error).__name__}

        from radar import budget
        try:
            sources = budget.state_report(db_path, config=config)
        except Exception as error:
            sources = {"total": 0, "error": type(error).__name__}
        enabled = [item for item in sources.get("items", []) if item.get("enabled")]
        failed = [item for item in sources.get("items", [])
                  if item.get("last_run_status") == "falhou"]
        check("fontes_catalogo", "Catálogo de fontes", "aprovado"
              if sources.get("total") else "reprovado",
              {"total": sources.get("total"), "habilitadas": len(enabled),
               "com_falha": len(failed)}, blocking=not sources.get("total"))

        external = []
        try:
            from radar import source_catalog
            for source in source_catalog.catalog():
                if source.get("status") == "aguardando_credencial" or (
                        source.get("credential_env") and source.get("status") != "habilitada"):
                    external.append({"id": source["id"], "status": source["status"],
                                     "credential_env": source.get("credential_env")})
        except Exception:
            external = []
        if external:
            check("credenciais_externas", "Credenciais externas", "pendente_externo",
                  {"fontes": external})
            pending.append({"codigo": "credenciais_externas",
                            "total": len(external),
                            "texto": "fontes dependem de credencial/termos; não bloqueiam o produto"})

        last_cycle = None
        stuck = 0
        next_run = None
        if "ciclos_monitoramento" in tables:
            row = conn.execute(
                "SELECT id,started_at,finished_at,state FROM ciclos_monitoramento "
                "ORDER BY started_at DESC, id DESC LIMIT 1").fetchone()
            if row:
                last_cycle = {"id": row[0], "started_at": row[1], "finished_at": row[2],
                              "state": row[3]}
            stuck = int(_scalar(conn, "SELECT COUNT(*) FROM ciclos_monitoramento "
                                     "WHERE state='em_andamento'"))
            if last_cycle:
                interval = 6
                if config and config.get("monitor_interval_hours"):
                    interval = int(config["monitor_interval_hours"])
                try:
                    started = datetime.fromisoformat(last_cycle["started_at"])
                    if not started.tzinfo:
                        started = started.replace(tzinfo=timezone.utc)
                    from datetime import timedelta
                    next_run = (started + timedelta(hours=interval)).isoformat()
                except (TypeError, ValueError):
                    next_run = None
        cycle_state = (last_cycle or {}).get("state")
        cycle_ok = cycle_state == "concluido"
        check("monitoramento", "Ciclo de monitoramento",
              "aprovado" if cycle_ok else ("pendente" if last_cycle else "pendente"),
              {"last_cycle": last_cycle, "stuck_runs": stuck,
               "next_run_at": next_run})
        if last_cycle and not cycle_ok:
            pending.append({"codigo": "ultimo_ciclo_" + str(cycle_state), "total": 1,
                            "texto": "o último ciclo não terminou concluído; fontes podem ter falhado"})
        if stuck:
            pending.append({"codigo": "ciclos_em_andamento", "total": stuck,
                            "texto": "execução anterior sem estado final; o próximo ciclo a encerra"})
        if sem_versao:
            pending.append({"codigo": "documentos_sem_versao", "total": sem_versao,
                            "texto": "documento descoberto ainda não baixado/importado"})
        if por_estado.get("parcial"):
            pending.append({"codigo": "extracoes_parciais", "total": por_estado["parcial"],
                            "texto": "PDF longo lido por prefixo; páginas restantes são retomáveis"})
        if por_estado.get("falhou"):
            pending.append({"codigo": "extracoes_falhas", "total": por_estado["falhou"],
                            "texto": "versão sem texto extraível; OCR é opcional"})
        if conflicts_total:
            pending.append({"codigo": "conflitos_documentais", "total": conflicts_total,
                            "texto": "conflito classificado aguarda decisão humana; não bloqueia"})
        if revalidacao.get("total"):
            pending.append({"codigo": "prazos_a_revalidar",
                            "total": revalidacao["total"],
                            "texto": "prazo futuro ainda sem verificação registrada"})

        studies = {name: _count(conn, name) for name in (
            "estudo_disciplinas", "estudo_topicos", "estudo_sessoes", "estudo_revisoes",
            "estudo_perfil", "pratica_flashcards", "pratica_questoes", "pratica_tentativas",
            "pratica_simulados", "pratica_pacotes", "pratica_midias")}
        check("estudos", "Serviços de estudos", "aprovado" if all(
            name in tables for name in ("estudo_sessoes", "pratica_flashcards",
                                        "pratica_questoes", "pratica_simulados"))
              else "reprovado", {"tabelas": studies}, blocking=True)

        api = {}
        try:
            from radar import api_contract
            api = api_contract.verify(str(Path(__file__).resolve().parent / "server.py"))
        except Exception as error:
            api = {"ok": False, "error": type(error).__name__}
        check("contrato_api", "Contrato de API cobre o servidor", "aprovado"
              if api.get("ok") else "reprovado", api,
              blocking=not api.get("ok"))

    database = {
        "path": db_path, "schema_version": schema, "journal_mode": journal,
        "integrity": integrity, "foreign_key_violations": len(fk),
        "tables": len(tables),
        "counts": {"documentos": documentos, "versoes": versoes, "blocos": blocos,
                   "propostas": propostas, "evidencias": evidencias,
                   "revisoes": revisoes, "valores_atuais": valores,
                   "reconciliacoes": reconciliacoes, "lotes": lotes},
    }
    pipeline = {
        "documentos_sem_versao": sem_versao,
        "versoes_por_estado": por_estado,
        "versoes_sem_blocos": sem_blocos,
        "versoes_com_falha": versoes_falhas,
        "propostas_sem_evidencia": propostas_sem_evidencia,
        "evidencias_vazias": evidencias_vazias,
    }
    domain = {"conflitos": conflicts_total,
              "prazos_a_revalidar": revalidacao.get("total"),
              "revisoes_registradas": revisoes,
              "valores_vigentes": valores,
              "reconciliacoes": reconciliacoes}
    monitoring = {"last_cycle": last_cycle, "next_run_at": next_run,
                  "stuck_runs": stuck,
                  "sources_habilitadas": len(enabled),
                  "sources_com_falha": len(failed)}
    sources_out = {"total": sources.get("total", 0), "habilitadas": len(enabled),
                   "com_falha": len(failed), "credenciais_externas": external}
    backup = _last_backup(db_path)

    failed = [item for item in checks if item["status"] == "reprovado"]
    external = [item for item in checks if item["status"] == "pendente_externo"]
    status = ("bloqueado" if failed else
              "pronto_com_pendencias" if (pending or external) else "pronto")
    return {
        "version": VERSION, "generated_at": generated, "status": status,
        "ready": not failed,
        "checks": checks, "pendencias": pending, "database": database,
        "pipeline": pipeline, "domain": domain, "sources": sources_out,
        "monitoring": monitoring, "studies": studies, "api": api, "backup": backup,
        "limitations": [
            "o relatório lê o banco e o contrato; não executa a suíte de testes",
            "pendência documental isolada não é indisponibilidade do backend",
        ],
    }


def report(db_path: str, *, config: dict | None = None, now=None, full: bool = False) -> dict:
    """Relatório com cache curto (60 s) e geração single-flight.

    ``full=True`` ignora o cache (usado no fechamento/CLI). O cache é invalidado por
    mtime/tamanho do banco e pela configuração de fontes; não por filtros do cliente,
    porque o endpoint não aceita filtros.
    """
    key = _cache_key(db_path, config, full)
    if key is None:
        return _build_report(db_path, config=config, now=now)
    with _CACHE_LOCK:
        cached = _CACHE.get(key)
        if cached and time.time() - cached[0] < _CACHE_TTL_SECONDS:
            return cached[1]
    with _COMPUTE_LOCK:
        with _CACHE_LOCK:
            cached = _CACHE.get(key)
            if cached and time.time() - cached[0] < _CACHE_TTL_SECONDS:
                return cached[1]
        result = _build_report(db_path, config=config, now=now)
        with _CACHE_LOCK:
            if len(_CACHE) >= _CACHE_MAX:
                _CACHE.clear()
            _CACHE[key] = (time.time(), result)
        return result
