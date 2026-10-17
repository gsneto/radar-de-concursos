"""Download documental validado; transporte precisa expor endereço peer verificável."""

from __future__ import annotations

import ipaddress
import json
import http.client
import socket
import time
from contextlib import closing
from datetime import datetime, timezone
from urllib.parse import urljoin, urlsplit
from uuid import uuid4

from radar.document_discovery import allowed_document_url
from radar.document_store import connect_documents, record_version


MAX_BYTES = 20 * 1024 * 1024

# Classificação de falha: distingue política de acesso, limite, erro temporário e arquivo
# inválido. Nenhuma dessas categorias autoriza tentativa de evasão (proxy, UA falso etc.).
DENIED_STATUSES = (401, 403)
RATE_LIMIT_STATUSES = (429,)
TRANSIENT_STATUSES = (500, 502, 503, 504)


class DownloadError(ValueError):
    """Falha de download com código estável e status HTTP quando existir."""

    def __init__(self, code: str, message: str, http_status=None):
        super().__init__(message)
        self.code = code
        self.http_status = http_status


class _PinnedHTTPSConnection(http.client.HTTPSConnection):
    def __init__(self, host: str, ip: str, timeout: float):
        super().__init__(host, timeout=timeout)
        self.ip = ip

    def connect(self):
        raw = socket.create_connection((self.ip, 443), self.timeout)
        try:
            self.sock = self._context.wrap_socket(raw, server_hostname=self.host)
        except BaseException:
            raw.close()
            raise


def fetch_document(url: str, timeout: int, limit: int, *, extra_hosts=None) -> dict:
    """Conecta somente ao IP público resolvido, com TLS para o host permitido."""
    deadline = time.monotonic() + timeout
    visited = set()
    for _ in range(4):
        if not allowed_document_url(url, extra_hosts=extra_hosts) or url in visited:
            raise ValueError("URL ou redirecionamento não autorizado")
        visited.add(url)
        parts = urlsplit(url)
        addresses = socket.getaddrinfo(parts.hostname, 443, type=socket.SOCK_STREAM)
        if not addresses or any(not ipaddress.ip_address(item[4][0]).is_global for item in addresses):
            raise ValueError("resolução DNS não pública")
        ip = addresses[0][4][0]
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            raise TimeoutError("prazo do download expirou")
        connection = _PinnedHTTPSConnection(parts.hostname, ip, remaining)
        try:
            path = parts.path or "/"
            if parts.query:
                path += "?" + parts.query
            connection.request("GET", path, headers={"User-Agent": "radar-de-concursos/0.1", "Accept": "application/pdf,text/html"})
            response = connection.getresponse()
            peer_ip = connection.sock.getpeername()[0]
            if peer_ip != ip or not ipaddress.ip_address(peer_ip).is_global:
                raise ValueError("peer distinto do IP público resolvido")
            if response.status in (301, 302, 303, 307, 308):
                location = response.getheader("Location")
                if not location:
                    raise ValueError("redirecionamento sem destino")
                url = urljoin(url, location)
                continue
            content_type = response.getheader("Content-Type", "")
            if response.status != 200:
                if response.status in DENIED_STATUSES:
                    raise DownloadError("acesso_negado", "acesso negado pela fonte",
                                        response.status)
                if response.status in RATE_LIMIT_STATUSES:
                    raise DownloadError("limite_acesso", "fonte sinalizou limite de acesso",
                                        response.status)
                if response.status in TRANSIENT_STATUSES:
                    raise DownloadError("falha_temporaria", "erro temporário da fonte",
                                        response.status)
                raise DownloadError("http_invalido", "resposta HTTP não íntegra",
                                    response.status)
            if response.getheader("Content-Length") and int(response.getheader("Content-Length")) > limit:
                raise ValueError("conteúdo excede limite")
            body = bytearray()
            while True:
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    raise TimeoutError("prazo do download expirou")
                connection.sock.settimeout(remaining)
                chunk = response.read(min(65536, limit + 1 - len(body)))
                if not chunk:
                    break
                body.extend(chunk)
                if len(body) > limit:
                    raise ValueError("conteúdo excede limite")
            return dict(status=response.status, final_url=url, content_type=content_type,
                        peer_ip=peer_ip, body=bytes(body))
        finally:
            connection.close()
    raise ValueError("limite de redirecionamentos excedido")


def _is_transient(error: Exception) -> bool:
    if isinstance(error, DownloadError):
        return error.code == "falha_temporaria"
    return isinstance(error, (TimeoutError, ConnectionError, OSError))


def download_document(db_path, document_id: str, transport=None, *, allowed_hosts=None,
                      attempts: int = 2, backoff_seconds: float = 1.0,
                      sleep=time.sleep) -> str:
    """Baixa e valida um documento.

    ``allowed_hosts`` é um conjunto **explicitamente** autorizado pelo conector que chamou
    (ex.: CDN de anexos do IBFC). Sem ele, vale somente a lista global — o comportamento dos
    outros conectores não muda.

    Erros transitórios (5xx, timeout, conexão) são tentados no máximo ``attempts`` vezes com
    backoff. Acesso negado (401/403) e limite (429) **não** são repetidos: a resposta real é
    registrada e a tentativa para.
    """
    extra = tuple(allowed_hosts or ())
    with closing(connect_documents(db_path)) as conn:
        found = conn.execute("SELECT official_url FROM documentos WHERE id=?", (document_id,)).fetchone()
    if not found:
        raise ValueError("documento não encontrado")
    url = found[0]
    attempt_id = str(uuid4())
    now = datetime.now(timezone.utc).isoformat()
    if transport is None:
        if extra:
            transport = lambda target, timeout, limit: fetch_document(
                target, timeout, limit, extra_hosts=extra)
        else:
            transport = fetch_document
    if not allowed_document_url(url, extra_hosts=extra):
        raise DownloadError("url_nao_autorizada", "URL não autorizada")

    attempts = max(1, int(attempts))
    response = None
    last_error = None
    for index in range(attempts):
        try:
            response = transport(url, timeout=15, limit=MAX_BYTES)
            if response["status"] != 200:
                status = response["status"]
                if status in DENIED_STATUSES:
                    raise DownloadError("acesso_negado", "acesso negado pela fonte", status)
                if status in RATE_LIMIT_STATUSES:
                    raise DownloadError("limite_acesso", "fonte sinalizou limite de acesso", status)
                if status in TRANSIENT_STATUSES:
                    raise DownloadError("falha_temporaria", "erro temporário da fonte", status)
                raise DownloadError("http_invalido", "resposta HTTP não íntegra", status)
            last_error = None
            break
        except DownloadError as error:
            last_error = error
            if not _is_transient(error) or index == attempts - 1:
                break
        except Exception as error:  # timeout/conexão: transitório, com backoff
            last_error = error
            if not _is_transient(error) or index == attempts - 1:
                break
        if backoff_seconds:
            sleep(backoff_seconds * (index + 1))
    if last_error is not None:
        code = getattr(last_error, "code", "falha_temporaria")
        status = getattr(last_error, "http_status", None)
        with closing(connect_documents(db_path)) as conn, conn:
            conn.execute("INSERT INTO tentativas_download VALUES (?,?,?,?,?,?,?)",
                         (attempt_id, document_id, now, "falhou", status, code, None))
            conn.execute(
                "INSERT INTO eventos_documentais (id,document_id,event_type,occurred_at,note) "
                "VALUES (?,?,'falha',?,?)",
                (str(uuid4()), document_id, now, json.dumps(
                    {"code": code, "http_status": status,
                     "error": type(last_error).__name__}, ensure_ascii=False)))
        raise last_error if isinstance(last_error, DownloadError) else DownloadError(
            code, str(last_error))

    try:
        if not allowed_document_url(response["final_url"], extra_hosts=extra):
            raise DownloadError("url_nao_autorizada", "redirecionamento não validado")
        if not ipaddress.ip_address(response["peer_ip"]).is_global:
            raise DownloadError("url_nao_autorizada", "endereço peer não público")
        content_type = response["content_type"].split(";", 1)[0].lower()
        if content_type not in {"text/html", "application/pdf"}:
            raise DownloadError("arquivo_invalido", "MIME não suportado")
        if urlsplit(url).path.lower().endswith('.pdf') and content_type == 'text/html':
            raise DownloadError("arquivo_invalido", "HTML inesperado para documento PDF")
        content = response["body"]
        if not isinstance(content, bytes) or not content or len(content) > MAX_BYTES:
            raise DownloadError("arquivo_invalido", "conteúdo vazio ou excede limite")
        if content_type == "application/pdf" and not content.startswith(b"%PDF-"):
            raise DownloadError("arquivo_invalido", "assinatura PDF ausente")
        version = record_version(db_path, document_id, content, dict(fetched_at=now,
                                 fetched_url=response["final_url"], content_type=response["content_type"]))
    except DownloadError as error:
        with closing(connect_documents(db_path)) as conn, conn:
            conn.execute("INSERT INTO tentativas_download VALUES (?,?,?,?,?,?,?)",
                         (attempt_id, document_id, now, "falhou", error.http_status,
                          error.code, None))
            conn.execute(
                "INSERT INTO eventos_documentais (id,document_id,event_type,occurred_at,note) "
                "VALUES (?,?,'falha',?,?)",
                (str(uuid4()), document_id, now, json.dumps(
                    {"code": error.code, "http_status": error.http_status}, ensure_ascii=False)))
        raise
    except Exception as error:
        # Falha de persistência (disco/DB) também precisa ficar auditável.
        with closing(connect_documents(db_path)) as conn, conn:
            conn.execute("INSERT INTO tentativas_download VALUES (?,?,?,?,?,?,?)",
                         (attempt_id, document_id, now, "falhou", None,
                          "falha_persistencia", None))
            conn.execute(
                "INSERT INTO eventos_documentais (id,document_id,event_type,occurred_at,note) "
                "VALUES (?,?,'falha',?,?)",
                (str(uuid4()), document_id, now, json.dumps(
                    {"code": "falha_persistencia", "error": type(error).__name__},
                    ensure_ascii=False)))
        raise
    with closing(connect_documents(db_path)) as conn, conn:
        conn.execute("UPDATE documentos SET final_url=?,last_checked_at=? WHERE id=?",
                     (response["final_url"], now, document_id))
        conn.execute("INSERT INTO tentativas_download VALUES (?,?,?,?,?,?,?)",
                     (attempt_id, document_id, now, "concluido", 200, None, response["final_url"]))
    return version
