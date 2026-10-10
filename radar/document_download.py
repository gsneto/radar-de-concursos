"""Download documental validado; transporte precisa expor endereço peer verificável."""

from __future__ import annotations

import ipaddress
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


def fetch_document(url: str, timeout: int, limit: int) -> dict:
    """Conecta somente ao IP público resolvido, com TLS para o host permitido."""
    deadline = time.monotonic() + timeout
    visited = set()
    for _ in range(4):
        if not allowed_document_url(url) or url in visited:
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
                raise ValueError("resposta HTTP não íntegra")
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


def download_document(db_path, document_id: str, transport=None) -> str:
    with closing(connect_documents(db_path)) as conn:
        found = conn.execute("SELECT official_url FROM documentos WHERE id=?", (document_id,)).fetchone()
    if not found:
        raise ValueError("documento não encontrado")
    url = found[0]
    attempt_id = str(uuid4())
    now = datetime.now(timezone.utc).isoformat()
    try:
        if not allowed_document_url(url):
            raise ValueError("URL não autorizada")
        if transport is None:
            transport = fetch_document
        response = transport(url, timeout=15, limit=MAX_BYTES)
        if response["status"] != 200:
            raise ValueError("resposta HTTP não íntegra")
        if not allowed_document_url(response["final_url"]):
            raise ValueError("redirecionamento não validado")
        if not ipaddress.ip_address(response["peer_ip"]).is_global:
            raise ValueError("endereço peer não público")
        if response["content_type"].split(";", 1)[0].lower() not in {"text/html", "application/pdf"}:
            raise ValueError("MIME não suportado")
        if urlsplit(url).path.lower().endswith('.pdf') and response["content_type"].split(";", 1)[0].lower() == 'text/html':
            raise ValueError("HTML inesperado para documento PDF")
        content = response["body"]
        if not isinstance(content, bytes) or not content or len(content) > MAX_BYTES:
            raise ValueError("conteúdo vazio ou excede limite")
        if response["content_type"].split(";", 1)[0].lower() == "application/pdf" and not content.startswith(b"%PDF-"):
            raise ValueError("assinatura PDF ausente")
        version = record_version(db_path, document_id, content, dict(fetched_at=now,
                                 fetched_url=response["final_url"], content_type=response["content_type"]))
    except Exception as error:
        with closing(connect_documents(db_path)) as conn:
            conn.execute("INSERT INTO tentativas_download VALUES (?,?,?,?,?,?,?)",
                         (attempt_id, document_id, now, "falhou", None, type(error).__name__, None))
            conn.execute("INSERT INTO eventos_documentais (id,document_id,event_type,occurred_at,note) VALUES (?,?,'falha',?,?)",
                         (str(uuid4()), document_id, now, type(error).__name__))
            conn.commit()
        raise
    with closing(connect_documents(db_path)) as conn:
        conn.execute("UPDATE documentos SET final_url=?,last_checked_at=? WHERE id=?",
                     (response["final_url"], now, document_id))
        conn.execute("INSERT INTO tentativas_download VALUES (?,?,?,?,?,?,?)",
                     (attempt_id, document_id, now, "concluido", 200, None, response["final_url"]))
        conn.commit()
    return version
