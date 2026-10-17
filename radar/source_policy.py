"""Política de persistência: a única porta de entrada para gravar conteúdo externo.

Nenhum conector deve escrever conteúdo sem consultar esta camada. A decisão é por
``(fonte, tipo de conteúdo)`` e vem do catálogo versionado (`radar/source_catalog.py`).

Consequências práticas:
- ``persistencia_permitida``: pode gravar, com proveniência (fonte, URL, data, hash).
- ``uso_transitorio``: só pode ser usado em memória durante a operação; proibido gravar em
  SQLite, arquivo de cache, exportação ou log.
- ``persistencia_nao_verificada``: tratada como proibida até revisão de termos.
- ``acesso_bloqueado``: nem consultar.
- ``importacao_manual_controlada``: só pelo fluxo de ingestão manual, com procedência.
"""

from __future__ import annotations

from contextlib import closing
from datetime import datetime, timezone
from uuid import uuid4

from radar import source_catalog as catalog
from radar.document_store import connect_documents, is_readable_schema

SOURCES_SCHEMA_VERSION = 18


def is_sources_schema(conn) -> bool:
    return conn.execute("PRAGMA user_version").fetchone()[0] >= SOURCES_SCHEMA_VERSION

POLICY_VERSION = "policy_v1"


class PolicyError(ValueError):
    """Operação recusada pela política de persistência."""

    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code


def decision(source_id: str, content_type: str) -> dict:
    """Decisão explicada, sem efeito colateral."""
    try:
        source = catalog.get_source(source_id)
    except KeyError as error:
        raise PolicyError("fonte_desconhecida", f"fonte não catalogada: {source_id}") from error
    entry = source["content"].get(content_type)
    if entry is None:
        return {
            "source_id": source_id, "content_type": content_type, "allowed": False,
            "permission": catalog.ACESSO_BLOQUEADO,
            "permission_label": catalog.PERMISSION_LABELS[catalog.ACESSO_BLOQUEADO],
            "reason": "tipo de conteúdo não declarado para esta fonte",
            "source_status": source["status"],
        }
    permission = entry["permission"]
    allowed = permission == catalog.PERSISTENCIA_PERMITIDA
    reason = entry["note"]
    if source["status"] != "habilitada":
        # Lista positiva: qualquer estado diferente de "habilitada" bloqueia a persistência.
        allowed = False
        reason = f"{reason}; estado da fonte: {source['status']}"
    return {
        "source_id": source_id,
        "content_type": content_type,
        "allowed": allowed,
        "permission": permission,
        "permission_label": catalog.PERMISSION_LABELS[permission],
        "reason": reason,
        "license": entry.get("license"),
        "evidence_url": entry.get("evidence_url"),
        "verified_at": entry.get("verified_at"),
        "confidence": entry.get("confidence"),
        "source_status": source["status"],
    }


def require_persist(source_id: str, content_type: str, *, purpose: str = "conteudo") -> dict:
    """Autoriza a persistência ou levanta ``PolicyError`` com o motivo real."""
    result = decision(source_id, content_type)
    if result["allowed"]:
        return result
    raise PolicyError("persistencia_nao_autorizada",
                      f"persistência de {content_type} de {source_id} não autorizada "
                      f"({result['permission']}): {result['reason']} [{purpose}]")


def can_persist(source_id: str, content_type: str) -> bool:
    return decision(source_id, content_type)["allowed"]


def transient_only(source_id: str, content_type: str) -> bool:
    return decision(source_id, content_type)["permission"] == catalog.SOMENTE_USO_TRANSITORIO


def redact_for_log(value, *, source_id: str, content_type: str):
    """Remove corpo de conteúdo transitório antes de qualquer log/relatório.

    Metadados e URLs continuam utilizáveis; o corpo do conteúdo não.
    """
    if transient_only(source_id, content_type):
        return {"redacted": True, "source_id": source_id, "content_type": content_type,
                "reason": "conteúdo transitório não pode ser persistido nem logado"}
    return value


def audit() -> dict:
    """Mapa de decisões por fonte/tipo, para a visão operacional."""
    items = []
    for source in catalog.catalog():
        for content_type in source["content"]:
            items.append(decision(source["id"], content_type))
    return {"version": POLICY_VERSION, "total": len(items), "decisoes": items}


def record_review(db_path, source_id: str, *, reviewer: str, review_decision: str,
                  note: str, now: str | None = None) -> dict:
    """Registra revisão humana de política (append-only), sem alterar o catálogo."""
    catalog.get_source(source_id)
    decision = review_decision
    if decision not in ("manter", "restringir", "ampliar", "suspender"):
        raise PolicyError("decisao_invalida", "decisão de revisão inválida")
    if not isinstance(reviewer, str) or not reviewer.strip():
        raise PolicyError("revisor_obrigatorio", "revisor obrigatório")
    if not isinstance(note, str) or not note.strip():
        raise PolicyError("justificativa_obrigatoria", "justificativa obrigatória")
    at = now or datetime.now(timezone.utc).isoformat()
    review_id = str(uuid4())
    with closing(connect_documents(db_path)) as conn, conn:
        if not is_sources_schema(conn):
            raise ValueError("migração documental pendente")
        conn.execute("INSERT INTO fontes_revisoes (id,source_id,reviewed_at,reviewer,decision,"
                     "note) VALUES (?,?,?,?,?,?)",
                     (review_id, source_id, at, reviewer.strip(), decision, note.strip()))
    return {"version": POLICY_VERSION, "review_id": review_id, "source_id": source_id,
            "decision": decision, "reviewed_at": at}


def review_history(db_path, source_id: str | None = None, *, limit: int = 50) -> dict:
    if source_id is not None and not source_id:
        raise PolicyError("fonte_obrigatoria", "source_id vazio")
    catalog.get_source(source_id) if source_id else None
    limit = int(limit)
    if limit < 1 or limit > 500:
        raise ValueError("limite fora da faixa")
    with closing(connect_documents(db_path)) as conn:
        if not is_sources_schema(conn):
            raise ValueError("migração documental pendente")
        if source_id:
            rows = conn.execute(
                "SELECT id,source_id,reviewed_at,reviewer,decision,note FROM fontes_revisoes "
                "WHERE source_id=? ORDER BY reviewed_at DESC, rowid DESC LIMIT ?",
                (source_id, limit)).fetchall()
        else:
            rows = conn.execute(
                "SELECT id,source_id,reviewed_at,reviewer,decision,note FROM fontes_revisoes "
                "ORDER BY reviewed_at DESC, rowid DESC LIMIT ?", (limit,)).fetchall()
    return {"version": POLICY_VERSION, "total": len(rows),
            "itens": [{"review_id": row[0], "source_id": row[1], "reviewed_at": row[2],
                       "reviewer": row[3], "decision": row[4], "note": row[5]}
                      for row in rows]}
