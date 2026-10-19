"""Executa um ciclo de monitoramento das fontes oficiais autorizadas.

O ciclo é único e termina: consulta a página de descoberta, registra documentos
novos, baixa/compara os conhecidos, classifica a mudança e persiste o resultado.
Nunca promove propostas, nunca faz loop interno e nunca migra o banco sozinho.
"""

from __future__ import annotations

import json
from contextlib import closing
from datetime import datetime, timezone, timedelta
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
    """Fontes oficiais autorizadas: Guajará-Mirim (artigo), DOU (Seção 3), FGV, Quadrix e IBFC."""
    from radar.dou_source import dou_source, fetch_article
    from radar.fgv_source import fgv_source
    from radar.ibfc_source import ibfc_source
    from radar.pci_source import pci_source
    from radar.quadrix_source import quadrix_source
    return [
        {
            "source_url": SOURCE_URL,
            "fetch": fetch_official,
            "discover": lambda html, observation_id: discover_documents(html, SOURCE_URL, observation_id),
        },
        # DOU: enriquece cada matéria com o ato oficial completo (texto-dou).
        dou_source(article_fetcher=fetch_article),
        # FGV: catálogo de concursos, com identidade por concurso (multi-concurso).
        fgv_source(),
        # Quadrix: banca com páginas server-rendered e documentos públicos (multi-concurso).
        quadrix_source(),
        # IBFC (Fase 27): banca com catálogo server-rendered; identidade por certame.
        # ``download_new_only`` evita rebaixar todo o histórico a cada ciclo.
        {**ibfc_source(), "download_new_only": True},
        # PCI: canal complementar de descoberta (agregador não oficial), via MCP.
        pci_source(),
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


PREFIX_PAGES = 40
EXTRACTOR_VERSION = "extract_v2"


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
    from radar.document_extract import ExtractionError, extract_document
    try:
        extracted = extract_document(content, content_type, prefix_pages=PREFIX_PAGES)
    except ExtractionError as error:
        with closing(connect_documents(db_path)) as conn, conn:
            conn.execute("UPDATE versoes_documento SET extraction_state='falhou',error_code=? WHERE id=?",
                         (error.code, version_id))
            conn.execute("""INSERT INTO eventos_documentais
                (id,document_id,version_id,event_type,occurred_at,note)
                SELECT ?,document_id,id,'falha',?,? FROM versoes_documento WHERE id=?""",
                (str(uuid4()), _now(), json.dumps(
                    {"code": error.code, "message": str(error)[:200],
                     "extractor_version": EXTRACTOR_VERSION}, ensure_ascii=False), version_id))
        return
    except ValueError as error:
        with closing(connect_documents(db_path)) as conn, conn:
            conn.execute("UPDATE versoes_documento SET extraction_state='falhou',error_code=? WHERE id=?",
                         (type(error).__name__, version_id))
        return
    blocks = extracted["blocks"]
    proposals = extract_field_proposals(blocks, version_id, contest_id, role_id,
                                        pdf_bytes=content)
    note = json.dumps({"extractor_version": extracted["extractor_version"],
                       "truncated": extracted["truncated"],
                       "total_pages": extracted["total_pages"],
                       "limitation": extracted["limitation"],
                       "blocks": len(blocks)}, ensure_ascii=False)
    record_analysis(db_path, version_id, blocks, proposals, note=note,
                    partial=bool(extracted["truncated"]))
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


DENIAL_WINDOW_HOURS = 24


def _recently_denied(db_path, document_ids) -> set:
    """Documentos com 401/403/429 recente: não repetir a tentativa a cada ciclo."""
    if not document_ids:
        return set()
    cutoff = (datetime.now(timezone.utc) - timedelta(hours=DENIAL_WINDOW_HOURS)).isoformat()
    marks = ",".join("?" for _ in document_ids)
    with closing(connect_documents(db_path)) as conn:
        rows = conn.execute(
            f"SELECT DISTINCT document_id FROM tentativas_download "
            f"WHERE attempted_at >= ? AND document_id IN ({marks}) "
            f"AND error_code IN ('acesso_negado','limite_acesso')",
            (cutoff, *document_ids)).fetchall()
    return {row[0] for row in rows}


def _check_identity_after_download(db_path, document_id: str, version_id: str) -> None:
    """Divergência de identidade vai para revisão humana; nunca é resolvida por suposição."""
    from radar.document_ingest import check_download_identity
    try:
        check_download_identity(db_path, document_id, version_id)
    except ValueError:
        pass


def _run_source(db_path, cycle_id, source, transport, analyze, now) -> dict:
    source_url = source["source_url"]
    fonte_id = str(uuid4())
    checked_at = now()
    multi = bool(source.get("multi_contest"))
    if multi:
        observation_id = None
        contest_id = None
    else:
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
    extra_summary = {}
    source_partial = False
    source_failed = False
    try:
        if multi:
            discovered = source["discover"](db_path, html)
            if isinstance(discovered, dict):
                candidates = discovered.get("candidates", [])
                extra_summary = discovered.get("summary", {}) or {}
                source_partial = bool(discovered.get("partial"))
                source_failed = bool(discovered.get("failed"))
            else:
                candidates = discovered
        else:
            candidates = source["discover"](html, observation_id)
    except Exception as error:
        _insert_fonte(db_path, fonte_id, cycle_id, source_url, "falhou", checked_at,
                      _last_success(db_path, source_url), None, type(error).__name__, 0, 0, 0, 0,
                      "nao_auditada", {})
        return {"source_url": source_url, "state": "falhou", "error_code": type(error).__name__}

    known_by_obs: dict[str, set] = {}
    involved_contests: set = set()
    if contest_id is not None:
        involved_contests.add(contest_id)
    documents_new = 0
    nominal_skipped = 0
    new_ids = []
    skip_download = {}
    allowed_hosts = {}
    policy_stripped = []
    policy_skipped = []
    errors = []
    inline_content = {}
    for candidate in candidates:
        obs_id = candidate.get("observation_id")
        if not obs_id:
            errors.append({"stage": "candidate", "error_code": "sem_observacao"})
            continue
        if obs_id not in known_by_obs:
            with closing(connect_documents(db_path)) as conn:
                known_by_obs[obs_id] = {row[0] for row in conn.execute(
                    "SELECT id FROM documentos WHERE observation_id=?", (obs_id,))}
                row = conn.execute("SELECT contest_id FROM observacoes_concurso WHERE id=?", (obs_id,)).fetchone()
                if row:
                    involved_contests.add(row[0])
        # Porta única de persistência: o tipo de conteúdo do candidato é decidido aqui e
        # consultado na política antes de qualquer escrita.
        from radar import source_policy
        policy_source = source.get("id") or "guajara"
        content_type = ("documento" if candidate.get("inline_content")
                        or candidate.get("kind") in ("edital", "retificacao")
                        else "metadados")
        body_denied = False
        if not source_policy.can_persist(policy_source, content_type):
            if candidate.get("inline_content") and source_policy.can_persist(
                    policy_source, "metadados"):
                # Metadados/URL continuam como pista; o corpo de terceiro não é gravado.
                candidate = {k: v for k, v in candidate.items()
                             if k not in ("inline_content", "inline_content_type")}
                body_denied = True
                policy_stripped.append({"document_url": candidate.get("official_url"),
                                        "content_type": content_type,
                                        "permission": source_policy.decision(
                                            policy_source, content_type)["permission"]})
            else:
                policy_skipped.append({"document_url": candidate.get("official_url"),
                                       "content_type": content_type,
                                       "permission": source_policy.decision(
                                           policy_source, content_type)["permission"]})
                continue
        try:
            document_id = register_document(db_path, candidate)
        except ValueError:
            continue  # candidato inválido/desconhecido: ignorado, não é falha de fonte
        except Exception as error:
            errors.append({"stage": "register", "error_code": type(error).__name__})
            continue
        if document_id not in known_by_obs[obs_id]:
            known_by_obs[obs_id].add(document_id)
            documents_new += 1
            new_ids.append(document_id)
        from radar.document_types import is_nominal_title
        if is_nominal_title(candidate.get("title")):
            # Lista nominal (nomes/notas de candidatos): metadados ficam, o corpo não é
            # baixado nem extraído. Vale mesmo quando a banca rotula como "Retificação".
            skip_download[document_id] = "lista_nominal"
            nominal_skipped += 1
            continue
        if body_denied:
            # Corpo de terceiro não autorizado: nem download, nem versão. Metadados ficam.
            skip_download[document_id] = "politica_conteudo"
        # Candidato cujo host não é autorizado para download (ex.: CDN com robots.txt
        # restritivo) é registrado com metadados e URL, mas o byte não é buscado.
        if candidate.get("fetch_allowed") is False:
            reason = candidate.get("fetch_blocked_reason") or "host_nao_autorizado"
            skip_download[document_id] = reason
            # Política da fonte (robots.txt), NÃO negativa HTTP: fica registrada por documento
            # como política, para não ser confundida com "servidor negou acesso".
            from radar.document_ingest import record_policy_block
            try:
                record_policy_block(
                    db_path, document_id, reason,
                    official_url=candidate.get("official_url"),
                    evidence={"fonte": source.get("id"),
                              "politica": "fetch_allowed=false"},
                    detected_at=checked_at)
            except ValueError:
                pass
        elif candidate.get("download_allowed_hosts"):
            allowed_hosts[document_id] = tuple(candidate["download_allowed_hosts"])
        # Fontes cuja API já entrega o texto oficial gravam a versão sem rebaixar a página.
        body = candidate.get("inline_content")
        if body:
            inline_content[document_id] = (
                body, candidate.get("inline_content_type") or "text/html", candidate["official_url"])

    versions_new = 0
    changes = 0
    denied_recent = _recently_denied(db_path, list(skip_download))
    if source.get("inline"):
        # Fonte cujo conteúdo é entregue pela API: versiona apenas as matérias desta
        # consulta. Documentos de edições anteriores não são rebaixados pela página,
        # evitando versões/mudanças falsas e crescimento ilimitado por ciclo.
        targets = list(inline_content.keys())
    elif source.get("download_new_only"):
        # Fontes de catálogo (ex.: banca): baixa apenas documentos novos do ciclo,
        # sem repetir todo o histórico a cada consulta.
        targets = new_ids
    elif contest_id is None:
        targets = []  # fonte multi-concurso sem política de download: nada a rebaixar
    else:
        with closing(connect_documents(db_path)) as conn:
            targets = [row[0] for row in conn.execute(
                "SELECT id FROM documentos WHERE contest_id=? ORDER BY discovered_at,id", (contest_id,))]
    for document_id in targets:
        if document_id in skip_download:
            # Política de acesso, não falha: o documento fica com URL e metadados, sem byte.
            # O motivo entra no resumo da fonte (``summary_json``), não como erro.
            continue
        if document_id in denied_recent:
            # A fonte já negou (401/403) ou limitou (429) há pouco: não repetir a tentativa.
            skip_download[document_id] = "acesso_negado_recente"
            continue
        with closing(connect_documents(db_path)) as conn:
            before = conn.execute("SELECT count(*) FROM versoes_documento WHERE document_id=?",
                                  (document_id,)).fetchone()[0]
        try:
            if document_id in inline_content:
                body, ctype, url = inline_content[document_id]
                version_id = record_version(db_path, document_id, body, dict(
                    fetched_at=checked_at, fetched_url=url, content_type=ctype))
            else:
                version_id = download_document(
                    db_path, document_id, transport=transport,
                    allowed_hosts=allowed_hosts.get(document_id))
                _check_identity_after_download(db_path, document_id, version_id)
        except Exception as error:
            errors.append({"document_id": document_id,
                           "error_code": getattr(error, "code", type(error).__name__),
                           "http_status": getattr(error, "http_status", None)})
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
        if contest_id is not None:
            pending = _pending_analysis(conn, contest_id)
            coverage = _coverage_state(conn, contest_id)
        else:
            pending = sum(_pending_analysis(conn, cid) for cid in involved_contests)
            coverage = "parcial" if any(
                _coverage_state(conn, cid) != "nao_auditada" for cid in involved_contests) else "nao_auditada"
    if source_failed:
        state = "falhou"  # nenhuma consulta teve sucesso: não é "sem novidades"
    elif errors or source_partial:
        state = "parcial"
    else:
        state = "concluido"
    bloqueados = {}
    for motivo in skip_download.values():
        bloqueados[motivo] = bloqueados.get(motivo, 0) + 1
    summary = {"documents_found": len(candidates), "documents_new": documents_new,
               "versions_new": versions_new, "changes": changes, "errors": errors,
               "downloads_bloqueados": bloqueados,
               "politica_nao_persistido": policy_skipped,
               "politica_sem_corpo": policy_stripped}
    for key, value in extra_summary.items():
        if key != "errors":
            summary[key] = value
    if "errors" in extra_summary:
        summary["source_errors"] = extra_summary["errors"]
    _insert_fonte(db_path, fonte_id, cycle_id, source_url, state, checked_at,
                  checked_at if state == "concluido" else _last_success(db_path, source_url), None, None,
                  len(candidates), documents_new, versions_new, pending, coverage, summary)
    return {"source_url": source_url, "state": state, "documents_found": len(candidates),
            "documents_new": documents_new, "versions_new": versions_new, "changes": changes,
            "changes_pending": pending, "coverage_state": coverage, "errors": errors,
            "downloads_bloqueados": bloqueados,
            "politica_nao_persistido": len(policy_skipped),
            "politica_sem_corpo": len(policy_stripped),
            "nominais_ignorados": nominal_skipped}


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
            ensure_observation(db_path, source["source_url"], competition_id,
                               tipo_identidade=source.get("tipo_identidade"))

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
