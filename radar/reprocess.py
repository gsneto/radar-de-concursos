"""Reprocessamento idempotente de documentos já armazenados (Fase 26).

Motivo: os extratores de **local de prova** (novo) e de **conteúdo programático** (corrigido
para texto de PDF sem quebras de linha) precisam rodar sobre editais que já foram analisados.
``record_analysis`` recusa versão já analisada — e deve continuar recusando, porque reescrever
blocos quebraria as evidências existentes.

Este módulo faz o caminho seguro: lê os blocos **já gravados**, gera propostas novas, valida a
citação contra o texto do bloco original e insere somente o que ainda não existe. Nunca apaga,
nunca reescreve, nunca reanalisa.

Idempotência: a chave é ``(contest_id, field_name, value_json, block_id, quote)``. Reexecutar
não duplica proposta nem evidência.
"""

from __future__ import annotations

import json
from contextlib import closing
from datetime import datetime, timezone
from uuid import uuid4

from radar.document_store import connect_documents, is_readable_schema

REPROCESS_VERSION = "reprocess_v1"


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def stored_blocks(conn, version_id: str) -> list[dict]:
    """Blocos já persistidos, na forma que os extratores esperam (com ``block_id``)."""
    return [
        {"block_id": row[0], "page_number": row[1], "locator": row[2],
         "start_offset": row[3], "end_offset": row[4], "text": row[5]}
        for row in conn.execute(
            "SELECT id,page_number,locator,start_offset,end_offset,text FROM blocos_documento "
            "WHERE version_id=? ORDER BY page_number,start_offset,id", (version_id,))]


EXTRACTOR_VERSION = "reprocess_v2"


def propose_for_version(conn, version_id: str) -> list[dict]:
    """Propostas dos extratores atuais sobre os blocos armazenados (sem gravar nada).

    A versão do conjunto de extratores fica registrada no relatório: mudança de
    comportamento é rastreável sem reescrever evidência antiga.
    """
    from radar import exam_location, inline_requirements, program_content, vacancy_aggregate
    from radar.document_fields import LABEL_PREFIX

    row = conn.execute(
        "SELECT d.contest_id, d.role_id FROM versoes_documento v "
        "JOIN documentos d ON d.id=v.document_id WHERE v.id=?", (version_id,)).fetchone()
    if row is None:
        raise ValueError("versão inexistente")
    contest_id, role_id = row
    blocks = stored_blocks(conn, version_id)
    if not blocks:
        return []
    proposals = program_content.extract_program_content(
        blocks, contest_id, label_prefix=LABEL_PREFIX)
    proposals.extend(exam_location.extract_exam_location(
        blocks, contest_id, label_prefix=LABEL_PREFIX))
    # Fase 31: quadro de vagas com total agregado (nunca distribui por modalidade).
    proposals.extend(vacancy_aggregate.parse_aggregate_table(
        blocks, contest_id, label_prefix=LABEL_PREFIX))
    # Fase 31: requisito em texto corrido ("Requisito: ...").
    proposals.extend(inline_requirements.extract_inline_requirements(
        blocks, contest_id, label_prefix=LABEL_PREFIX))
    return proposals


def _existing_keys(conn, contest_id: str) -> set[tuple]:
    keys = set()
    for field_name, value_json, block_id, quote in conn.execute(
            """SELECT p.field_name, p.value_json, e.block_id, e.quote
               FROM propostas_campo p JOIN evidencias e ON e.id=p.evidence_id
               WHERE p.contest_id=?""", (contest_id,)):
        keys.add((field_name, value_json, block_id, quote))
    return keys


def reprocess_version(db_path, version_id: str, *, dry_run=True) -> dict:
    """Acrescenta propostas novas de uma versão já analisada. Idempotente."""
    with closing(connect_documents(db_path)) as conn:
        if not is_readable_schema(conn):
            raise ValueError("migração documental pendente")
        proposals = propose_for_version(conn, version_id)
        if not proposals:
            return {"extractor_version": EXTRACTOR_VERSION, "version": REPROCESS_VERSION, "extractor_version": EXTRACTOR_VERSION,
                    "dry_run": bool(dry_run), "version_id": version_id, "geradas": 0,
                    "novas": 0, "ignoradas": 0, "invalidas": 0, "campos": {}}
        contest_id = conn.execute(
            "SELECT contest_id FROM documentos d JOIN versoes_documento v ON v.document_id=d.id "
            "WHERE v.id=?", (version_id,)).fetchone()[0]
        blocks = {b["block_id"]: b for b in stored_blocks(conn, version_id)}
        existing = _existing_keys(conn, contest_id)
    by_index = [b for b in blocks.values()]
    by_index.sort(key=lambda b: (b["page_number"] or 0, b["start_offset"], b["block_id"]))

    novas, ignoradas, invalidas = [], 0, 0
    for proposal in proposals:
        evidence = proposal["evidence"]
        index = evidence.get("block_index")
        if not isinstance(index, int) or not 0 <= index < len(by_index):
            invalidas += 1
            continue
        block = by_index[index]
        start, end = evidence.get("start_offset"), evidence.get("end_offset")
        quote = evidence.get("quote")
        if not (isinstance(start, int) and isinstance(end, int) and quote
                and 0 <= start < end <= len(block["text"])
                and block["text"][start:end] == quote):
            invalidas += 1
            continue
        if not proposal.get("ambiguity_reason"):
            # Nada pode ser gravado como confirmado: sem motivo declarado, não entra.
            invalidas += 1
            continue
        key = (proposal["field_name"], proposal["value_json"], block["block_id"], quote)
        if key in existing:
            ignoradas += 1
            continue
        existing.add(key)
        novas.append({**proposal, "_block_id": block["block_id"],
                      "_start": start, "_end": end, "_page": block["page_number"],
                      "_locator": block.get("locator")})

    campos = {}
    for item in novas:
        campos[item["field_name"]] = campos.get(item["field_name"], 0) + 1
    report = {"version": REPROCESS_VERSION, "dry_run": bool(dry_run),
              "version_id": version_id, "geradas": len(proposals), "novas": len(novas),
              "ignoradas": ignoradas, "invalidas": invalidas, "campos": campos}
    if dry_run or not novas:
        return report

    with closing(connect_documents(db_path)) as conn:
        try:
            conn.execute("BEGIN IMMEDIATE")
            # Releitura dentro da transação: duas execuções concorrentes não duplicam.
            existing_tx = _existing_keys(conn, novas[0]["contest_id"])
            deduped = []
            for item in novas:
                key = (item["field_name"], item["value_json"], item["_block_id"],
                       item["evidence"]["quote"])
                if key in existing_tx:
                    continue
                existing_tx.add(key)
                deduped.append(item)
            novas = deduped
            for item in novas:
                evidence_id = str(uuid4())
                conn.execute(
                    "INSERT INTO evidencias (id,version_id,block_id,quote,page_number,locator,"
                    "start_offset,end_offset,captured_at) VALUES (?,?,?,?,?,?,?,?,?)",
                    (evidence_id, version_id, item["_block_id"], item["evidence"]["quote"],
                     item["_page"], item.get("_locator"), item["_start"],
                     item["_end"], _now()))
                conn.execute(
                    "INSERT INTO propostas_campo (id,contest_id,role_id,field_name,value_json,"
                    "value_type,evidence_id,extraction_method,ambiguity_reason,extracted_at) "
                    "VALUES (?,?,?,?,?,?,?,?,?,?)",
                    (str(uuid4()), item["contest_id"], item.get("role_id"),
                     item["field_name"], item["value_json"], item.get("value_type", "string"),
                     evidence_id, item.get("extraction_method"), item.get("ambiguity_reason"),
                     _now()))
            conn.commit()
        except BaseException:
            conn.rollback()
            raise
    report["gravadas"] = len(novas)
    return report


def reprocess_editais(db_path, *, dry_run=True, contest_ids=None, limit=None) -> dict:
    """Reprocessa as versões de **edital** já analisadas, de forma idempotente.

    Só considera documentos classificados como edital (abertura/retificado) — nunca páginas de
    agregador, resultado, convocação ou homologação.
    """
    allowed = {str(c) for c in contest_ids} if contest_ids else None
    with closing(connect_documents(db_path)) as conn:
        if not is_readable_schema(conn):
            raise ValueError("migração documental pendente")
        rows = conn.execute(
            """SELECT d.contest_id, v.id, d.title FROM documentos d
               JOIN versoes_documento v ON v.document_id=d.id
               WHERE (d.kind='edital' OR d.tipo_documental IN
                      ('edital_abertura','edital_retificado'))
                 AND COALESCE(d.tipo_documental,'') NOT IN
                     ('pagina_agregador','pagina_banca','pagina_orgao')
                 AND v.extraction_state IN ('parcial','concluida')
               ORDER BY d.contest_id, v.fetched_at DESC, d.id, v.id""").fetchall()
    seen_contest = set()
    targets = []
    for contest_id, version_id, title in rows:
        if allowed is not None and contest_id not in allowed:
            continue
        if contest_id in seen_contest:
            continue
        seen_contest.add(contest_id)
        targets.append((contest_id, version_id, title))
    if limit:
        targets = targets[:int(limit)]

    reports, total_novas, campos = [], 0, {}
    for contest_id, version_id, title in targets:
        result = reprocess_version(db_path, version_id, dry_run=dry_run)
        total_novas += result["novas"]
        for name, count in result["campos"].items():
            campos[name] = campos.get(name, 0) + count
        reports.append({"contest_id": contest_id, "version_id": version_id,
                        "title": title, "novas": result["novas"],
                        "ignoradas": result["ignoradas"], "invalidas": result["invalidas"]})
    return {"extractor_version": EXTRACTOR_VERSION, "version": REPROCESS_VERSION, "dry_run": bool(dry_run),
            "concursos": len(targets), "propostas_novas": total_novas, "campos": campos,
            "detalhe": reports}
