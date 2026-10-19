"""Orçamento e consumo por fonte e por execução.

Regras:
- nenhuma chamada paga sem custo verificado e orçamento suficiente;
- limites por execução (chamadas, itens, créditos e valor) e janela mensal;
- consumo real registrado após a resposta, com checkpoint para retomada;
- relatório por execução, sem segredos.
"""

from __future__ import annotations

import json
from contextlib import closing
from datetime import datetime, timezone
from uuid import uuid4

from radar import source_catalog as catalog
from radar import source_policy
from radar.document_store import connect_documents, is_readable_schema

BUDGET_VERSION = "budget_v1"

DEFAULT_LIMITS = {
    "max_calls": 50,
    "max_items": 500,
    "max_credits": 0,
    "max_cost": 0,
    "currency": "BRL",
}


class BudgetError(ValueError):
    """Chamada recusada por custo não verificado ou orçamento esgotado."""

    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _month_start(iso: str) -> str:
    """Primeiro instante do mês da execução (janela mensal de consumo)."""
    try:
        moment = datetime.fromisoformat(iso)
    except ValueError:
        moment = datetime.now(timezone.utc)
    return moment.replace(day=1, hour=0, minute=0, second=0, microsecond=0).isoformat()


def limits_for(source_id: str, overrides: dict | None = None) -> dict:
    """Limites efetivos: padrão → catálogo → configuração do operador."""
    limits = dict(DEFAULT_LIMITS)
    source = catalog.get_source(source_id)
    cost = source.get("cost") or {}
    if cost.get("verified") and isinstance(cost.get("amount"), (int, float)):
        # Uma execução não pode custar mais que uma unidade de cobrança por padrão.
        limits["max_cost"] = float(cost["amount"])
        limits["currency"] = cost.get("currency") or limits["currency"]
    if source.get("monthly_limit"):
        limits["max_calls"] = min(limits["max_calls"], int(source["monthly_limit"]))
    for key, value in (overrides or {}).items():
        if key in limits and value is not None:
            limits[key] = value
    return limits


def require_paid_allowed(source_id: str, estimated_cost: float = 0.0) -> dict:
    """Recusa consumo pago sem custo verificado ou sem autorização explícita."""
    source = catalog.get_source(source_id)
    cost = source.get("cost") or {}
    if estimated_cost and estimated_cost > 0:
        if not cost.get("verified"):
            raise BudgetError("custo_nao_verificado",
                              f"custo de {source_id} não verificado: consumo pago recusado")
        if not cost.get("authorized"):
            raise BudgetError("consumo_pago_nao_autorizado",
                              f"consumo pago de {source_id} não autorizado na configuração")
    return cost


def open_run(db_path, source_id: str, *, overrides: dict | None = None,
             now: str | None = None) -> dict:
    """Abre uma execução com orçamento; grava o início em ``fontes_consumo``."""
    source = catalog.get_source(source_id)  # valida id
    limits = limits_for(source_id, overrides)
    run_id = str(uuid4())
    at = now or _now()
    ensure_state(db_path, source_id, now=at)
    with closing(connect_documents(db_path)) as conn:
        if not is_readable_schema(conn):
            raise ValueError("migração documental pendente")
        last = conn.execute(
            "SELECT MAX(started_at) FROM fontes_consumo WHERE source_id=?",
            (source_id,)).fetchone()
        monthly = conn.execute(
            "SELECT COALESCE(SUM(calls),0) FROM fontes_consumo WHERE source_id=? "
            "AND started_at >= ?", (source_id, _month_start(at))).fetchone()[0]
    if last and last[0]:
        try:
            elapsed = datetime.fromisoformat(at) - datetime.fromisoformat(last[0])
        except ValueError:
            elapsed = None
        minimum = float(source.get("min_interval_hours") or 0)
        if elapsed is not None and minimum and elapsed.total_seconds() < minimum * 3600:
            raise BudgetError("intervalo_minimo",
                              f"{source_id} exige intervalo mínimo de {minimum:g} h")
    monthly_limit = source.get("monthly_limit")
    if monthly_limit is not None and monthly + int(limits["max_calls"]) > int(monthly_limit):
        raise BudgetError("limite_mensal", f"limite mensal de {source_id} atingido")
    with closing(connect_documents(db_path)) as conn, conn:
        conn.execute(
            "INSERT INTO fontes_consumo (id,source_id,run_id,started_at,calls,items,credits,"
            "cost_amount,cost_currency,status,checkpoint_json,limits_json) "
            "VALUES (?,?,?,?,0,0,0,0,?,'em_andamento',NULL,?)",
            (str(uuid4()), source_id, run_id, at, limits["currency"],
             json.dumps(limits, sort_keys=True)))
    return {"version": BUDGET_VERSION, "run_id": run_id, "source_id": source_id,
            "started_at": at, "limits": limits, "used": {"calls": 0, "items": 0,
                                                         "credits": 0.0, "cost": 0.0}}


def _used(db_path, run_id: str) -> dict:
    with closing(connect_documents(db_path)) as conn:
        row = conn.execute(
            "SELECT calls, items, credits, cost_amount FROM fontes_consumo WHERE run_id=?",
            (run_id,)).fetchone()
    if not row:
        raise BudgetError("execucao_inexistente", "execução não encontrada")
    return {"calls": row[0], "items": row[1], "credits": row[2], "cost": row[3]}


def check_call(db_path, run_id: str, *, estimated_items: int = 0,
               estimated_cost: float = 0.0, estimated_credits: float = 0.0) -> dict:
    """Verifica se a próxima chamada cabe no orçamento antes de executá-la."""
    with closing(connect_documents(db_path)) as conn:
        row = conn.execute("SELECT source_id, status, limits_json FROM fontes_consumo "
                           "WHERE run_id=?", (run_id,)).fetchone()
    if not row:
        raise BudgetError("execucao_inexistente", "execução não encontrada")
    if row[1] != "em_andamento":
        raise BudgetError("execucao_encerrada", "execução já encerrada")
    source_id = row[0]
    # Os limites da execução são os gravados na abertura (inclui overrides do operador).
    limits = json.loads(row[2]) if row[2] else limits_for(source_id)
    used = _used(db_path, run_id)
    if used["calls"] + 1 > limits["max_calls"]:
        raise BudgetError("limite_de_chamadas", "limite de chamadas da execução atingido")
    if used["items"] + max(0, int(estimated_items)) > limits["max_items"]:
        raise BudgetError("limite_de_itens", "limite de itens da execução atingido")
    if used["credits"] + max(0.0, float(estimated_credits)) > float(limits["max_credits"]):
        raise BudgetError("limite_de_creditos", "limite de créditos da execução atingido")
    if used["cost"] + max(0.0, float(estimated_cost)) > float(limits["max_cost"]):
        raise BudgetError("limite_de_custo", "limite monetário da execução atingido")
    if estimated_cost > 0:
        require_paid_allowed(source_id, estimated_cost)
    return {"allowed": True, "source_id": source_id, "limits": limits, "used": used}


def record_call(db_path, run_id: str, *, items: int = 0, credits: float = 0.0,
                cost: float = 0.0, success: bool = True) -> dict:
    """Registra o consumo real **dentro** dos limites da execução.

    A atualização é condicional e atômica: se a chamada excederia qualquer limite, nada é
    gravado e ``BudgetError`` é levantado. Falha não cobra (créditos e valor zerados).
    """
    items = max(0, int(items))
    credits = max(0.0, float(credits)) if success else 0.0
    cost = max(0.0, float(cost)) if success else 0.0
    with closing(connect_documents(db_path)) as conn, conn:
        conn.execute("BEGIN IMMEDIATE")
        row = conn.execute(
            "SELECT source_id, limits_json FROM fontes_consumo WHERE run_id=?",
            (run_id,)).fetchone()
        if not row:
            raise BudgetError("execucao_inexistente", "execução não encontrada")
        source_id, limits_json = row
        limits = json.loads(limits_json) if limits_json else limits_for(source_id)
        if cost > 0:
            require_paid_allowed(source_id, cost)
        cursor = conn.execute(
            "UPDATE fontes_consumo SET calls=calls+1, items=items+?, credits=credits+?, "
            "cost_amount=cost_amount+? WHERE run_id=? "
            "AND calls+1 <= ? AND items+? <= ? AND credits+? <= ? AND cost_amount+? <= ?",
            (items, credits, cost, run_id,
             int(limits["max_calls"]), items, int(limits["max_items"]),
             credits, float(limits["max_credits"]), cost, float(limits["max_cost"])))
        if cursor.rowcount != 1:
            raise BudgetError("limite_excedido",
                              "consumo excederia o orçamento da execução; nada foi gravado")
        conn.execute(
            "UPDATE fontes_estado SET calls_total=calls_total+1, "
            "credits_total=credits_total+?, cost_total=cost_total+?, updated_at=? "
            "WHERE source_id=?", (credits, cost, _now(), source_id))
    return _used(db_path, run_id)


def save_checkpoint(db_path, run_id: str, checkpoint: dict) -> None:
    with closing(connect_documents(db_path)) as conn, conn:
        conn.execute("UPDATE fontes_consumo SET checkpoint_json=? WHERE run_id=?",
                     (json.dumps(checkpoint, ensure_ascii=False, sort_keys=True), run_id))


def finish_run(db_path, run_id: str, *, status: str = "concluida",
               notes: str | None = None, now: str | None = None) -> dict:
    if status not in ("concluida", "parcial", "falhou", "interrompida"):
        raise ValueError("estado de execução inválido")
    with closing(connect_documents(db_path)) as conn, conn:
        row = conn.execute("SELECT source_id FROM fontes_consumo WHERE run_id=?",
                           (run_id,)).fetchone()
        if not row:
            raise BudgetError("execucao_inexistente", "execução não encontrada")
        conn.execute("UPDATE fontes_consumo SET finished_at=?, status=?, notes=? "
                     "WHERE run_id=?", (now or _now(), status, notes, run_id))
        conn.execute(
            "UPDATE fontes_estado SET last_run_at=?, last_run_status=?, updated_at=?, "
            "last_error=CASE WHEN ?='falhou' THEN COALESCE(?, last_error) ELSE last_error END "
            "WHERE source_id=?",
            (now or _now(), status, now or _now(), status, notes, row[0]))
    return usage(db_path, run_id)


def usage(db_path, run_id: str) -> dict:
    with closing(connect_documents(db_path)) as conn:
        row = conn.execute(
            "SELECT source_id, started_at, finished_at, calls, items, credits, cost_amount, "
            "cost_currency, status, checkpoint_json, notes FROM fontes_consumo "
            "WHERE run_id=?", (run_id,)).fetchone()
    if not row:
        raise BudgetError("execucao_inexistente", "execução não encontrada")
    return {"version": BUDGET_VERSION, "run_id": run_id, "source_id": row[0],
            "started_at": row[1], "finished_at": row[2], "calls": row[3], "items": row[4],
            "credits": row[5], "cost": row[6], "currency": row[7], "status": row[8],
            "checkpoint": json.loads(row[9]) if row[9] else None, "notes": row[10]}


def ensure_state(db_path, source_id: str, *, enabled: bool = False,
                 now: str | None = None) -> None:
    """Garante uma linha de estado para a fonte (idempotente)."""
    catalog.get_source(source_id)
    with closing(connect_documents(db_path)) as conn, conn:
        conn.execute(
            "INSERT INTO fontes_estado (source_id,enabled,status,updated_at) "
            "VALUES (?,?,?,?) ON CONFLICT(source_id) DO NOTHING",
            (source_id, 1 if enabled else 0, "nao_testada", now or _now()))


_CONFIG_KEY_BY_SOURCE = {
    "guajara": "guajara", "dou-secao-3": "dou", "fgv-conhecimento": "fgv",
    "quadrix": "quadrix", "pci": "pci", "ibfc": "ibfc",
}


def state_report(db_path, *, config: dict | None = None) -> dict:
    """Estado operacional de todas as fontes do catálogo, sem segredos.

    Quando ``config`` é informado, a habilitação efetiva vem da configuração
    (``sources.<chave>.enabled``), não apenas da linha persistida em ``fontes_estado``.
    Sem isso, a interface mostraria todas as fontes desligadas mesmo com o ciclo ativo.
    """
    with closing(connect_documents(db_path)) as conn:
        if not is_readable_schema(conn):
            raise ValueError("migração documental pendente")
        rows = {row[0]: row for row in conn.execute(
            "SELECT source_id, enabled, status, last_run_at, last_error, calls_total, "
            "credits_total, cost_total, cost_currency, updated_at, last_run_status "
            "FROM fontes_estado")}
        last = {row[0]: row[1:] for row in conn.execute(
            "SELECT source_id, calls, items, credits, cost_amount, status, finished_at "
            "FROM fontes_consumo c WHERE started_at = (SELECT MAX(started_at) "
            "FROM fontes_consumo WHERE source_id=c.source_id)")}
    configured = (config or {}).get("sources") or {}
    items = []
    for source in catalog.catalog():
        state = rows.get(source["id"])
        consumo = last.get(source["id"])
        key = _CONFIG_KEY_BY_SOURCE.get(source["id"])
        options = configured.get(key) if key else None
        enabled = (bool(options.get("enabled")) if isinstance(options, dict)
                   else (bool(state[1]) if state else False))
        items.append({
            "id": source["id"], "name": source["name"], "category": source["category"],
            "nature": source["nature"], "access": source["access"],
            "status": source["status"],
            "enabled": enabled,
            "configured": bool(isinstance(options, dict)),
            "min_interval_hours": (options.get("min_interval_hours")
                                   if isinstance(options, dict) else None),
            "runtime_status": state[2] if state else "nao_testada",
            "last_run_at": state[3] if state else None,
            "last_run_status": state[10] if state else None,
            "last_error": state[4] if state else None,
            "calls_total": state[5] if state else 0,
            "credits_total": state[6] if state else 0,
            "cost_total": state[7] if state else 0,
            "currency": (state[8] if state else None) or (source.get("cost") or {}).get("currency"),
            "credential_env": source["credential_env"],
            "persistence": {ctype: source_policy.decision(source["id"], ctype)["permission"]
                            for ctype in source["content"]},
            "connector": source["connector"],
            "last_run": ({"calls": consumo[0], "items": consumo[1], "credits": consumo[2],
                          "cost": consumo[3], "status": consumo[4],
                          "finished_at": consumo[5]} if consumo else None),
            "review_due": source["review_due"],
            "notes": source["notes"],
        })
    return {"version": BUDGET_VERSION, "total": len(items), "items": items,
            "catalogo": catalog.summary(),
            "revisao_vencida": catalog.review_due_sources()}


def consumption_report(db_path, *, source_id: str | None = None, limit: int = 50) -> dict:
    """Consumo por execução, para a visão operacional (sem segredos)."""
    if source_id:
        catalog.get_source(source_id)
    limit = int(limit)
    if limit < 1 or limit > 500:
        raise ValueError("limite fora da faixa")
    with closing(connect_documents(db_path)) as conn:
        if not is_readable_schema(conn):
            raise ValueError("migração documental pendente")
        if source_id:
            rows = conn.execute(
                "SELECT run_id,source_id,started_at,finished_at,calls,items,credits,"
                "cost_amount,cost_currency,status FROM fontes_consumo WHERE source_id=? "
                "ORDER BY started_at DESC, rowid DESC LIMIT ?", (source_id, limit)).fetchall()
        else:
            rows = conn.execute(
                "SELECT run_id,source_id,started_at,finished_at,calls,items,credits,"
                "cost_amount,cost_currency,status FROM fontes_consumo "
                "ORDER BY started_at DESC, rowid DESC LIMIT ?", (limit,)).fetchall()
    return {"version": BUDGET_VERSION, "total": len(rows),
            "itens": [{"run_id": row[0], "source_id": row[1], "started_at": row[2],
                       "finished_at": row[3], "calls": row[4], "items": row[5],
                       "credits": row[6], "cost": row[7], "currency": row[8],
                       "status": row[9]} for row in rows]}
