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
from datetime import datetime, timezone, timedelta
from hashlib import sha256
from urllib.parse import urlsplit
from uuid import uuid4

from radar.document_discovery import allowed_document_url
from radar.document_store import connect_documents, is_readable_schema, record_version

INGEST_VERSION = "ingest_v1"

MAX_BYTES = 20 * 1024 * 1024
ALLOWED_TYPES = ("application/pdf", "application/zip", "text/html")

# Estados de aquisição. Política de robots é **política**, não negativa HTTP: nunca é
# apresentada como se o servidor tivesse recusado o acesso.
STATE_LABELS = {
    "baixado": "Baixado e validado",
    "importado_manualmente": "Importado manualmente (procedência declarada)",
    "politica_robots": "Não tentado: robots.txt do host restringe a coleta",
    "acesso_negado": "Servidor negou o acesso (401/403)",
    "limite_acesso": "Servidor sinalizou limite de acesso (429)",
    "falha_temporaria": "Falha temporária na tentativa de download",
    "arquivo_invalido": "Arquivo recebido não passou na validação",
    "identidade_pendente": "Baixado, identidade pendente de confirmação humana",
    "pendente_tentativa": "Registrado, download ainda não tentado",
}

BLOCKED_REASON_LABELS = {
    "robots_disallow_anexos_cdn": "robots.txt do CDN de anexos restringe a coleta",
    "host_nao_autorizado": "Host não autorizado para download",
}

# Compatibilidade com nomes anteriores do relatório.
STATE_ALIASES = {"obtido": "baixado", "bloqueado": "politica_robots",
                 "indisponivel": "falha_temporaria", "pendente_download": "pendente_tentativa"}


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


def record_policy_block(db_path, document_id: str, reason: str, *, official_url=None,
                        evidence: dict | None = None, detected_at=None) -> dict:
    """Registra (append-only, idempotente) que a **política** da fonte impediu a tentativa.

    Isto não é negativa HTTP: nenhuma requisição foi feita ao arquivo. O evento é
    ``politica_robots`` para não confundir restrição de robots com acesso negado pelo servidor.
    """
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
                "AND event_type IN ('politica_robots','download_bloqueado') "
                "ORDER BY occurred_at", (document_id,)):
            try:
                parsed = json.loads(previous)
            except (TypeError, ValueError):
                continue
            if parsed.get("reason") == reason and parsed.get("host") == host:
                return {"version": INGEST_VERSION, "event_id": event_id, "duplicado": True}
        event_id = str(uuid4())
        conn.execute(
            "INSERT INTO eventos_documentais (id,document_id,event_type,occurred_at,note) "
            "VALUES (?,?,'politica_robots',?,?)", (event_id, document_id, at, note))
    return {"version": INGEST_VERSION, "event_id": event_id, "duplicado": False,
            "host": host, "reason": reason}


def _acquisition_state(has_version: bool, imported: bool, policy: bool,
                       last_error: str | None, identity_pending: bool,
                       attempted: bool) -> str:
    """Classifica o estado real de aquisição, sem confundir política com negativa HTTP."""
    if identity_pending:
        return "identidade_pendente"
    if imported:
        return "importado_manualmente"
    if has_version:
        return "baixado"
    if last_error in ("acesso_negado", "limite_acesso", "arquivo_invalido",
                      "falha_temporaria", "url_nao_autorizada", "http_invalido"):
        return "acesso_negado" if last_error == "acesso_negado" else (
            "limite_acesso" if last_error == "limite_acesso" else (
                "arquivo_invalido" if last_error == "arquivo_invalido"
                else "falha_temporaria"))
    if attempted:
        return "falha_temporaria"
    if policy:
        return "politica_robots"
    return "pendente_tentativa"


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
        states = tuple(STATE_ALIASES.get(state, state) for state in states)
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
                    AND e.event_type IN ('politica_robots','download_bloqueado')),
                   (SELECT COUNT(*) FROM tentativas_download t WHERE t.document_id=d.id),
                   (SELECT t.error_code FROM tentativas_download t WHERE t.document_id=d.id
                    ORDER BY t.attempted_at DESC, t.rowid DESC LIMIT 1),
                   (SELECT COUNT(*) FROM eventos_documentais e WHERE e.document_id=d.id
                    AND e.event_type='identidade_pendente')
            FROM documentos d
            LEFT JOIN observacoes_concurso o ON o.id=d.observation_id
            WHERE (? IS NULL OR d.contest_id=?)
            ORDER BY d.contest_id, d.title, d.id""", (contest_id, contest_id)).fetchall()
        blocked_events = {}
        for document_id, note in conn.execute(
                "SELECT document_id, note FROM eventos_documentais "
                "WHERE event_type IN ('politica_robots','download_bloqueado') "
                "ORDER BY occurred_at"):
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
         page_url, competition_id, versions, imported, blocked, attempted,
         last_error, identity_pending) = row
        state = _acquisition_state(bool(versions), bool(imported), bool(blocked),
                                   last_error, bool(identity_pending), bool(attempted))
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
            "attempted": bool(attempted),
            "last_error": last_error,
            "blocked_reason": event.get("reason") if event else None,
            "blocked_reason_label": BLOCKED_REASON_LABELS.get(event.get("reason"))
            if event else None,
            "blocked_evidence": event.get("evidence") if event else None,
            "manual_import": imports.get(document_id),
        }
        if state in ("politica_robots", "acesso_negado", "limite_acesso",
                     "falha_temporaria", "arquivo_invalido", "pendente_tentativa"):
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
        "limitacao": ("Documento não obtido não é 'edital inexistente': a referência oficial é "
                      "preservada. Política de robots.txt não é negativa HTTP. Nenhum controle "
                      "de acesso é contornado; a obtenção legítima depende de página oficial "
                      "alternativa ou fornecimento manual."),
    }


def check_download_identity(db_path, document_id: str, version_id: str) -> dict:
    """Verifica se a identidade do documento bate com a observação de origem.

    Divergência (prefixo do identificador, ausência de órgão ou de identificador) **não** é
    resolvida automaticamente: vira evento ``identidade_pendente`` para revisão humana, com
    URL, data da coleta e hash preservados.
    """
    at = _now()
    with closing(connect_documents(db_path)) as conn:
        if not is_readable_schema(conn):
            raise ValueError("migração documental pendente")
        row = conn.execute("""
            SELECT d.issuer, d.source_identifier, d.official_url, o.competition_id, v.sha256
            FROM documentos d
            LEFT JOIN observacoes_concurso o ON o.id=d.observation_id
            LEFT JOIN versoes_documento v ON v.id=?
            WHERE d.id=?""", (version_id, document_id)).fetchone()
    if not row:
        raise ValueError("documento inexistente")
    issuer, source_identifier, official_url, competition_id, digest = row
    problems = []
    if not issuer:
        problems.append("documento sem órgão/emissor")
    if source_identifier and competition_id:
        prefix = source_identifier.split(":", 1)[0]
        if prefix != competition_id:
            problems.append("identificador do documento diverge da observação")
    if not source_identifier:
        problems.append("documento sem identificador de origem")
    result = {"document_id": document_id, "version_id": version_id, "sha256": digest,
              "competition_id": competition_id, "source_identifier": source_identifier,
              "issuer": issuer, "official_url": official_url,
              "problems": problems, "collected_at": at}
    if not problems:
        result["duplicado"] = False
        return result
    payload = json.dumps(result, ensure_ascii=False, sort_keys=True)
    with closing(connect_documents(db_path)) as conn, conn:
        existing = conn.execute(
            "SELECT id FROM eventos_documentais WHERE document_id=? "
            "AND event_type='identidade_pendente' AND note=?",
            (document_id, payload)).fetchone()
        if existing:
            result["event_id"] = existing[0]
            result["duplicado"] = True
            return result
        event_id = str(uuid4())
        conn.execute(
            "INSERT INTO eventos_documentais (id,document_id,version_id,event_type,occurred_at,"
            "note) VALUES (?,?,?,'identidade_pendente',?,?)",
            (event_id, document_id, version_id, at, payload))
    result["event_id"] = event_id
    result["duplicado"] = False
    return result


def normalize_legacy_policy_events(db_path, *, apply: bool = False) -> dict:
    """Reclassifica eventos antigos ``download_bloqueado`` de robots como ``politica_robots``.

    O evento original não é apagado: o tipo é corrigido (nenhuma requisição HTTP aconteceu) e
    a nota recebe ``reclassificado_de`` para manter a trilha.
    """
    with closing(connect_documents(db_path)) as conn:
        if not is_readable_schema(conn):
            raise ValueError("migração documental pendente")
        rows = []
        for event_id, note in conn.execute(
                "SELECT id, note FROM eventos_documentais "
                "WHERE event_type='download_bloqueado' ORDER BY occurred_at"):
            try:
                parsed = json.loads(note or "{}")
            except (TypeError, ValueError):
                continue
            if parsed.get("reason") in BLOCKED_REASON_LABELS:
                rows.append((event_id, parsed))
    report = {"total": len(rows), "apply": bool(apply)}
    if not apply or not rows:
        return report
    with closing(connect_documents(db_path)) as conn, conn:
        for event_id, parsed in rows:
            parsed["reclassificado_de"] = "download_bloqueado"
            conn.execute(
                "UPDATE eventos_documentais SET event_type='politica_robots', note=? "
                "WHERE id=? AND event_type='download_bloqueado'",
                (json.dumps(parsed, ensure_ascii=False, sort_keys=True), event_id))
    report["reclassificados"] = len(rows)
    return report


def retry_policy_documents(db_path, *, hosts, limit=10, delay_seconds=1.0,
                           dry_run=True, transport=None, sleep=None) -> dict:
    """Tenta baixar, **uma vez e em série**, documentos retidos por política de robots.

    Requisições normais, com timeout, limite de tamanho e sem qualquer evasão. Negativa
    (401/403), limite (429) e CAPTCHA interrompem o documento e ficam registrados. ``dry_run``
    apenas lista o que seria tentado.
    """
    from time import sleep as _sleep
    sleep = sleep or _sleep
    hosts = tuple(host for host in (hosts or ()) if host)
    if not hosts:
        raise ValueError("hosts autorizados obrigatórios")
    limit = int(limit)
    if limit < 1 or limit > 200:
        raise ValueError("limite fora da faixa")
    with closing(connect_documents(db_path)) as conn:
        if not is_readable_schema(conn):
            raise ValueError("migração documental pendente")
        candidates = []
        for document_id, url, title in conn.execute("""
                SELECT d.id, d.official_url, d.title FROM documentos d
                WHERE d.official_url LIKE 'https://anexos.cdn.selecao.net.br/%'
                  AND NOT EXISTS (SELECT 1 FROM versoes_documento v WHERE v.document_id=d.id)
                  AND NOT EXISTS (SELECT 1 FROM tentativas_download t
                                  WHERE t.document_id=d.id AND t.error_code IN
                                        ('acesso_negado','limite_acesso')
                                    AND t.attempted_at >= ?)
                ORDER BY d.contest_id, d.title, d.id LIMIT ?""",
                ((datetime.now(timezone.utc) - timedelta(hours=24)).isoformat(), limit)):
            candidates.append({"document_id": document_id, "official_url": url,
                               "title": title})
    report = {"version": INGEST_VERSION, "dry_run": bool(dry_run), "hosts": list(hosts),
              "candidatos": len(candidates), "baixados": 0, "falhas": [],
              "arquivo_invalido": 0, "acesso_negado": 0, "limite_acesso": 0,
              "falha_temporaria": 0}
    if dry_run:
        report["itens"] = candidates
        return report
    for index, item in enumerate(candidates):
        try:
            from radar.document_download import download_document
            download_document(db_path, item["document_id"], transport=transport,
                              allowed_hosts=hosts)
            report["baixados"] += 1
            try:
                check_download_identity(db_path, item["document_id"],
                                        _latest_version(db_path, item["document_id"]))
            except ValueError:
                pass
        except Exception as error:
            code = getattr(error, "code", "falha_temporaria")
            key = code if code in ("arquivo_invalido", "acesso_negado",
                                   "limite_acesso", "falha_temporaria") else "falha_temporaria"
            report[key] = report.get(key, 0) + 1
            report["falhas"].append({"document_id": item["document_id"], "code": code,
                                     "http_status": getattr(error, "http_status", None)})
            if code in ("acesso_negado", "limite_acesso"):
                report["interrompido"] = code
                break
        if index < len(candidates) - 1 and delay_seconds:
            sleep(delay_seconds)
    return report


def _latest_version(db_path, document_id: str):
    with closing(connect_documents(db_path)) as conn:
        row = conn.execute("SELECT id FROM versoes_documento WHERE document_id=? "
                           "ORDER BY fetched_at DESC, rowid DESC LIMIT 1",
                           (document_id,)).fetchone()
    return row[0] if row else None


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


# Nome anterior mantido para não quebrar chamadas existentes.
record_blocked_document = record_policy_block
blocked_report_alias = blocked_report
