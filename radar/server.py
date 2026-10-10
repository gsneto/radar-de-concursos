"""Servidor HTTP loopback do Radar de Concursos (somente stdlib).

Expõe:
- ``GET /api/concursos`` → array JSON do contrato v1 lido de ``list_records``;
- ``GET /`` → página estática ``web/index.html``;
- ``GET /styles.css`` e ``GET /app.js`` (e variantes ``/web/...``) → assets locais;
- métodos de escrita (POST/PUT/DELETE/PATCH) → 405 com ``Allow: GET``;
- caminhos desconhecidos (incluindo tentativas de path traversal) → 404.

``create_server(db_path, host='127.0.0.1', port=8000)`` retorna o servidor
configurado, sem chamar ``serve_forever`` (fica a cargo do chamador).
Somente loopback por padrão; nunca faz bind em interfaces públicas sem pedido.
"""

from __future__ import annotations

import json
import sqlite3
from uuid import UUID
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from urllib.parse import urlparse, urlsplit

from radar.document_store import get_competition_details, list_competition_identities
from radar.storage import list_records

# Diretório web: irmão do pacote ``radar`` (raiz do projeto).
WEB_DIR = Path(__file__).resolve().parent.parent / "web"

_CONTENT_TYPES = {
    "index.html": "text/html; charset=utf-8",
    "styles.css": "text/css; charset=utf-8",
    "app.js": "application/javascript; charset=utf-8",
}

# Rotas de assets, aceitando também o prefixo ``/web/``.
_ASSET_ROUTES = {
    "/styles.css": "styles.css",
    "/web/styles.css": "styles.css",
    "/app.js": "app.js",
    "/web/app.js": "app.js",
}


class _RadarHTTPServer(HTTPServer):
    """HTTPServer que carrega o caminho do banco para o handler."""

    def __init__(self, server_address, db_path):
        super().__init__(server_address, _RadarRequestHandler)
        self.db_path = db_path


class _RadarRequestHandler(BaseHTTPRequestHandler):
    server_version = "RadarConcursos/0.1"

    # Silencia o log por requisição (útil em testes e em uso local discreto).
    def log_message(self, format, *args):
        return

    # --- Helpers de resposta -------------------------------------------------

    def _send(self, status, content_type, body_bytes):
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body_bytes)))
        self.end_headers()
        self.wfile.write(body_bytes)

    def _send_no_content(self, status, headers=None):
        self.send_response(status)
        for name, value in (headers or {}).items():
            self.send_header(name, value)
        self.send_header("Content-Length", "0")
        self.end_headers()

    def _serve_file(self, filename: str):
        # filename vem de rotas fixas; resolve contra o diretório web e exige
        # que o resultado permaneça dentro dele (bloqueia path traversal).
        web_root = WEB_DIR.resolve()
        candidate = (web_root / filename).resolve()
        if web_root != candidate and web_root not in candidate.parents:
            self._send_no_content(HTTPStatus.NOT_FOUND)
            return
        if not candidate.is_file():
            self._send_no_content(HTTPStatus.NOT_FOUND)
            return
        content_type = _CONTENT_TYPES.get(filename, "application/octet-stream")
        self._send(HTTPStatus.OK, content_type, candidate.read_bytes())

    def _serve_api(self):
        try:
            payload = list_records(self.server.db_path)
        except sqlite3.Error:
            body = json.dumps({"error": "Falha ao consultar dados locais"}).encode("utf-8")
            self._send(HTTPStatus.INTERNAL_SERVER_ERROR, "application/json; charset=utf-8", body)
            return
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self._send(
            HTTPStatus.OK, "application/json; charset=utf-8", body
        )

    def _serve_document_api(self, contest_id=None):
        try:
            if contest_id is None:
                payload = list_competition_identities(self.server.db_path)
            else:
                payload = get_competition_details(self.server.db_path, contest_id)
        except (ValueError, sqlite3.Error):
            self._send(HTTPStatus.SERVICE_UNAVAILABLE, "application/json; charset=utf-8",
                       b'{"error":"Migracao documental pendente"}')
            return
        if payload is None:
            self._send_no_content(HTTPStatus.NOT_FOUND)
            return
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self._send(HTTPStatus.OK, "application/json; charset=utf-8", body)

    # --- Roteamento ----------------------------------------------------------

    def do_GET(self):
        parts = urlsplit(self.path)
        path = parts.path
        if path == "/api/concursos":
            self._serve_api()
        elif path == "/api/concursos/identidades":
            if parts.query:
                self._send_no_content(HTTPStatus.BAD_REQUEST)
            else:
                self._serve_document_api()
        elif path.startswith("/api/concursos/") and path.endswith("/detalhes"):
            segment = path[len("/api/concursos/"):-len("/detalhes")]
            try:
                contest_id = str(UUID(segment))
                if segment != contest_id or parts.query:
                    raise ValueError("UUID ou query inválida")
            except ValueError:
                self._send_no_content(HTTPStatus.BAD_REQUEST)
            else:
                self._serve_document_api(contest_id)
        elif path in ("/", "/index.html"):
            self._serve_file("index.html")
        elif path in _ASSET_ROUTES:
            self._serve_file(_ASSET_ROUTES[path])
        else:
            self._send_no_content(HTTPStatus.NOT_FOUND)

    def _method_not_allowed(self):
        self._send_no_content(HTTPStatus.METHOD_NOT_ALLOWED, {"Allow": "GET"})

    def do_POST(self):
        self._method_not_allowed()

    def do_PUT(self):
        self._method_not_allowed()

    def do_DELETE(self):
        self._method_not_allowed()

    def do_PATCH(self):
        self._method_not_allowed()

    def do_HEAD(self):
        if self.path.startswith('/api/concursos/'):
            self._method_not_allowed()
        else:
            self._send_no_content(HTTPStatus.METHOD_NOT_ALLOWED, {'Allow': 'GET'})


def create_server(db_path, host="127.0.0.1", port=8000):
    """Cria e retorna o servidor HTTP configurado, sem iniciar serve_forever.

    O servidor liga o socket em ``(host, port)`` (use ``port=0`` para porta
    efêmera em testes), mas fica a cargo do chamador chamar ``serve_forever``.
    """
    return _RadarHTTPServer((host, port), db_path)
