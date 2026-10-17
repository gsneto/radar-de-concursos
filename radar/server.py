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
from urllib.parse import parse_qs, urlparse, urlsplit

from radar.document_store import get_competition_details, list_competition_identities, monitoring_status
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

    def __init__(self, server_address, db_path, config_path=None):
        super().__init__(server_address, _RadarRequestHandler)
        self.db_path = db_path
        self.config_path = config_path


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

    def _serve_monitoring(self):
        try:
            payload = monitoring_status(self.server.db_path)
        except (ValueError, sqlite3.Error):
            self._send(HTTPStatus.SERVICE_UNAVAILABLE, "application/json; charset=utf-8",
                       b'{"error":"Migracao documental pendente"}')
            return
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self._send(HTTPStatus.OK, "application/json; charset=utf-8", body)

    def _serve_confirmation(self):
        from radar.confirmation import queue_status
        try:
            payload = queue_status(self.server.db_path)
        except (ValueError, sqlite3.Error):
            self._send(HTTPStatus.SERVICE_UNAVAILABLE, "application/json; charset=utf-8",
                       b'{"error":"Migracao documental pendente"}')
            return
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self._send(HTTPStatus.OK, "application/json; charset=utf-8", body)

    def _serve_alerts(self, unseen_only, limit):
        from radar import ops
        try:
            payload = {"alerts": ops.list_alerts(self.server.db_path, unseen_only=unseen_only,
                                                 limit=limit),
                       "counts": ops.alert_counts(self.server.db_path)}
        except (ValueError, sqlite3.Error):
            self._send(HTTPStatus.SERVICE_UNAVAILABLE, "application/json; charset=utf-8",
                       b'{"error":"Migracao documental pendente"}')
            return
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self._send(HTTPStatus.OK, "application/json; charset=utf-8", body)

    def _serve_health(self):
        from radar import ops
        from radar.ops_config import load_config
        try:
            config = load_config()
            config["db_path"] = self.server.db_path
            payload = ops.health(config, check_server=False)
        except (ValueError, sqlite3.Error):
            self._send(HTTPStatus.SERVICE_UNAVAILABLE, "application/json; charset=utf-8",
                       b'{"error":"Migracao documental pendente"}')
            return
        body = json.dumps(payload, ensure_ascii=False, default=str).encode("utf-8")
        self._send(HTTPStatus.OK, "application/json; charset=utf-8", body)

    def _serve_priorities(self, limit):
        from radar import preferences, priority
        from radar.ops_config import load_config
        try:
            config = load_config(self.server.config_path)
            config["db_path"] = self.server.db_path
            prefs = preferences.load(config)
            payload = priority.prioritize(self.server.db_path, prefs, limit=limit)
        except (ValueError, sqlite3.Error):
            self._send(HTTPStatus.SERVICE_UNAVAILABLE, "application/json; charset=utf-8",
                       b'{"error":"Migracao documental pendente"}')
            return
        body = json.dumps(payload, ensure_ascii=False, default=str).encode("utf-8")
        self._send(HTTPStatus.OK, "application/json; charset=utf-8", body)

    def _serve_preferences(self):
        from radar import preferences
        from radar.ops_config import load_config
        payload = preferences.load(load_config(self.server.config_path))
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self._send(HTTPStatus.OK, "application/json; charset=utf-8", body)

    def _save_preferences(self):
        """POST /api/preferencias: valida e grava as preferências geográficas locais."""
        from radar import preferences
        from radar.ops_config import update_preferences
        try:
            length = int(self.headers.get("Content-Length") or 0)
        except (TypeError, ValueError):
            length = 0
        if length <= 0 or length > 4096:
            self._send_no_content(HTTPStatus.BAD_REQUEST)
            return
        try:
            payload = json.loads(self.rfile.read(length).decode("utf-8"))
        except (ValueError, UnicodeDecodeError):
            self._send_no_content(HTTPStatus.BAD_REQUEST)
            return
        try:
            saved = preferences.validate(payload)
        except preferences.PreferenceError as error:
            body = json.dumps({"error": str(error)}, ensure_ascii=False).encode("utf-8")
            self._send(HTTPStatus.BAD_REQUEST, "application/json; charset=utf-8", body)
            return
        try:
            update_preferences(saved, self.server.config_path)
        except (OSError, ValueError) as error:
            body = json.dumps({"error": f"não foi possível gravar as preferências: {type(error).__name__}"},
                              ensure_ascii=False).encode("utf-8")
            self._send(HTTPStatus.INTERNAL_SERVER_ERROR, "application/json; charset=utf-8", body)
            return
        body = json.dumps(saved, ensure_ascii=False).encode("utf-8")
        self._send(HTTPStatus.OK, "application/json; charset=utf-8", body)

    # --- Gestão de estudos (dados pessoais; rotas aditivas, v1 intacta) ------

    def _bad_request(self, message="requisição inválida"):
        body = json.dumps({"error": message}, ensure_ascii=False).encode("utf-8")
        self._send(HTTPStatus.BAD_REQUEST, "application/json; charset=utf-8", body)

    def _read_json(self, max_len=8192):
        """Lê e valida o corpo JSON da requisição; devolve ``dict`` ou ``None`` (já responde 400)."""
        try:
            length = int(self.headers.get("Content-Length") or 0)
        except (TypeError, ValueError):
            length = 0
        if length <= 0 or length > max_len:
            self._bad_request("corpo ausente ou grande demais")
            return None
        try:
            payload = json.loads(self.rfile.read(length).decode("utf-8"))
        except (ValueError, UnicodeDecodeError):
            self._bad_request("JSON inválido")
            return None
        if not isinstance(payload, dict):
            self._bad_request("corpo deve ser um objeto JSON")
            return None
        return payload

    def _serve_study(self, fn, *args, **kwargs):
        from radar import study_store
        try:
            payload = fn(self.server.db_path, *args, **kwargs)
        except ValueError as error:
            body = json.dumps({"error": str(error)}, ensure_ascii=False).encode("utf-8")
            self._send(HTTPStatus.BAD_REQUEST, "application/json; charset=utf-8", body)
            return
        except sqlite3.Error:
            self._send(HTTPStatus.SERVICE_UNAVAILABLE, "application/json; charset=utf-8",
                       b'{"error":"Migracao documental pendente"}')
            return
        body = json.dumps(payload, ensure_ascii=False, default=str).encode("utf-8")
        self._send(HTTPStatus.OK, "application/json; charset=utf-8", body)

    def _serve_triage(self, include_seen, limit):
        from radar import ops
        from radar.ops_config import load_config
        try:
            config = load_config()
            config["db_path"] = self.server.db_path
            payload = ops.triage(self.server.db_path, include_seen=include_seen, limit=limit,
                                 horizon_days=int(config.get("triage_horizon_days", 7)))
        except (ValueError, sqlite3.Error):
            self._send(HTTPStatus.SERVICE_UNAVAILABLE, "application/json; charset=utf-8",
                       b'{"error":"Migracao documental pendente"}')
            return
        body = json.dumps(payload, ensure_ascii=False, default=str).encode("utf-8")
        self._send(HTTPStatus.OK, "application/json; charset=utf-8", body)

    def _alert_action(self, alert_id):
        """POST /api/alertas/<id>: visto/dispensar/adiar (não apaga histórico)."""
        from radar import ops
        try:
            length = int(self.headers.get("Content-Length") or 0)
        except (TypeError, ValueError):
            length = 0
        if length <= 0 or length > 4096:
            self._send_no_content(HTTPStatus.BAD_REQUEST)
            return
        try:
            payload = json.loads(self.rfile.read(length).decode("utf-8"))
        except (ValueError, UnicodeDecodeError):
            self._send_no_content(HTTPStatus.BAD_REQUEST)
            return
        if not isinstance(payload, dict):
            self._send_no_content(HTTPStatus.BAD_REQUEST)
            return
        action = payload.get("action")
        seen = dismissed = None
        snooze_until = None
        if action == "seen":
            seen = True
        elif action == "dismiss":
            dismissed = True
        elif action == "reopen":
            seen = False
            dismissed = False
            snooze_until = ""
        elif action == "snooze":
            snooze_until = payload.get("until")
            if not isinstance(snooze_until, str) or not snooze_until:
                self._send_no_content(HTTPStatus.BAD_REQUEST)
                return
        else:
            self._send_no_content(HTTPStatus.BAD_REQUEST)
            return
        try:
            ok = ops.mark_alert(self.server.db_path, alert_id, seen=seen, dismissed=dismissed,
                                snooze_until=snooze_until)
        except ValueError:
            self._send_no_content(HTTPStatus.BAD_REQUEST)
            return
        except sqlite3.Error:
            self._send(HTTPStatus.SERVICE_UNAVAILABLE, "application/json; charset=utf-8",
                       b'{"error":"Migracao documental pendente"}')
            return
        if not ok:
            self._send_no_content(HTTPStatus.NOT_FOUND)
            return
        body = json.dumps({"id": alert_id, "action": action, "updated": True}).encode("utf-8")
        self._send(HTTPStatus.OK, "application/json; charset=utf-8", body)

    # --- Roteamento ----------------------------------------------------------

    def do_GET(self):
        from radar import study_store
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
        elif path == "/api/monitoramento":
            if parts.query:
                self._send_no_content(HTTPStatus.BAD_REQUEST)
            else:
                self._serve_monitoring()
        elif path == "/api/confirmacao":
            if parts.query:
                self._send_no_content(HTTPStatus.BAD_REQUEST)
            else:
                self._serve_confirmation()
        elif path == "/api/alertas":
            query = parse_qs(parts.query)
            unseen = query.get("unseen", ["0"])[0] in ("1", "true", "yes")
            try:
                limit = int(query.get("limit", ["50"])[0])
            except ValueError:
                self._send_no_content(HTTPStatus.BAD_REQUEST)
                return
            if set(query) - {"unseen", "limit"}:
                self._send_no_content(HTTPStatus.BAD_REQUEST)
            else:
                self._serve_alerts(unseen, limit)
        elif path == "/api/saude":
            if parts.query:
                self._send_no_content(HTTPStatus.BAD_REQUEST)
            else:
                self._serve_health()
        elif path == "/api/triagem":
            query = parse_qs(parts.query)
            try:
                limit = int(query.get("limit", ["200"])[0])
            except ValueError:
                self._send_no_content(HTTPStatus.BAD_REQUEST)
                return
            include_seen = query.get("include_seen", ["0"])[0] in ("1", "true", "yes")
            if set(query) - {"include_seen", "limit"}:
                self._send_no_content(HTTPStatus.BAD_REQUEST)
            else:
                self._serve_triage(include_seen, limit)
        elif path == "/api/prioridades":
            query = parse_qs(parts.query)
            try:
                limit = int(query.get("limit", ["200"])[0])
            except ValueError:
                self._send_no_content(HTTPStatus.BAD_REQUEST)
                return
            if limit < 1 or set(query) - {"limit"}:
                self._send_no_content(HTTPStatus.BAD_REQUEST)
            else:
                self._serve_priorities(limit)
        elif path == "/api/preferencias":
            if parts.query:
                self._send_no_content(HTTPStatus.BAD_REQUEST)
            else:
                self._serve_preferences()
        elif path == "/api/estudos/painel":
            if parts.query:
                self._send_no_content(HTTPStatus.BAD_REQUEST)
            else:
                self._serve_study(study_store.study_dashboard)
        elif path == "/api/estudos/disciplinas":
            if parts.query:
                self._send_no_content(HTTPStatus.BAD_REQUEST)
            else:
                self._serve_study(study_store.list_disciplinas)
        elif path == "/api/estudos/topicos":
            query = parse_qs(parts.query)
            if set(query) - {"disciplina_id"}:
                self._send_no_content(HTTPStatus.BAD_REQUEST)
            else:
                self._serve_study(study_store.list_topicos, query.get("disciplina_id", [None])[0])
        elif path == "/api/estudos/progresso":
            query = parse_qs(parts.query)
            if set(query) - {"contest_id"}:
                self._send_no_content(HTTPStatus.BAD_REQUEST)
            else:
                self._serve_study(study_store.list_progresso,
                                  contest_id=query.get("contest_id", [""])[0])
        elif path == "/api/estudos/sessoes":
            query = parse_qs(parts.query)
            try:
                limit = int(query.get("limit", ["50"])[0])
            except ValueError:
                self._send_no_content(HTTPStatus.BAD_REQUEST)
                return
            if limit < 1 or set(query) - {"limit"}:
                self._send_no_content(HTTPStatus.BAD_REQUEST)
            else:
                self._serve_study(study_store.list_sessions, limit=limit)
        elif path == "/api/estudos/sessao-atual":
            if parts.query:
                self._send_no_content(HTTPStatus.BAD_REQUEST)
            else:
                self._serve_study(study_store.current_session)
        elif path == "/api/estudos/revisoes":
            if parts.query:
                self._send_no_content(HTTPStatus.BAD_REQUEST)
            else:
                self._serve_study(study_store.pending_revisions)
        elif path in ("/", "/index.html"):
            self._serve_file("index.html")
        elif path in _ASSET_ROUTES:
            self._serve_file(_ASSET_ROUTES[path])
        else:
            self._send_no_content(HTTPStatus.NOT_FOUND)

    def _method_not_allowed(self, allow="GET"):
        self._send_no_content(HTTPStatus.METHOD_NOT_ALLOWED, {"Allow": allow})

    def do_POST(self):
        from radar import study_store
        parts = urlsplit(self.path)
        path = parts.path
        if path.startswith("/api/alertas/") and not parts.query:
            alert_id = path[len("/api/alertas/"):]
            if alert_id and "/" not in alert_id:
                self._alert_action(alert_id)
                return
        if path == "/api/preferencias":
            if parts.query:
                self._send_no_content(HTTPStatus.BAD_REQUEST)
            else:
                self._save_preferences()
            return
        if path == "/api/estudos/disciplinas":
            if parts.query:
                self._send_no_content(HTTPStatus.BAD_REQUEST)
                return
            body = self._read_json()
            if body is not None:
                self._serve_study(study_store.create_disciplina, body.get("nome"))
            return
        if path == "/api/estudos/topicos":
            if parts.query:
                self._send_no_content(HTTPStatus.BAD_REQUEST)
                return
            body = self._read_json()
            if body is not None:
                self._serve_study(study_store.create_topico, body.get("disciplina_id"),
                                  body.get("nome"), body.get("parent_id"))
            return
        if path == "/api/estudos/progresso":
            if parts.query:
                self._send_no_content(HTTPStatus.BAD_REQUEST)
                return
            body = self._read_json()
            if body is not None:
                self._serve_study(study_store.set_progress, body.get("topico_id"),
                                  body.get("state"), contest_id=body.get("contest_id") or "")
            return
        if path == "/api/estudos/sessoes":
            if parts.query:
                self._send_no_content(HTTPStatus.BAD_REQUEST)
                return
            body = self._read_json()
            if body is None:
                return
            action = body.get("action")
            if action == "start":
                self._serve_study(study_store.start_session,
                                  disciplina_id=body.get("disciplina_id"),
                                  topico_id=body.get("topico_id"),
                                  contest_id=body.get("contest_id") or "",
                                  modo=body.get("modo") or "livre")
            elif action == "pause":
                self._serve_study(study_store.pause_session, body.get("id"))
            elif action == "resume":
                self._serve_study(study_store.resume_session, body.get("id"))
            elif action == "finish":
                self._serve_study(study_store.finish_session, body.get("id"))
            elif action == "discard":
                self._serve_study(study_store.discard_session, body.get("id"))
            else:
                self._send_no_content(HTTPStatus.BAD_REQUEST)
            return
        if path == "/api/estudos/revisoes":
            if parts.query:
                self._send_no_content(HTTPStatus.BAD_REQUEST)
                return
            body = self._read_json()
            if body is not None:
                self._serve_study(study_store.mark_revision_done, body.get("progresso_id"),
                                  resultado=body.get("resultado"))
            return
        self._method_not_allowed()

    def do_PUT(self):
        self._verb_not_allowed()

    def do_DELETE(self):
        self._verb_not_allowed()

    def do_PATCH(self):
        self._verb_not_allowed()

    def _verb_not_allowed(self):
        path = urlsplit(self.path).path
        post_paths = ("/api/preferencias", "/api/estudos/disciplinas", "/api/estudos/topicos",
                      "/api/estudos/progresso", "/api/estudos/sessoes")
        allow = "GET, POST" if path in post_paths else "GET"
        self._method_not_allowed(allow)

    def do_HEAD(self):
        if self.path.startswith('/api/concursos/'):
            self._method_not_allowed()
        else:
            self._send_no_content(HTTPStatus.METHOD_NOT_ALLOWED, {'Allow': 'GET'})


def create_server(db_path, host="127.0.0.1", port=8000, config_path=None):
    """Cria e retorna o servidor HTTP configurado, sem iniciar serve_forever.

    O servidor liga o socket em ``(host, port)`` (use ``port=0`` para porta
    efêmera em testes), mas fica a cargo do chamador chamar ``serve_forever``.
    ``config_path`` aponta para o ``radar_ops.json`` (preferências); ``None`` usa o padrão.
    """
    return _RadarHTTPServer((host, port), db_path, config_path)
