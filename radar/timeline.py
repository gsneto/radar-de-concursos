"""Linha do tempo das mudanças da base (Fase 34).

O ciclo agendado do Windows altera a base enquanto o operador trabalha. Este módulo mostra
**o que mudou desde um instante de referência**, sem criar uma segunda contabilidade:

- ciclos: ``ciclos_monitoramento`` + ``ciclos_fontes`` (a mesma tabela que o monitoramento
  grava);
- eventos: ``eventos_documentais`` (descoberta, download, análise, falha, revisão);
- versões e propostas: timestamps reais (``fetched_at``, ``extracted_at``);
- pendências: documentos nominais sem conteúdo e falhas de fonte.

Atribuição de documentos a um ciclo é **por janela de tempo** (início/fim do ciclo). Isso é
o que os dados permitem provar: um documento descoberto fora de qualquer janela é
"fora de ciclo" (execução manual), não "do ciclo". Nenhuma contagem é estimada.
"""

from __future__ import annotations

from contextlib import closing
from datetime import datetime, timezone

from radar.document_store import connect_documents, is_readable_schema

TIMELINE_VERSION = "timeline_v1"


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _parse(value):
    if not isinstance(value, str):
        return None
    try:
        return datetime.fromisoformat(value)
    except ValueError:
        return None


def timeline(db_path, *, since=None, limit=200) -> dict:
    """Mudanças desde ``since`` (ISO). Sem ``since``, usa as últimas 24 horas."""
    limit = int(limit)
    if limit < 1 or limit > 1000:
        raise ValueError("limite fora da faixa")
    now_dt = datetime.now(timezone.utc)
    if since:
        start = _parse(since)
        if start is None:
            raise ValueError("data de referência inválida")
        # Comparações são de string ISO: normalizar para UTC evita que o mesmo instante
        # expresso com outro fuso produza contagens diferentes.
        if start.tzinfo is None:
            start = start.replace(tzinfo=timezone.utc)
        start = start.astimezone(timezone.utc)
    else:
        start = datetime.fromtimestamp(now_dt.timestamp() - 86400, tz=timezone.utc)
    since_iso = start.isoformat()

    with closing(connect_documents(db_path)) as conn:
        if not is_readable_schema(conn):
            raise ValueError("migração documental pendente")
        cycles = [{"cycle_id": row[0], "started_at": row[1], "finished_at": row[2],
                   "state": row[3], "documents_found": row[4], "documents_new": row[5],
                   "versions_new": row[6], "changes_pending": row[7]}
                  for row in conn.execute(
                      "SELECT id, started_at, finished_at, state, documents_found,"
                      " documents_new, versions_new, changes_pending "
                      "FROM ciclos_monitoramento "
                      "WHERE started_at <= ? AND (finished_at IS NULL OR finished_at >= ?) "
                      "ORDER BY started_at", (now_dt.isoformat(), since_iso))]
        sources_by_cycle = {}
        for cycle_id, source_url, state, new, versions, error in conn.execute(
                "SELECT cycle_id, source_url, state, documents_new, versions_new, error_code "
                "FROM ciclos_fontes WHERE cycle_id IN ("
                " SELECT id FROM ciclos_monitoramento WHERE started_at <= ? "
                " AND (finished_at IS NULL OR finished_at >= ?)) "
                "ORDER BY cycle_id, source_url", (now_dt.isoformat(), since_iso)):
            sources_by_cycle.setdefault(cycle_id, []).append(
                {"source_url": source_url, "state": state, "documents_new": new,
                 "versions_new": versions, "error_code": error})

        # Snapshot do que já existia antes da referência (por timestamp real).
        baseline = {
            "documentos": conn.execute(
                "SELECT COUNT(*) FROM documentos WHERE discovered_at < ?",
                (since_iso,)).fetchone()[0],
            "versoes": conn.execute(
                "SELECT COUNT(*) FROM versoes_documento WHERE fetched_at < ?",
                (since_iso,)).fetchone()[0],
            "propostas": conn.execute(
                "SELECT COUNT(*) FROM propostas_campo WHERE extracted_at < ?",
                (since_iso,)).fetchone()[0],
            "revisoes": conn.execute(
                "SELECT COUNT(*) FROM revisoes_campo WHERE reviewed_at < ?",
                (since_iso,)).fetchone()[0],
        }
        novos = {
            "documentos": conn.execute(
                "SELECT COUNT(*) FROM documentos WHERE discovered_at >= ?",
                (since_iso,)).fetchone()[0],
            "versoes": conn.execute(
                "SELECT COUNT(*) FROM versoes_documento WHERE fetched_at >= ?",
                (since_iso,)).fetchone()[0],
            "propostas": conn.execute(
                "SELECT COUNT(*) FROM propostas_campo WHERE extracted_at >= ?",
                (since_iso,)).fetchone()[0],
            "revisoes": conn.execute(
                "SELECT COUNT(*) FROM revisoes_campo WHERE reviewed_at >= ?",
                (since_iso,)).fetchone()[0],
        }
        events = {}
        for event_type, count in conn.execute(
                "SELECT event_type, COUNT(*) FROM eventos_documentais "
                "WHERE occurred_at >= ? GROUP BY event_type ORDER BY 2 DESC", (since_iso,)):
            events[event_type] = count
        discovered = [{"document_id": row[0], "contest_id": row[1], "title": row[2],
                       "tipo_documental": row[3], "issuer": row[4],
                       "discovered_at": row[5]}
                      for row in conn.execute(
                          "SELECT id, contest_id, title, tipo_documental, issuer, discovered_at "
                          "FROM documentos WHERE discovered_at >= ? "
                          "ORDER BY discovered_at DESC LIMIT ?", (since_iso, limit))]
        failures = [{"source_url": row[0], "state": row[1], "error_code": row[2],
                     "checked_at": row[3]}
                    for row in conn.execute(
                        "SELECT source_url, state, error_code, checked_at FROM ciclos_fontes "
                        "WHERE state='falhou' AND checked_at >= ? "
                        "ORDER BY checked_at DESC LIMIT ?", (since_iso, limit))]
        nominal_pending = conn.execute(
            "SELECT COUNT(*) FROM documentos d WHERE NOT EXISTS ("
            " SELECT 1 FROM versoes_documento v WHERE v.document_id=d.id)").fetchone()[0]

    for cycle in cycles:
        cycle["fontes"] = sources_by_cycle.get(cycle["cycle_id"], [])

    windows = [(cycle["started_at"], cycle["finished_at"] or now_dt.isoformat(),
                cycle["cycle_id"]) for cycle in cycles]
    for document in discovered:
        document["atribuicao"] = "fora_de_ciclo"
        for start_at, end_at, cycle_id in windows:
            if start_at <= (document["discovered_at"] or "") <= end_at:
                # Ciclo que começou antes da referência ainda explica o documento; chamar de
                # "execução manual" seria falso.
                document["atribuicao"] = (
                    "ciclo_agendado" if start_at >= since_iso
                    else "ciclo_anterior_a_referencia")
                document["cycle_id"] = cycle_id
                break

    return {
        "version": TIMELINE_VERSION, "generated_at": now_dt.isoformat(),
        "referencia": {"desde": since_iso, "ate": now_dt.isoformat()},
        "snapshot_anterior": baseline,
        "novos": novos,
        "eventos": events,
        "ciclos": cycles,
        "documentos_descobertos": discovered,
        "falhas_de_fonte": failures,
        "documentos_sem_conteudo": nominal_pending,
        "limitacao": ("Atribuição de documento a ciclo é por janela de tempo (início/fim), "
                      "não por evento individual: o que está fora de qualquer janela é "
                      "execução manual. Contagens vêm das tabelas do monitoramento, não de "
                      "uma contabilidade paralela."),
    }
