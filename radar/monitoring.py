"""Executa um ciclo de monitoramento das fontes oficiais autorizadas.

O ciclo é único e termina: consulta a página de descoberta, registra documentos
novos, baixa/compara os conhecidos, classifica a mudança e persiste o resultado.
Nunca promove propostas, nunca faz loop interno e nunca migra o banco sozinho.
"""

from __future__ import annotations

from contextlib import closing
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

from radar.collector import SOURCE_URL, fetch_official
from radar.document_discovery import discover_documents
from radar.document_download import download_document
from radar.document_store import (
    SCHEMA_VERSION,
    connect_documents,
    ensure_observation,
    record_version,
    register_document,
    sync_v1_identifiers,
)


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def default_sources() -> list[dict]:
    """Fontes oficiais autorizadas: Guajará-Mirim (artigo) e DOU (Seção 3)."""
    from radar.dou_source import dou_source, fetch_article
    return [
        {
            "source_url": SOURCE_URL,
            "fetch": fetch_official,
            "discover": lambda html, observation_id: discover_documents(html, SOURCE_URL, observation_id),
        },
        # DOU: enriquece cada matéria com o ato oficial completo (texto-dou).
        dou_source(article_fetcher=fetch_article),
    ]


def _coverage_state(conn, contest_id: str) -> str:
    audit = conn.execute(
        "SELECT state,checked_urls_json FROM auditorias_cobertura WHERE contest_id=? "
        "ORDER BY checked_at DESC,id DESC LIMIT 1", (contest_id,)).fetchone()
    if not audit:
        return "nao_auditada"
    state, urls_json = audit
    if state == "auditada_ate":
        import json
        urls = set(json.loads(urls_json))
        docs = {row[0] for row in conn.execute(
            "SELECT official_url FROM documentos WHERE contest_id=?", (contest_id,))}
        if not docs.issubset(urls):
            return "parcial"
    return state


def _pending_analysis(conn, contest_id: str) -> int:
    return conn.execute(
        "SELECT count(*) FROM versoes_documento v JOIN documentos d ON d.id=v.document_id "
        "WHERE d.contest_id=? AND v.extraction_state='nao_iniciada'", (contest_id,)).fetchone()[0]


def _analyze_version(db_path, version_id: str) -> None:
    """Extrai blocos/propostas de uma versão nova; falha vira estado auditável."""
    import hashlib
    from radar.document_extract import extract_blocks
    from radar.document_fields import extract_field_proposals, invalid_registration_period
    from radar.document_store import record_analysis
    with closing(connect_documents(db_path)) as conn:
        row = conn.execute(
            "SELECT v.sha256,v.local_path,v.content_type,d.contest_id,d.role_id "
            "FROM versoes_documento v JOIN documentos d ON d.id=v.document_id WHERE v.id=?",
            (version_id,)).fetchone()
    if not row:
        raise ValueError("versão inexistente")
    digest, relative_path, content_type, contest_id, role_id = row
    root = Path(db_path).resolve().parent / (Path(db_path).name + ".documents")
    artifact = (Path(db_path).resolve().parent / relative_path).resolve()
    if artifact.parent != root.resolve() or artifact.name != digest:
        raise ValueError("caminho de artefato inválido")
    content = artifact.read_bytes()
    if hashlib.sha256(content).hexdigest() != digest:
        raise ValueError("hash de artefato divergente")
    try:
        blocks = extract_blocks(content, content_type)
    except ValueError as error:
        with closing(connect_documents(db_path)) as conn, conn:
            conn.execute("UPDATE versoes_documento SET extraction_state='falhou',error_code=? WHERE id=?",
                         (type(error).__name__, version_id))
            conn.execute("""INSERT INTO eventos_documentais
                (id,document_id,version_id,event_type,occurred_at,note)
                SELECT ?,document_id,id,'falha',?,? FROM versoes_documento WHERE id=?""",
                (str(uuid4()), _now(), type(error).__name__, version_id))
        return
    proposals = extract_field_proposals(blocks, version_id, contest_id, role_id)
    record_analysis(db_path, version_id, blocks, proposals)
    if invalid_registration_period(blocks):
        with closing(connect_documents(db_path)) as conn, conn:
            conn.execute("UPDATE versoes_documento SET error_code='invalid_registration_period' WHERE id=?", (version_id,))
            conn.execute("""INSERT INTO eventos_documentais
                (id,document_id,version_id,event_type,occurred_at,note)
                SELECT ?,document_id,id,'falha',?,'invalid_registration_period'
                FROM versoes_documento WHERE id=?""", (str(uuid4()), _now(), version_id))


def _last_success(db_path, source_url: str):
    """Último `last_success_at` conhecido da fonte, preservado mesmo em ciclos com falha."""
    with closing(connect_documents(db_path)) as conn:
        row = conn.execute(
            "SELECT last_success_at FROM ciclos_fontes WHERE source_url=? AND last_success_at IS NOT NULL "
            "ORDER BY checked_at DESC LIMIT 1", (source_url,)).fetchone()
    return row[0] if row else None


def _run_source(db_path, cycle_id, source, transport, analyze, now) -> dict:
    source_url = source["source_url"]
    fonte_id = str(uuid4())
    checked_at = now()
    with closing(connect_documents(db_path)) as conn:
        observation = conn.execute(
            "SELECT id,contest_id FROM observacoes_concurso WHERE source_url=? "
            "ORDER BY competition_id LIMIT 1", (source_url,)).fetchone()
    if observation is None:
        _insert_fonte(db_path, fonte_id, cycle_id, source_url, "nao_verificada", checked_at,
                      _last_success(db_path, source_url), None, "sem_observacao_v1", 0, 0, 0, 0,
                      "nao_auditada", {})
        return {"source_url": source_url, "state": "nao_verificada", "error_code": "sem_observacao_v1"}
    observation_id, contest_id = observation
    try:
        html = source["fetch"]()
    except Exception as error:  # fonte indisponível: preserva o último resultado válido
        _insert_fonte(db_path, fonte_id, cycle_id, source_url, "falhou", checked_at,
                      _last_success(db_path, source_url), None, type(error).__name__, 0, 0, 0, 0,
                      "nao_auditada", {})
        return {"source_url": source_url, "state": "falhou", "error_code": type(error).__name__}
    try:
        candidates = source["discover"](html, observation_id)
    except Exception as error:
        _insert_fonte(db_path, fonte_id, cycle_id, source_url, "falhou", checked_at,
                      _last_success(db_path, source_url), None, type(error).__name__, 0, 0, 0, 0,
                      "nao_auditada", {})
        return {"source_url": source_url, "state": "falhou", "error_code": type(error).__name__}

    with closing(connect_documents(db_path)) as conn:
        known_ids = {row[0] for row in conn.execute(
            "SELECT id FROM documentos WHERE observation_id=?", (observation_id,))}
    documents_new = 0
    errors = []
    inline_content = {}
    for candidate in candidates:
        try:
            document_id = register_document(db_path, candidate)
        except ValueError:
            continue  # candidato inválido/desconhecido: ignorado, não é falha de fonte
        except Exception as error:
            errors.append({"stage": "register", "error_code": type(error).__name__})
            continue
        if document_id not in known_ids:
            known_ids.add(document_id)
            documents_new += 1
        # Fontes cuja API já entrega o texto oficial gravam a versão sem rebaixar a página.
        body = candidate.get("inline_content")
        if body:
            inline_content[document_id] = (
                body, candidate.get("inline_content_type") or "text/html", candidate["official_url"])

    versions_new = 0
    changes = 0
    if source.get("inline"):
        # Fonte cujo conteúdo é entregue pela API: versiona apenas as matérias desta
        # consulta. Documentos de edições anteriores não são rebaixados pela página,
        # evitando versões/mudanças falsas e crescimento ilimitado por ciclo.
        targets = list(inline_content.keys())
    else:
        with closing(connect_documents(db_path)) as conn:
            targets = [row[0] for row in conn.execute(
                "SELECT id FROM documentos WHERE contest_id=? ORDER BY discovered_at,id", (contest_id,))]
    for document_id in targets:
        with closing(connect_documents(db_path)) as conn:
            before = conn.execute("SELECT count(*) FROM versoes_documento WHERE document_id=?",
                                  (document_id,)).fetchone()[0]
        try:
            if document_id in inline_content:
                body, ctype, url = inline_content[document_id]
                version_id = record_version(db_path, document_id, body, dict(
                    fetched_at=checked_at, fetched_url=url, content_type=ctype))
            else:
                version_id = download_document(db_path, document_id, transport=transport)
        except Exception as error:
            errors.append({"document_id": document_id, "error_code": type(error).__name__})
            continue
        with closing(connect_documents(db_path)) as conn:
            after = conn.execute("SELECT count(*) FROM versoes_documento WHERE document_id=?",
                                 (document_id,)).fetchone()[0]
        if after > before:
            versions_new += 1
            if before > 0:
                changes += 1
            if analyze:
                try:
                    _analyze_version(db_path, version_id)
                except Exception as error:
                    errors.append({"document_id": document_id, "error_code": type(error).__name__})

    with closing(connect_documents(db_path)) as conn:
        pending = _pending_analysis(conn, contest_id)
        coverage = _coverage_state(conn, contest_id)
    state = "parcial" if errors else "concluido"
    summary = {"documents_found": len(candidates), "documents_new": documents_new,
               "versions_new": versions_new, "changes": changes, "errors": errors}
    _insert_fonte(db_path, fonte_id, cycle_id, source_url, state, checked_at,
                  checked_at if state == "concluido" else _last_success(db_path, source_url), None, None,
                  len(candidates), documents_new, versions_new, pending, coverage, summary)
    return {"source_url": source_url, "state": state, "documents_found": len(candidates),
            "documents_new": documents_new, "versions_new": versions_new, "changes": changes,
            "changes_pending": pending, "coverage_state": coverage, "errors": errors}


def _insert_fonte(db_path, fonte_id, cycle_id, source_url, state, checked_at, last_success_at,
                  http_status, error_code, found, new, versions, pending, coverage, summary) -> None:
    import json
    with closing(connect_documents(db_path)) as conn, conn:
        conn.execute("BEGIN IMMEDIATE")
        conn.execute(
            """INSERT INTO ciclos_fontes (id,cycle_id,source_url,state,checked_at,last_success_at,
            http_status,error_code,documents_found,documents_new,versions_new,changes_pending,
            coverage_state,summary_json) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (fonte_id, cycle_id, source_url, state, checked_at, last_success_at, http_status,
             error_code, found, new, versions, pending, coverage, json.dumps(summary, ensure_ascii=False)))


def run_cycle(db_path, *, sources=None, transport=None, analyze=False, now=None) -> dict:
    """Executa um ciclo único de monitoramento e devolve um resumo verificável."""
    now = now or _now
    if not Path(db_path).exists():
        raise ValueError("banco documental inexistente; rode documents-migrate")
    sources = list(default_sources() if sources is None else sources)
    with closing(connect_documents(db_path)) as conn:
        version = conn.execute("PRAGMA user_version").fetchone()[0]
    if version != SCHEMA_VERSION:
        raise ValueError("migração documental pendente; rode documents-migrate")
    sync_v1_identifiers(db_path)
    # Fontes que não derivam de ``concursos`` v1 declaram a própria identidade.
    for source in sources:
        competition_id = source.get("competition_id")
        if competition_id:
            ensure_observation(db_path, source["source_url"], competition_id)

    started = now()
    cycle_id = str(uuid4())
    with closing(connect_documents(db_path)) as conn, conn:
        conn.execute("BEGIN IMMEDIATE")
        conn.execute("UPDATE ciclos_monitoramento SET state='interrompido',finished_at=? "
                     "WHERE state='em_andamento'", (started,))
        conn.execute("INSERT INTO ciclos_monitoramento (id,started_at,state) VALUES (?,?,'em_andamento')",
                     (cycle_id, started))

    results = [_run_source(db_path, cycle_id, source, transport, analyze, now) for source in sources]

    states = [result["state"] for result in results]
    if states and all(state == "falhou" for state in states):
        cycle_state = "falhou"
    elif states and all(state == "concluido" for state in states):
        cycle_state = "concluido"
    else:
        cycle_state = "parcial"
    finished = now()
    with closing(connect_documents(db_path)) as conn, conn:
        conn.execute("BEGIN IMMEDIATE")
        documents_found = conn.execute(
            "SELECT coalesce(sum(documents_found),0) FROM ciclos_fontes WHERE cycle_id=?", (cycle_id,)).fetchone()[0]
        documents_new = conn.execute(
            "SELECT coalesce(sum(documents_new),0) FROM ciclos_fontes WHERE cycle_id=?", (cycle_id,)).fetchone()[0]
        versions_new = conn.execute(
            "SELECT coalesce(sum(versions_new),0) FROM ciclos_fontes WHERE cycle_id=?", (cycle_id,)).fetchone()[0]
        pending = conn.execute(
            "SELECT coalesce(max(changes_pending),0) FROM ciclos_fontes WHERE cycle_id=?", (cycle_id,)).fetchone()[0]
        last_success = conn.execute(
            "SELECT max(last_success_at) FROM ciclos_fontes WHERE cycle_id=?", (cycle_id,)).fetchone()[0]
        conn.execute("""UPDATE ciclos_monitoramento SET finished_at=?,state=?,documents_found=?,
            documents_new=?,versions_new=?,changes_pending=?,last_success_at=? WHERE id=?""",
            (finished, cycle_state, documents_found, documents_new, versions_new, pending,
             last_success, cycle_id))
    return {"cycle_id": cycle_id, "state": cycle_state, "started_at": started, "finished_at": finished,
            "documents_found": documents_found, "documents_new": documents_new,
            "versions_new": versions_new, "changes_pending": pending, "sources": results}
