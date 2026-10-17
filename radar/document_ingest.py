"""Documentos bloqueados, alternativas oficiais e ingestão manual controlada (Fase 28).

Princípios:

- ``robots.txt`` **não** é contornado: se o host proíbe, o documento é registrado com URL e
  metadados, o bloqueio fica registrado e o byte não é baixado;
- alternativa só é sugerida quando há **igualdade exata** de identificador ou URL em host
  autorizado — nunca por semelhança de título;
- o arquivo fornecido manualmente **não** vira oficial por declaração: guarda procedência
  explícita (origem declarada, URL original, canal, autor, data e hash local) e continua
  sujeito à revisão documental;
- o conteúdo é validado por assinatura antes de persistir e nunca é executado.
"""

from __future__ import annotations

import json
from contextlib import closing
from datetime import datetime, timezone
from hashlib import sha256
from urllib.parse import urlsplit
from uuid import uuid4

from radar.document_discovery import allowed_document_url
from radar.document_store import connect_documents, is_readable_schema, record_version

INGEST_VERSION = "ingest_v1"

MAX_BYTES = 20 * 1024 * 1024
ALLOWED_TYPES = ("application/pdf", "application/zip", "text/html")

STATE_LABELS = {
    "obtido": "Versão obtida pelo coletor",
    "importado_manualmente": "Importado manualmente (procedência declarada)",
    "bloqueado": "Download bloqueado pela fonte (robots.txt)",
    "indisponivel": "Indisponível na fonte (HTTP de erro)",
    "pendente_download": "Registrado, ainda não baixado",
}

BLOCKED_REASON_LABELS = {
    "robots_disallow_anexos_cdn": "robots.txt do CDN de anexos proíbe a coleta",
    "host_nao_autorizado": "Host não autorizado para download",
}


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _require_text(value, message):
    if not isinstance(value, str) or not value.strip():
        raise ValueError(message)
    return value.strip()


def detect_content_type(body: bytes):
    """Assinatura do arquivo, não a extensão nem a declaração do usuário."""
    if not isinstance(body, (bytes, bytearray)) or not body:
        return None
    if body.startswith(b"%PDF-"):
        return "application/pdf"
    if body.startswith(b"PK\x03\x04"):
        return "application/zip"
    head = bytes(body[:512]).lstrip().lower()
    if head.startswith(b"<!doctype html") or head.startswith(b"<html"):
        return "text/html"
    return None


def record_blocked_document(db_path, document_id: str, reason: str, *, official_url=None,
                            evidence: dict | None = None, detected_at=None) -> dict:
    """Registra (append-only, idempotente) que o download foi bloqueado pela política da fonte."""
    reason = _require_text(reason, "motivo do bloqueio obrigatório")
    if reason not in BLOCKED_REASON_LABELS:
        raise ValueError("motivo de bloqueio desconhecido")
    at = detected_at or _now()
    with closing(connect_documents(db_path)) as conn, conn:
        conn.execute("BEGIN IMMEDIATE")
        if not is_readable_schema(conn):
            raise ValueError("migração documental pendente")
        row = conn.execute("SELECT official_url FROM documentos WHERE id=?",
                           (document_id,)).fetchone()
        if not row:
            raise ValueError("documento inexistente")
        url = official_url or row[0]
        host = urlsplit(url).hostname or ""
        payload = {"reason": reason, "host": host, "official_url": url,
                   "robots_url": f"https://{host}/robots.txt" if host else None,
                   "evidence": evidence or {}, "detected_at": at}
        note = json.dumps(payload, ensure_ascii=False, sort_keys=True)
        # Idempotência por (documento, motivo, host): o instante da detecção não duplica o fato.
        for event_id, previous in conn.execute(
                "SELECT id, note FROM eventos_documentais WHERE document_id=? "
                "AND event_type='download_bloqueado' ORDER BY occurred_at", (document_id,)):
            try:
                parsed = json.loads(previous)
            except (TypeError, ValueError):
                continue
            if parsed.get("reason") == reason and parsed.get("host") == host:
                return {"version": INGEST_VERSION, "event_id": event_id, "duplicado": True}
        event_id = str(uuid4())
        conn.execute(
            "INSERT INTO eventos_documentais (id,document_id,event_type,occurred_at,note) "
            "VALUES (?,?,'download_bloqueado',?,?)", (event_id, document_id, at, note))
    return {"version": INGEST_VERSION, "event_id": event_id, "duplicado": False,
            "host": host, "reason": reason}


def _acquisition_state(has_version: bool, imported: bool, blocked: bool, failed: bool) -> str:
    if imported:
        return "importado_manualmente"
    if has_version:
        return "obtido"
    if blocked:
        return "bloqueado"
    if failed:
        return "indisponivel"
    return "pendente_download"


def blocked_report(db_path, *, contest_id=None, states=None, limit=200) -> dict:
    """Estado de aquisição de cada documento, com motivo explícito e alternativas.

    ``states`` restringe aos estados pedidos (ex.: ``("bloqueado","indisponivel")``).
    """
    limit = int(limit)
    if limit < 1 or limit > 1000:
        raise ValueError("limite fora da faixa")
    if states is not None:
        if isinstance(states, str):
            states = [item for item in states.split(",") if item]
        states = tuple(states)
        if not states or any(state not in STATE_LABELS for state in states):
            raise ValueError("estado de aquisição inválido")
    with closing(connect_documents(db_path)) as conn:
        if not is_readable_schema(conn):
            raise ValueError("migração documental pendente")
        rows = conn.execute("""
            SELECT d.id, d.title, d.official_url, d.issuer, d.kind, d.tipo_documental,
                   d.published_at, d.contest_id, o.source_url, o.competition_id,
                   (SELECT COUNT(*) FROM versoes_documento v WHERE v.document_id=d.id),
                   (SELECT COUNT(*) FROM ingestoes_documentais i WHERE i.document_id=d.id),
                   (SELECT COUNT(*) FROM eventos_documentais e WHERE e.document_id=d.id
                    AND e.event_type='download_bloqueado'),
                   (SELECT COUNT(*) FROM tentativas_download t WHERE t.document_id=d.id
                    AND t.state='falhou')
            FROM documentos d
            LEFT JOIN observacoes_concurso o ON o.id=d.observation_id
            WHERE (? IS NULL OR d.contest_id=?)
            ORDER BY d.contest_id, d.title, d.id""", (contest_id, contest_id)).fetchall()
        blocked_events = {}
        for document_id, note in conn.execute(
                "SELECT document_id, note FROM eventos_documentais "
                "WHERE event_type='download_bloqueado' ORDER BY occurred_at"):
            try:
                blocked_events[document_id] = json.loads(note)
            except (TypeError, ValueError):
                blocked_events[document_id] = {"reason": "desconhecido", "evidence": {}}
        paths = {}
        for document_id, url in conn.execute("SELECT id, official_url FROM documentos"):
            paths.setdefault(_path_of(url), []).append((document_id, url))
        with_version = {row[0] for row in conn.execute(
            "SELECT DISTINCT document_id FROM versoes_documento")}
        imports = {}
        for row in conn.execute(
                "SELECT document_id, channel, declared_origin, ingested_at, sha256, review_state "
                "FROM ingestoes_documentais ORDER BY ingested_at"):
            imports[row[0]] = {"channel": row[1], "declared_origin": row[2],
                               "ingested_at": row[3], "sha256": row[4], "review_state": row[5]}

    items = []
    totals = {}
    for row in rows:
        (document_id, title, official_url, issuer, kind, tipo, published, contest,
         page_url, competition_id, versions, imported, blocked, failed) = row
        state = _acquisition_state(bool(versions), bool(imported), bool(blocked), bool(failed))
        event = blocked_events.get(document_id)
        item = {
            "document_id": document_id,
            "title": title,
            "official_url": official_url,
            "issuer": issuer,
            "kind": kind,
            "tipo_documental": tipo,
            "published_at": published,
            "contest_id": contest,
            "competition_id": competition_id,
            "page_url": page_url,
            "state": state,
            "state_label": STATE_LABELS[state],
            "versions": versions,
            "blocked_reason": event.get("reason") if event else None,
            "blocked_reason_label": BLOCKED_REASON_LABELS.get(event.get("reason"))
            if event else None,
            "blocked_evidence": event.get("evidence") if event else None,
            "manual_import": imports.get(document_id),
        }
        if state in ("bloqueado", "indisponivel"):
            item["alternatives"] = _alternatives(
                official_url, page_url, paths, with_version, document_id)
        totals[state] = totals.get(state, 0) + 1
        if states is not None and state not in states:
            continue
        items.append(item)
    return {
        "version": INGEST_VERSION,
        "total": len(items),
        "por_estado": totals,
        "itens": items[:limit],
        "limitacao": ("Documento bloqueado não é 'edital inexistente': a referência oficial é "
                      "preservada. Nenhum controle de acesso é contornado; a obtenção legítima "
                      "depende de página oficial alternativa ou fornecimento manual."),
    }


def _alternatives(official_url, page_url, paths, with_version, document_id):
    """Alternativas determinísticas: igualdade exata de caminho ou página acessível.

    Não há semelhança de título, órgão ou data: só entra o que é igual byte a byte no caminho
    do arquivo (mesma plataforma, host diferente) ou uma página oficial acessível.
    """
    out = []
    if page_url:
        authorized = allowed_document_url(page_url)
        out.append({"tipo": "pagina_de_origem", "url": page_url,
                    "download_autorizado": authorized,
                    "motivo": ("página oficial de origem; download direto autorizado"
                               if authorized else
                               "página oficial de origem legível pelo adaptador da fonte; "
                               "download direto de arquivo não autorizado")})
    for other, other_url in paths.get(_path_of(official_url), []):
        if other == document_id or other not in with_version:
            continue
        if allowed_document_url(other_url):
            out.append({"tipo": "caminho_identico_em_host_autorizado", "document_id": other,
                        "motivo": "mesmo caminho de arquivo já obtido em host autorizado"})
        else:
            out.append({"tipo": "caminho_identico_em_host_nao_autorizado",
                        "document_id": other,
                        "motivo": "mesmo caminho obtido em host sem autorização de download"})
    out.append({"tipo": "pesquisa_humana",
                "motivo": ("verificar portal do órgão contratante e Diário Oficial; a identidade "
                           "do documento deve ser conferida por título, data e conteúdo")})
    out.append({"tipo": "importacao_manual",
                "motivo": "usuário pode fornecer o arquivo com procedência declarada e hash local"})
    return out


def _path_of(url: str) -> str:
    """Caminho do arquivo (sem host): igualdade exata entre espelhos da mesma plataforma."""
    return urlsplit(url or "").path


def ingest_manual_document(db_path, document_id: str, body: bytes, *, declared_origin: str,
                           channel: str, declared_by: str, original_url=None, note=None,
                           dry_run: bool = False, now=None) -> dict:
    """Persiste arquivo fornecido pelo usuário com procedência explícita e hash local.

    Não marca o documento como oficial: registra a ingestão e deixa o documento sujeito à
    revisão. O arquivo é validado por assinatura; conteúdo não reconhecido é recusado.
    """
    declared_origin = _require_text(declared_origin, "origem declarada obrigatória")
    channel = _require_text(channel, "canal de ingestão obrigatório")
    declared_by = _require_text(declared_by, "responsável pela ingestão obrigatório")
    if not isinstance(body, (bytes, bytearray)) or not body:
        raise ValueError("arquivo vazio")
    if len(body) > MAX_BYTES:
        raise ValueError("arquivo excede o limite")
    content_type = detect_content_type(body)
    if content_type not in ALLOWED_TYPES:
        raise ValueError("formato de arquivo não reconhecido")
    if original_url is not None:
        parts = urlsplit(original_url)
        if parts.scheme not in ("http", "https") or not parts.hostname:
            raise ValueError("URL original inválida")
    at = now or _now()
    digest = sha256(bytes(body)).hexdigest()

    with closing(connect_documents(db_path)) as conn:
        if not is_readable_schema(conn):
            raise ValueError("migração documental pendente")
        document = conn.execute("SELECT official_url FROM documentos WHERE id=?",
                                (document_id,)).fetchone()
        if not document:
            raise ValueError("documento inexistente")
        existing = conn.execute(
            "SELECT id FROM versoes_documento WHERE document_id=? AND sha256=?",
            (document_id, digest)).fetchone()

    validation = {"assinatura": content_type, "bytes": len(body), "sha256": digest,
                  "limite_bytes": MAX_BYTES, "resultado": "valido"}
    if existing:
        return {"version": INGEST_VERSION, "duplicada": True, "version_id": existing[0],
                "sha256": digest, "content_type": content_type, "validation": validation,
                "review_state": "pendente"}
    if dry_run:
        return {"version": INGEST_VERSION, "duplicada": False, "version_id": None,
                "sha256": digest, "content_type": content_type, "validation": validation,
                "dry_run": True}

    version_id = record_version(
        db_path, document_id, bytes(body),
        dict(fetched_at=at, fetched_url=original_url or document[0],
             content_type=content_type))
    # ``record_version`` pode deduplicar por conteúdo documental: o hash gravado é a verdade.
    with closing(connect_documents(db_path)) as conn:
        stored = conn.execute("SELECT sha256 FROM versoes_documento WHERE id=?",
                              (version_id,)).fetchone()
    version_sha = stored[0] if stored else digest
    validation["sha256_local"] = digest
    validation["sha256_versao"] = version_sha
    ingestion_id = str(uuid4())
    with closing(connect_documents(db_path)) as conn, conn:
        conn.execute(
            "INSERT INTO ingestoes_documentais (id,document_id,version_id,declared_origin,"
            "original_url,channel,ingested_at,sha256,byte_size,content_type,validation_json,"
            "review_state,note) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (ingestion_id, document_id, version_id, declared_origin, original_url or document[0],
             channel, at, version_sha, len(body), content_type,
             json.dumps(validation, ensure_ascii=False, sort_keys=True), "pendente", note))
        conn.execute(
            "INSERT INTO eventos_documentais (id,document_id,version_id,event_type,occurred_at,note)"
            " VALUES (?,?,?,'ingestao_manual',?,?)",
            (str(uuid4()), document_id, version_id, at,
             json.dumps({"origem_declarada": declared_origin, "canal": channel,
                         "responsavel": declared_by, "sha256": digest}, ensure_ascii=False)))
    return {"version": INGEST_VERSION, "duplicada": False, "version_id": version_id,
            "ingestion_id": ingestion_id, "sha256": digest, "content_type": content_type,
            "validation": validation, "review_state": "pendente",
            "limitacao": ("Ingestão manual não confirma o documento como oficial; a procedência "
                          "fica registrada e a revisão documental continua obrigatória.")}
