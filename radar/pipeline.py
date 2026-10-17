"""Pipeline documental end-to-end: estado por documento, cobertura e reprocessamento.

Este módulo **não** cria um segundo fluxo de extração. Ele:

- audita o caminho real de cada documento (descoberto → baixado → validado → registrado →
  identidade → concurso → classificado → extraído → blocos → propostas → revisão);
- pré-visualiza a extração sem gravar nada (``dry_run``);
- executa a extração controlada reaproveitando ``monitoring._analyze_version``;
- mede cobertura por concurso com denominadores explícitos, sem agrupar estados distintos.

Nenhuma etapa confirma campo: proposta é candidata até decisão humana registrada.
"""

from __future__ import annotations

import hashlib
import json
from contextlib import closing
from datetime import datetime, timezone
from pathlib import Path

from radar.document_store import connect_documents, is_readable_schema

PIPELINE_VERSION = "pipeline_v1"

# Estados de documento, do mais inicial ao mais completo. Um documento pode estar em mais de
# uma etapa concluída; o estado "efetivo" é o primeiro bloqueio.
DOCUMENT_STAGES = ("descoberto", "baixado", "validado", "classificado", "extraido",
                   "propostas", "revisavel")

DECISIVE_FIELDS = ("immediate_vacancies", "indigenous_vacancies",
                   "indigenous_reserve_vacancies", "education", "si_compatibility",
                   "exam_location", "registration_end", "exemption_end")

# Motivos de "não extraído", distintos entre si de propósito.
NOT_EXTRACTED_REASONS = {
    "nao_iniciada": "versão registrada, extração ainda não executada",
    "falhou": "extração falhou (ver código)",
    "sem_texto": "PDF sem texto extraível (provável digitalização) — exige OCR",
    "paginas_excedidas": "PDF acima do limite de páginas — extração limitada ao prefixo",
    "sem_versao": "documento registrado, nenhum byte obtido",
}


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _artifact(db_path, digest: str, relative_path: str) -> Path:
    root = Path(db_path).resolve().parent / (Path(db_path).name + ".documents")
    artifact = (Path(db_path).resolve().parent / relative_path).resolve()
    if artifact.parent != root.resolve() or artifact.name != digest:
        raise ValueError("caminho de artefato inválido")
    return artifact


def document_stage(row) -> dict:
    """Classifica um documento pelas etapas concluídas e pelo primeiro bloqueio real.

    ``blocked_at`` distingue "nunca tentado" de "tentado e falhou", usando o estado e o
    ``error_code`` da versão mais recente — nunca presume sucesso nem fracasso.
    """
    (document_id, contest_id, title, official_url, tipo, kind, issuer,
     source_identifier, versions, extracted_versions, blocks, proposals,
     association_state, contest_state, last_state, last_error) = row
    done = {"descoberto"}
    if versions:
        done.add("baixado")
    if tipo:
        done.add("classificado")
    if extracted_versions:
        done.add("extraido")
    if blocks:
        done.add("validado")
    if proposals:
        done.add("propostas")
    review_ready = bool(proposals) and association_state in ("confirmada", None)
    if review_ready:
        done.add("revisavel")
    stages = [stage for stage in DOCUMENT_STAGES if stage in done]
    blocked = None
    motivo = None
    if not versions:
        blocked, motivo = "sem_versao", NOT_EXTRACTED_REASONS["sem_versao"]
    elif not extracted_versions:
        if last_state == "falhou" and last_error == "pdf_sem_texto":
            blocked, motivo = "sem_texto", NOT_EXTRACTED_REASONS["sem_texto"]
        elif last_state == "falhou" and last_error == "pdf_paginas_excedidas":
            blocked, motivo = "paginas_excedidas", NOT_EXTRACTED_REASONS["paginas_excedidas"]
        elif last_state == "falhou":
            blocked, motivo = "falhou", NOT_EXTRACTED_REASONS["falhou"]
        else:
            blocked, motivo = "nao_iniciada", NOT_EXTRACTED_REASONS["nao_iniciada"]
    elif not proposals:
        blocked = "sem_propostas"
    elif not review_ready:
        blocked = "associacao_pendente"
    if blocked and blocked not in ("sem_propostas", "associacao_pendente"):
        stages = [stage for stage in stages if stage not in ("extraido", "validado",
                                                             "propostas", "revisavel")]
    return {
        "document_id": document_id,
        "contest_id": contest_id,
        "title": title,
        "official_url": official_url,
        "tipo_documental": tipo,
        "kind": kind,
        "issuer": issuer,
        "source_identifier": source_identifier,
        "stages": stages,
        "versions": versions,
        "extracted_versions": extracted_versions,
        "blocks": blocks,
        "proposals": proposals,
        "association_state": association_state,
        "contest_state": contest_state,
        "blocked_at": blocked,
        "blocked_reason": motivo,
        "last_extraction_state": last_state,
        "last_extraction_error": last_error,
        "review_ready": review_ready,
    }


def audit_documents(db_path, *, contest_id=None, document_id=None, limit=1000,
                    only_pending=False) -> dict:
    """Auditoria por documento. Somente leitura."""
    limit = int(limit)
    if limit < 1 or limit > 5000:
        raise ValueError("limite fora da faixa")
    with closing(connect_documents(db_path)) as conn:
        if not is_readable_schema(conn):
            raise ValueError("migração documental pendente")
        rows = conn.execute("""
            SELECT d.id, d.contest_id, d.title, d.official_url, d.tipo_documental, d.kind,
                   d.issuer, d.source_identifier,
                   (SELECT COUNT(*) FROM versoes_documento v WHERE v.document_id=d.id),
                   (SELECT COUNT(*) FROM versoes_documento v WHERE v.document_id=d.id
                     AND v.extraction_state IN ('parcial','concluida')),
                   (SELECT COUNT(*) FROM blocos_documento b
                     JOIN versoes_documento v ON v.id=b.version_id
                    WHERE v.document_id=d.id),
                   (SELECT COUNT(*) FROM propostas_campo p
                     JOIN evidencias e ON e.id=p.evidence_id
                     JOIN versoes_documento v ON v.id=e.version_id
                    WHERE v.document_id=d.id),
                   (SELECT a.state FROM associacoes_documento a WHERE a.document_id=d.id
                     ORDER BY a.decided_at DESC, a.rowid DESC LIMIT 1),
                   (SELECT c.estado_identidade FROM concursos_identidade c
                     WHERE c.id=d.contest_id),
                   (SELECT v.extraction_state FROM versoes_documento v
                     WHERE v.document_id=d.id
                     ORDER BY v.fetched_at DESC, v.rowid DESC LIMIT 1),
                   (SELECT v.error_code FROM versoes_documento v
                     WHERE v.document_id=d.id
                     ORDER BY v.fetched_at DESC, v.rowid DESC LIMIT 1)
            FROM documentos d
            WHERE (? IS NULL OR d.contest_id=?) AND (? IS NULL OR d.id=?)
            ORDER BY d.contest_id, d.title, d.id""",
            (contest_id, contest_id, document_id, document_id)).fetchall()
        failures = {}
        for row in conn.execute(
                "SELECT v.document_id, v.error_code FROM versoes_documento v "
                "WHERE v.extraction_state='falhou'"):
            failures.setdefault(row[0], []).append(row[1])
    items = []
    for row in rows:
        item = document_stage(row)
        item["extraction_errors"] = failures.get(item["document_id"], [])
        if only_pending and item["review_ready"]:
            continue
        items.append(item)
    counts = {}
    for item in items:
        key = "pronto_para_revisao" if item["review_ready"] else (
            item["blocked_at"] or "indefinido")
        counts[key] = counts.get(key, 0) + 1
    return {"version": PIPELINE_VERSION, "generated_at": _now(), "total": len(items),
            "returned": len(items[:limit]), "truncated": len(items) > limit,
            "por_bloqueio": counts, "itens": items[:limit],
            "limitacao": ("Documento baixado não é documento extraído; documento extraído "
                          "não é campo confirmado. Nenhuma etapa aprova dado.")}


def preview_analysis(db_path, version_id: str) -> dict:
    """Simula a extração de uma versão sem gravar nada (nem blocos, nem propostas)."""
    from radar.document_extract import ExtractionError, extract_document
    from radar.document_fields import extract_field_proposals
    from radar.monitoring import PREFIX_PAGES

    with closing(connect_documents(db_path)) as conn:
        if not is_readable_schema(conn):
            raise ValueError("migração documental pendente")
        row = conn.execute(
            "SELECT v.sha256, v.local_path, v.content_type, d.contest_id, d.role_id, "
            "d.title, (SELECT COUNT(*) FROM blocos_documento b WHERE b.version_id=v.id) "
            "FROM versoes_documento v JOIN documentos d ON d.id=v.document_id WHERE v.id=?",
            (version_id,)).fetchone()
    if not row:
        raise ValueError("versão inexistente")
    digest, relative_path, content_type, contest_id, role_id, title, blocks_existing = row
    if blocks_existing:
        return {"version": PIPELINE_VERSION, "version_id": version_id, "ja_analisada": True,
                "title": title, "would_write": False}
    artifact = _artifact(db_path, digest, relative_path)
    content = artifact.read_bytes()
    if hashlib.sha256(content).hexdigest() != digest:
        raise ValueError("hash de artefato divergente")
    try:
        extracted = extract_document(content, content_type, prefix_pages=PREFIX_PAGES)
    except ExtractionError as error:
        return {"version": PIPELINE_VERSION, "version_id": version_id, "title": title,
                "would_write": False, "error_code": error.code,
                "error": str(error), "would_blocks": 0, "would_proposals": 0}
    blocks = extracted["blocks"]
    proposals = extract_field_proposals(blocks, version_id, contest_id, role_id)
    invalid = 0
    for proposal in proposals:
        evidence = proposal["evidence"]
        block = blocks[evidence["block_index"]]
        start, end = evidence["start_offset"], evidence["end_offset"]
        if not (0 <= start < end <= len(block["text"])
                and block["text"][start:end] == evidence["quote"]):
            invalid += 1
    return {"version": PIPELINE_VERSION, "version_id": version_id, "title": title,
            "ja_analisada": False, "would_write": invalid == 0,
            "would_blocks": len(blocks), "would_proposals": len(proposals),
            "citacoes_invalidas": invalid, "truncated": extracted["truncated"],
            "total_pages": extracted["total_pages"],
            "limitation": extracted["limitation"],
            "extractor_version": extracted["extractor_version"],
            "fields": sorted({p["field_name"] for p in proposals})}


PERMANENT_BLOCK_CODES = ("pdf_sem_texto",)


def pending_versions(db_path, *, contest_id=None, document_id=None, limit=200,
                     include_blocked=False) -> list[dict]:
    """Versões baixadas que ainda não foram extraídas (mais antigas primeiro).

    Por padrão exclui falhas permanentes (PDF sem texto): repetir não muda o resultado até
    existir OCR. ``include_blocked=True`` lista também esses casos para inspeção.
    """
    limit = int(limit)
    if limit < 1 or limit > 2000:
        raise ValueError("limite fora da faixa")
    with closing(connect_documents(db_path)) as conn:
        if not is_readable_schema(conn):
            raise ValueError("migração documental pendente")
        rows = conn.execute("""
            SELECT v.id, v.document_id, d.title, v.content_type, v.byte_size, v.fetched_at,
                   d.contest_id, v.extraction_state, v.error_code
            FROM versoes_documento v JOIN documentos d ON d.id=v.document_id
            WHERE NOT EXISTS (SELECT 1 FROM blocos_documento b WHERE b.version_id=v.id)
              AND (? IS NULL OR d.contest_id=?) AND (? IS NULL OR d.id=?)
              AND (? OR v.error_code IS NULL OR v.error_code NOT IN (%s))
            ORDER BY v.fetched_at, v.id LIMIT ?""" % ",".join("?" for _ in PERMANENT_BLOCK_CODES),
            (contest_id, contest_id, document_id, document_id, include_blocked,
             *PERMANENT_BLOCK_CODES, limit)).fetchall()
    return [{"version_id": row[0], "document_id": row[1], "title": row[2],
             "content_type": row[3], "byte_size": row[4], "fetched_at": row[5],
             "contest_id": row[6], "extraction_state": row[7], "error_code": row[8]}
            for row in rows]


def analyze_versions(db_path, version_ids, *, dry_run=True, limit=None) -> dict:
    """Extrai versões em série, com limite. ``dry_run`` só pré-visualiza."""
    ids = list(version_ids)
    if limit is not None:
        ids = ids[:max(0, int(limit))]
    report = {"version": PIPELINE_VERSION, "dry_run": bool(dry_run), "total": len(ids),
              "extraidas": 0, "falhas": [], "ja_analisadas": 0, "previa": []}
    if dry_run:
        for version_id in ids:
            try:
                report["previa"].append(preview_analysis(db_path, version_id))
            except Exception as error:
                report["falhas"].append({"version_id": version_id,
                                         "code": getattr(error, "code",
                                                         type(error).__name__)})
        report["extraidas"] = sum(1 for item in report["previa"] if item.get("would_write"))
        # Erros de prévia não podem apagar os erros de versão inválida coletados no laço.
        report["falhas"].extend(
            {"version_id": item["version_id"], "code": item.get("error_code")}
            for item in report["previa"] if item.get("error_code"))
        report["ja_analisadas"] = sum(1 for item in report["previa"]
                                      if item.get("ja_analisada"))
        return report
    from radar.monitoring import _analyze_version
    for version_id in ids:
        with closing(connect_documents(db_path)) as conn:
            existing = conn.execute(
                "SELECT COUNT(*) FROM blocos_documento WHERE version_id=?",
                (version_id,)).fetchone()[0]
        if existing:
            report["ja_analisadas"] += 1
            continue
        try:
            _analyze_version(db_path, version_id)
        except Exception as error:  # falha isolada não interrompe o lote
            report["falhas"].append({"version_id": version_id,
                                     "code": getattr(error, "code", type(error).__name__)})
            continue
        with closing(connect_documents(db_path)) as conn:
            written = conn.execute(
                "SELECT COUNT(*) FROM blocos_documento WHERE version_id=?",
                (version_id,)).fetchone()[0]
        if written:
            report["extraidas"] += 1
        else:
            with closing(connect_documents(db_path)) as conn:
                code = conn.execute(
                    "SELECT error_code FROM versoes_documento WHERE id=?",
                    (version_id,)).fetchone()
            report["falhas"].append({"version_id": version_id,
                                     "code": code[0] if code else "sem_blocos"})
    return report


def contest_coverage(db_path, *, limit=500) -> dict:
    """Cobertura por concurso com as categorias distintas (nunca um "sem dados" genérico)."""
    limit = int(limit)
    if limit < 1 or limit > 5000:
        raise ValueError("limite fora da faixa")
    with closing(connect_documents(db_path)) as conn:
        if not is_readable_schema(conn):
            raise ValueError("migração documental pendente")
        contests = conn.execute(
            "SELECT id, estado_identidade FROM concursos_identidade "
            "WHERE estado_identidade='certame' ORDER BY id LIMIT ?", (limit,)).fetchall()
        data = {}
        for contest_id, *_ in contests:
            data[contest_id] = {
                "documentos": 0, "oficiais": 0, "edital": 0, "retificacao": 0,
                "com_texto": 0, "com_blocos": 0, "com_propostas": 0,
                "campos_decisivos": set(), "falhas": 0, "sem_texto": 0,
                "paginas_excedidas": 0, "associacao_pendente": 0, "ultima": None,
            }
        for row in conn.execute("""
                SELECT d.contest_id, d.id, d.tipo_documental, d.official_url, d.discovered_at,
                       (SELECT COUNT(*) FROM versoes_documento v WHERE v.document_id=d.id
                         AND v.extraction_state IN ('parcial','concluida')),
                       (SELECT COUNT(*) FROM versoes_documento v WHERE v.document_id=d.id
                         AND v.error_code='pdf_sem_texto'),
                       (SELECT COUNT(*) FROM eventos_documentais ev
                          JOIN versoes_documento v ON v.id=ev.version_id
                         WHERE v.document_id=d.id AND ev.event_type='analise'
                           AND json_extract(ev.note, '$.truncated') = 1),
                       (SELECT COUNT(*) FROM blocos_documento b
                         JOIN versoes_documento v ON v.id=b.version_id
                        WHERE v.document_id=d.id),
                       (SELECT a.state FROM associacoes_documento a
                         WHERE a.document_id=d.id
                         ORDER BY a.decided_at DESC, a.rowid DESC LIMIT 1)
                FROM documentos d WHERE d.contest_id IN
                  (SELECT id FROM concursos_identidade WHERE estado_identidade='certame')
                ORDER BY d.discovered_at"""):
            entry = data.get(row[0])
            if entry is None:
                continue
            entry["documentos"] += 1
            if row[3] and "pciconcursos" not in (row[3] or ""):
                entry["oficiais"] += 1
            tipo = row[2] or ""
            if tipo in ("edital_abertura", "edital_retificado"):
                entry["edital"] += 1
            if tipo in ("retificacao", "edital_retificado"):
                entry["retificacao"] += 1
            if row[5]:
                entry["com_texto"] += 1
            if row[8]:
                entry["com_blocos"] += 1
            entry["falhas"] += row[6]
            entry["sem_texto"] += row[6]
            entry["paginas_excedidas"] += row[7]
            if row[9] == "pendente":
                entry["associacao_pendente"] += 1
            if entry["ultima"] is None or (row[4] or "") > entry["ultima"]:
                entry["ultima"] = row[4]
        for row in conn.execute("""
                SELECT p.contest_id, p.field_name, COUNT(*) FROM propostas_campo p
                JOIN concursos_identidade c ON c.id=p.contest_id
                WHERE c.estado_identidade='certame'
                GROUP BY p.contest_id, p.field_name"""):
            entry = data.get(row[0])
            if entry is None:
                continue
            entry["propostas_total"] = entry.get("propostas_total", 0) + row[2]
            entry["campos_com_proposta"] = entry.get("campos_com_proposta", 0) + 1
            if row[1] in DECISIVE_FIELDS:
                entry["campos_decisivos"].add(row[1])
        confirmed = {}
        for contest_id, field in conn.execute(
                "SELECT contest_id, field_name FROM valores_atuais"):
            confirmed.setdefault(contest_id, set()).add(field)

    items = []
    totals = {}
    for contest_id, entry in data.items():
        # Classificação explícita: a categoria mais restritiva que descreve o concurso.
        if entry["documentos"] == 0:
            category = "sem_documento"
        elif entry["com_blocos"] == 0 and entry["sem_texto"]:
            category = "documento_sem_texto"
        elif entry["com_blocos"] == 0:
            category = "documento_nao_extraido"
        elif not entry.get("campos_com_proposta"):
            category = "texto_sem_campo"
        elif entry["campos_decisivos"]:
            category = "campo_candidato"
        else:
            category = "proposta_sem_campo_decisivo"
        if contest_id in confirmed and confirmed[contest_id]:
            category = "campo_confirmado"
        totals[category] = totals.get(category, 0) + 1
        items.append({
            "contest_id": contest_id,
            "categoria": category,
            "documentos": entry["documentos"],
            "documentos_oficiais": entry["oficiais"],
            "edital_principal": entry["edital"],
            "retificacoes": entry["retificacao"],
            "documentos_com_texto": entry["com_texto"],
            "documentos_com_blocos": entry["com_blocos"],
            "propostas": entry.get("propostas_total", 0),
            "campos_com_proposta": entry.get("campos_com_proposta", 0),
            "campos_decisivos": sorted(entry["campos_decisivos"]),
            "campos_confirmados": sorted(confirmed.get(contest_id, ())),
            "falhas_extracao": entry["falhas"],
            "sem_texto": entry["sem_texto"],
            "paginas_excedidas": entry["paginas_excedidas"],
            "associacao_pendente": entry["associacao_pendente"],
            "ultima_descoberta": entry["ultima"],
        })
    items.sort(key=lambda item: (item["categoria"], item["contest_id"]))
    return {"version": PIPELINE_VERSION, "generated_at": _now(),
            "concursos": len(items), "por_categoria": totals, "itens": items,
            "limitacao": ("Categorias são exclusivas e explícitas: ausência de campo não é "
                          "zero nem resposta negativa; campo candidato não é confirmado.")}


def duplicate_report(db_path, *, limit=100) -> dict:
    """Duplicidades existentes (somente leitura) para revisão — nunca apagadas sozinhas.

    Uma proposta duplicada é a mesma evidência, o mesmo escopo e o mesmo valor. O histórico
    não é removido: o relatório existe para decisão humana.
    """
    limit = int(limit)
    if limit < 1 or limit > 1000:
        raise ValueError("limite fora da faixa")
    with closing(connect_documents(db_path)) as conn:
        if not is_readable_schema(conn):
            raise ValueError("migração documental pendente")
        rows = conn.execute("""
            SELECT p.contest_id, p.role_id, p.field_name, p.value_json, e.block_id, e.quote,
                   COUNT(*) AS n, MIN(p.id) AS representative
            FROM propostas_campo p JOIN evidencias e ON e.id=p.evidence_id
            GROUP BY 1,2,3,4,5,6 HAVING n > 1
            ORDER BY n DESC, p.field_name LIMIT ?""", (limit,)).fetchall()
        duplicated_docs = conn.execute("""
            SELECT COUNT(*) FROM (SELECT contest_id, official_url FROM documentos
                                  GROUP BY 1,2 HAVING COUNT(*) > 1)""").fetchone()[0]
        duplicated_versions = conn.execute("""
            SELECT COUNT(*) FROM (SELECT document_id, sha256 FROM versoes_documento
                                  GROUP BY 1,2 HAVING COUNT(*) > 1)""").fetchone()[0]
    items = [{"contest_id": row[0], "role_id": row[1], "field_name": row[2],
              "value": row[3], "quote": (row[5] or "")[:120], "ocorrencias": row[6],
              "proposta_representante": row[7]} for row in rows]
    return {"version": PIPELINE_VERSION, "grupos": len(items),
            "propostas_excedentes": sum(item["ocorrencias"] - 1 for item in items),
            "documentos_url_repetida": duplicated_docs,
            "versoes_hash_repetido": duplicated_versions,
            "itens": items,
            "limitacao": ("Duplicidade histórica não é apagada automaticamente: o relatório "
                          "serve para decisão humana. Novas extrações não criam duplicatas "
                          "idênticas dentro da mesma versão.")}


def pipeline_summary(db_path) -> dict:
    """Indicadores globais com denominadores explícitos."""
    audit = audit_documents(db_path, limit=5000)
    coverage = contest_coverage(db_path, limit=5000)
    with closing(connect_documents(db_path)) as conn:
        if not is_readable_schema(conn):
            raise ValueError("migração documental pendente")
        total_contests = conn.execute(
            "SELECT COUNT(*) FROM concursos_identidade WHERE estado_identidade='certame'"
        ).fetchone()[0]
        docs = conn.execute("SELECT COUNT(*) FROM documentos").fetchone()[0]
        versions = conn.execute("SELECT COUNT(*) FROM versoes_documento").fetchone()[0]
        extracted = conn.execute(
            "SELECT COUNT(DISTINCT version_id) FROM blocos_documento").fetchone()[0]
        proposals = conn.execute("SELECT COUNT(*) FROM propostas_campo").fetchone()[0]
        evidences = conn.execute("SELECT COUNT(*) FROM evidencias").fetchone()[0]
        reviews = conn.execute("SELECT COUNT(*) FROM revisoes_campo").fetchone()[0]
        confirmed = conn.execute("SELECT COUNT(*) FROM valores_atuais").fetchone()[0]
        sem_texto = conn.execute(
            "SELECT COUNT(*) FROM versoes_documento WHERE error_code='pdf_sem_texto'"
        ).fetchone()[0]
        paginas = conn.execute(
            "SELECT COUNT(DISTINCT v.id) FROM versoes_documento v "
            "JOIN eventos_documentais ev ON ev.version_id=v.id "
            "WHERE ev.event_type='analise' AND json_extract(ev.note, '$.truncated') = 1"
        ).fetchone()[0]
        failures = conn.execute(
            "SELECT error_code, COUNT(*) FROM versoes_documento "
            "WHERE extraction_state='falhou' GROUP BY error_code").fetchall()
        duplicates = conn.execute("""
            SELECT COUNT(*) FROM (
              SELECT d.id FROM documentos d
              GROUP BY d.contest_id, d.official_url HAVING COUNT(*) > 1)""").fetchone()[0]
        with_text = conn.execute(
            "SELECT COUNT(*) FROM documentos d WHERE EXISTS ("
            " SELECT 1 FROM versoes_documento v JOIN blocos_documento b ON b.version_id=v.id"
            " WHERE v.document_id=d.id)").fetchone()[0]
        duplicate_proposals = conn.execute("""
            SELECT COALESCE(SUM(n - 1), 0) FROM (
              SELECT COUNT(*) n FROM propostas_campo p
              JOIN evidencias e ON e.id=p.evidence_id
              GROUP BY p.contest_id,p.role_id,p.field_name,p.value_json,e.block_id,e.quote
              HAVING n > 1)""").fetchone()[0]
    def pct(part, whole):
        return round(100.0 * part / whole, 1) if whole else None
    return {
        "version": PIPELINE_VERSION, "generated_at": _now(),
        "concursos": total_contests,
        "concursos_com_documento": coverage["concursos"] - coverage["por_categoria"].get(
            "sem_documento", 0),
        "concursos_com_edital": sum(1 for item in coverage["itens"]
                                    if item["edital_principal"] > 0),
        "documentos": docs,
        "documentos_com_texto": with_text,
        "versoes": versions,
        "versoes_extraidas": extracted,
        "propostas": proposals,
        "evidencias": evidences,
        "revisoes_humanas": reviews,
        "campos_confirmados": confirmed,
        "falhas_por_codigo": {code: count for code, count in failures},
        "sem_texto": sem_texto,
        "paginas_excedidas": paginas,
        "duplicidades_detectadas": duplicates,
        "duplicidades_propostas": duplicate_proposals,
        "cobertura": {
            "documentos_com_texto_pct": pct(with_text, docs),
            "versoes_extraidas_pct": pct(extracted, versions),
            "concursos_com_documento_pct": pct(
                coverage["concursos"] - coverage["por_categoria"].get("sem_documento", 0),
                total_contests),
            "concursos_com_edital_pct": pct(
                sum(1 for item in coverage["itens"] if item["edital_principal"] > 0),
                total_contests),
        },
        "documentos_por_bloqueio": audit["por_bloqueio"],
        "concursos_por_categoria": coverage["por_categoria"],
        "limitacao": ("Percentuais usam o denominador indicado. Proposta não é campo "
                      "confirmado; revisões humanas e valores vigentes são contados à parte."),
    }
