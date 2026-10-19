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

import base64
import binascii
import json
import sqlite3
from uuid import UUID
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, unquote, urlparse, urlsplit

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


class _RadarHTTPServer(ThreadingHTTPServer):
    """Servidor concorrente que carrega o caminho do banco para o handler.

    Cada requisição abre a própria conexão SQLite. Sem threads, um painel lento (contexto
    de quadro) bloqueia todos os outros e a revisão parece travada. Escritas continuam
    serializadas pelo `BEGIN IMMEDIATE` do SQLite.
    """

    daemon_threads = True
    allow_reuse_address = True

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

    def _send(self, status, content_type, body_bytes, headers=None):
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body_bytes)))
        for name, value in (headers or {}).items():
            self.send_header(name, value)
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

    def _drain(self, length, *, limit=64 * 1024 * 1024):
        """Consome o corpo rejeitado (até um teto) para o cliente receber a resposta HTTP."""
        remaining = min(int(length or 0), limit)
        while remaining > 0:
            chunk = self.rfile.read(min(65536, remaining))
            if not chunk:
                break
            remaining -= len(chunk)

    def _read_json(self, max_len=8192):
        """Lê e valida o corpo JSON da requisição; devolve ``dict`` ou ``None`` (já responde 400)."""
        try:
            length = int(self.headers.get("Content-Length") or 0)
        except (TypeError, ValueError):
            length = 0
        if length <= 0 or length > max_len:
            if length > max_len:
                self._drain(length)
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
        except (ValueError, TypeError, KeyError, AttributeError) as error:
            body = json.dumps({"error": str(error) or "requisição inválida"},
                              ensure_ascii=False).encode("utf-8")
            self._send(HTTPStatus.BAD_REQUEST, "application/json; charset=utf-8", body)
            return
        except sqlite3.Error:
            self._send(HTTPStatus.SERVICE_UNAVAILABLE, "application/json; charset=utf-8",
                       b'{"error":"Migracao documental pendente"}')
            return
        body = json.dumps(payload, ensure_ascii=False, default=str).encode("utf-8")
        self._send(HTTPStatus.OK, "application/json; charset=utf-8", body)

    def _review_queue(self, parts):
        """Fila de revisão com filtros explícitos; parâmetro desconhecido é recusado."""
        from radar import review
        query = parse_qs(parts.query)
        allowed = {"limit", "offset", "state", "contest_id", "role_id", "field",
                   "document_id", "source", "conflict", "min_priority", "since", "until",
                   "reviewed_since", "reviewed_until", "search"}
        if set(query) - allowed:
            self._bad_request("parâmetros inválidos")
            return
        try:
            limit = int(query.get("limit", ["25"])[0])
            offset = int(query.get("offset", ["0"])[0])
            min_priority = (int(query["min_priority"][0])
                            if "min_priority" in query else None)
        except ValueError:
            self._bad_request("parâmetros inválidos")
            return
        conflict = query.get("conflict", [None])[0]
        if conflict is not None:
            if conflict in ("1", "true", "yes"):
                conflict = True
            elif conflict in ("0", "false", "no"):
                conflict = False
            else:
                self._bad_request("conflict inválido")
                return
        self._serve_study(
            review.review_queue, limit=limit, offset=offset,
            state=query.get("state", ["pendente"])[0],
            contest_id=query.get("contest_id", [None])[0],
            role_id=query.get("role_id", [None])[0],
            field_name=query.get("field", [None])[0],
            document_id=query.get("document_id", [None])[0],
            source=query.get("source", [None])[0],
            conflict=conflict, min_priority=min_priority,
            since=query.get("since", [None])[0], until=query.get("until", [None])[0],
            reviewed_since=query.get("reviewed_since", [None])[0],
            reviewed_until=query.get("reviewed_until", [None])[0],
            search=(query.get("search") or [None])[0])

    def _serve_media(self, media_id):
        """Serve a imagem do flashcard com `Content-Type` fixo (nunca inferido do cliente)."""
        from radar import media, practice_store
        meta = practice_store.get_media(self.server.db_path, media_id)
        if meta is None:
            self._send_no_content(HTTPStatus.NOT_FOUND)
            return
        payload = media.read_media(self.server.db_path, meta["sha256"], meta["extensao"])
        if payload is None:
            self._send(HTTPStatus.NOT_FOUND, "application/json; charset=utf-8",
                       b'{"error":"arquivo de midia ausente"}')
            return
        self._send(HTTPStatus.OK, meta["mime"], payload,
                   {"X-Content-Type-Options": "nosniff",
                    "Cache-Control": "private, max-age=3600"})

    def _decode_base64(self, value, *, max_bytes):
        """Decodifica base64 do corpo JSON com limite; responde 400 e devolve ``None`` se inválido."""
        if not isinstance(value, str) or not value:
            self._bad_request("conteúdo base64 obrigatório")
            return None
        if len(value) > (max_bytes * 4 // 3) + 16:
            self._bad_request("conteúdo acima do limite")
            return None
        try:
            payload = base64.b64decode(value, validate=True)
        except (binascii.Error, ValueError):
            self._bad_request("base64 inválido")
            return None
        if len(payload) > max_bytes:
            self._bad_request("conteúdo acima do limite")
            return None
        return payload

    def _serve_exam(self, loader):
        """Resposta de simulado com códigos corretos: 404 ausente, 409 em andamento, 200 ok."""
        try:
            payload = loader()
        except ValueError as error:
            message = str(error)
            if "inexistente" in message:
                self._send(HTTPStatus.NOT_FOUND, "application/json; charset=utf-8",
                           json.dumps({"error": message}, ensure_ascii=False).encode("utf-8"))
                return
            status = HTTPStatus.CONFLICT if "em andamento" in message else HTTPStatus.BAD_REQUEST
            self._send(status, "application/json; charset=utf-8",
                       json.dumps({"error": message}, ensure_ascii=False).encode("utf-8"))
            return
        except sqlite3.Error:
            self._send(HTTPStatus.SERVICE_UNAVAILABLE, "application/json; charset=utf-8",
                       b'{"error":"Migracao documental pendente"}')
            return
        if payload is None:
            self._send_no_content(HTTPStatus.NOT_FOUND)
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
        from radar import study_store, knowledge_store, study_backup, practice_store, packages
        from radar import data_quality
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
        elif path == "/api/identidade":
            if parts.query:
                self._send_no_content(HTTPStatus.BAD_REQUEST)
            else:
                from radar import identity
                self._serve_study(identity.identity_audit)
        elif path == "/api/associacoes/fila":
            query = parse_qs(parts.query)
            try:
                limit = int(query.get("limit", ["50"])[0])
            except ValueError:
                self._bad_request("limit inválido")
                return
            state = query.get("state", [None])[0]
            from radar import identity
            if (limit < 1 or set(query) - {"limit", "state"}
                    or (state is not None and state not in identity.ASSOCIATION_STATES)):
                self._bad_request("parâmetros inválidos")
                return
            self._serve_study(identity.association_queue, limit=limit, state=state)
        elif path == "/api/associacoes":
            if parts.query:
                self._send_no_content(HTTPStatus.BAD_REQUEST)
            else:
                from radar import association
                self._serve_study(association.suspect_associations)
        elif path == "/api/pipeline":
            if parts.query:
                self._bad_request("parâmetros inválidos")
                return
            from radar import pipeline
            self._serve_study(pipeline.pipeline_summary)
        elif path == "/api/pipeline/continuidade":
            if parts.query:
                self._bad_request("parâmetros inválidos")
                return
            from radar import table_continuity
            self._serve_study(table_continuity.continuity_report_all)
        elif path == "/api/oportunidades":
            from radar import coverage_states
            query = parse_qs(parts.query)
            allowed = {"limit", "offset", "field", "conflict", "document_state", "has_page",
                       "search", "min_priority", "contest_id"}
            if set(query) - allowed:
                self._bad_request("parâmetros inválidos")
                return
            try:
                limit = int(query.get("limit", ["50"])[0])
                offset = int(query.get("offset", ["0"])[0])
                min_priority = (int(query["min_priority"][0])
                                if "min_priority" in query else None)
            except ValueError:
                self._bad_request("parâmetros inválidos")
                return
            def _bool(name):
                value = query.get(name, [None])[0]
                if value is None or value == "":
                    return None
                if value in ("1", "true", "yes"):
                    return True
                if value in ("0", "false", "no"):
                    return False
                raise ValueError(f"{name} inválido")
            try:
                conflict = _bool("conflict")
                has_page = _bool("has_page")
            except ValueError as error:
                self._bad_request(str(error))
                return
            document_state = query.get("document_state", [None])[0]
            if document_state and document_state not in coverage_states.STATE_ORDER:
                self._bad_request("estado documental inválido")
                return
            from radar import opportunities
            self._serve_study(opportunities.opportunity_list, limit=limit, offset=offset,
                              field=query.get("field", [None])[0], conflict=conflict,
                              document_state=document_state,
                              has_page=has_page, search=query.get("search", [None])[0],
                              min_priority=min_priority,
                              contest_id=query.get("contest_id", [None])[0])
        elif path == "/api/documentos/nominais":
            query = parse_qs(parts.query)
            if set(query) - {"limit", "offset"}:
                self._bad_request("parâmetros inválidos")
                return
            try:
                limit = int(query.get("limit", ["200"])[0])
                offset = int(query.get("offset", ["0"])[0])
            except ValueError:
                self._bad_request("parâmetros inválidos")
                return
            from radar import nominal_triage
            self._serve_study(nominal_triage.nominal_triage, limit=limit, offset=offset)
        elif path == "/api/linha-do-tempo":
            query = parse_qs(parts.query)
            if set(query) - {"since", "limit"}:
                self._bad_request("parâmetros inválidos")
                return
            try:
                limit = int(query.get("limit", ["200"])[0])
            except ValueError:
                self._bad_request("parâmetros inválidos")
                return
            from radar import timeline
            self._serve_study(timeline.timeline, since=(query.get("since") or [None])[0],
                              limit=limit)
        elif path.startswith("/api/revisao/evidencia/"):
            proposal_id = unquote(path[len("/api/revisao/evidencia/"):])
            if not proposal_id or "/" in proposal_id or parts.query:
                self._bad_request("proposta inválida")
                return
            from radar import opportunities
            self._serve_study(opportunities.proposal_evidence, proposal_id)
        elif path.startswith("/api/oportunidades/"):
            contest_id = unquote(path[len("/api/oportunidades/"):])
            if not contest_id or "/" in contest_id:
                self._bad_request("concurso inválido")
                return
            query = parse_qs(parts.query)
            if set(query) - {"role_id", "scope"}:
                self._bad_request("parâmetros inválidos")
                return
            from radar import opportunities
            self._serve_study(opportunities.opportunity_dossier, contest_id,
                              role_id=(query.get("role_id") or [None])[0],
                              scope=(query.get("scope") or [None])[0])
        elif path == "/api/reconciliacao":
            query = parse_qs(parts.query)
            allowed = {"limit", "offset", "contest_id", "nature", "state", "min_candidates"}
            if set(query) - allowed:
                self._bad_request("parâmetros inválidos")
                return
            try:
                limit = int(query.get("limit", ["50"])[0])
                offset = int(query.get("offset", ["0"])[0])
                min_candidates = (int(query["min_candidates"][0])
                                  if "min_candidates" in query else 0)
            except ValueError:
                self._bad_request("parâmetros inválidos")
                return
            from radar import role_identity
            self._serve_study(role_identity.reconciliation_queue, limit=limit, offset=offset,
                              contest_id=query.get("contest_id", [None])[0],
                              nature=query.get("nature", [None])[0],
                              state=query.get("state", [None])[0],
                              min_candidates=min_candidates)
        elif path == "/api/reconciliacao/historico":
            query = parse_qs(parts.query)
            if set(query) - {"contest_id", "label"} or "contest_id" not in query \
                    or "label" not in query:
                self._bad_request("contest_id e label obrigatórios")
                return
            from radar import role_identity
            self._serve_study(role_identity.reconciliation_history,
                              contest_id=query["contest_id"][0], label=query["label"][0])
        elif path == "/api/conflitos-revisao":
            query = parse_qs(parts.query)
            allowed = {"limit", "offset", "contest_id", "field", "cause", "priority"}
            if set(query) - allowed:
                self._bad_request("parâmetros inválidos")
                return
            try:
                limit = int(query.get("limit", ["50"])[0])
                offset = int(query.get("offset", ["0"])[0])
                priority = (int(query["priority"][0]) if "priority" in query else None)
            except ValueError:
                self._bad_request("parâmetros inválidos")
                return
            from radar import conflict_review
            self._serve_study(conflict_review.conflict_groups, limit=limit, offset=offset,
                              contest_id=query.get("contest_id", [None])[0],
                              field=query.get("field", [None])[0],
                              cause=query.get("cause", [None])[0], priority=priority)
        elif path == "/api/prazos":
            query = parse_qs(parts.query)
            allowed = {"limit", "offset", "contest_id", "group", "state"}
            if set(query) - allowed:
                self._bad_request("parâmetros inválidos")
                return
            try:
                limit = int(query.get("limit", ["100"])[0])
                offset = int(query.get("offset", ["0"])[0])
            except ValueError:
                self._bad_request("parâmetros inválidos")
                return
            from radar import deadline_review
            self._serve_study(deadline_review.deadline_report, limit=limit, offset=offset,
                              contest_id=query.get("contest_id", [None])[0],
                              group=query.get("group", [None])[0],
                              state=query.get("state", [None])[0])
        elif path == "/api/carteira":
            query = parse_qs(parts.query)
            allowed = {"limit", "offset", "prontidao", "prazo", "si", "indigena",
                       "documental", "uf", "conflito", "search", "contest_id", "role_id"}
            if set(query) - allowed:
                self._bad_request("parâmetros inválidos")
                return
            try:
                limit = int(query.get("limit", ["50"])[0])
                offset = int(query.get("offset", ["0"])[0])
            except ValueError:
                self._bad_request("parâmetros inválidos")
                return
            conflict = query.get("conflito", [None])[0]
            if conflict not in (None, "sim", "nao"):
                self._bad_request("conflito inválido")
                return
            from radar import portfolio
            self._serve_study(portfolio.portfolio, limit=limit, offset=offset,
                              prontidao=query.get("prontidao", [None])[0],
                              prazo=query.get("prazo", [None])[0],
                              si=query.get("si", [None])[0],
                              indigena=query.get("indigena", [None])[0],
                              documental=query.get("documental", [None])[0],
                              uf=query.get("uf", [None])[0],
                              conflito=None if conflict is None else conflict == "sim",
                              search=query.get("search", [None])[0],
                              contest_id=query.get("contest_id", [None])[0],
                              role_id=query.get("role_id", [None])[0])
        elif path == "/api/elegibilidade":
            query = parse_qs(parts.query)
            allowed = {"limit", "offset", "profile", "eligibility", "indigenous",
                       "temporal", "identity", "si", "uf", "conflict", "conflito",
                       "search", "contest_id", "role_id"}
            if set(query) - allowed:
                self._bad_request("parâmetros inválidos")
                return
            try:
                limit = int(query.get("limit", ["50"])[0])
                offset = int(query.get("offset", ["0"])[0])
            except ValueError:
                self._bad_request("parâmetros inválidos")
                return
            conflict = query.get("conflito", query.get("conflict", [None]))[0]
            if conflict not in (None, "sim", "nao"):
                self._bad_request("conflito inválido")
                return
            from radar import eligibility
            self._serve_study(eligibility.matrix, limit=limit, offset=offset,
                              profile=query.get("profile", [None])[0],
                              eligibility=query.get("eligibility", [None])[0],
                              indigenous=query.get("indigenous", [None])[0],
                              temporal=query.get("temporal", [None])[0],
                              identity=query.get("identity", [None])[0],
                              si=query.get("si", [None])[0],
                              uf=query.get("uf", [None])[0],
                              conflict=None if conflict is None else conflict == "sim",
                              search=query.get("search", [None])[0],
                              contest_id=query.get("contest_id", [None])[0],
                              role_id=query.get("role_id", [None])[0])
        elif path == "/api/elegibilidade/pendentes":
            query = parse_qs(parts.query)
            allowed = {"limit", "offset", "contest_id", "cause"}
            if set(query) - allowed:
                self._bad_request("parâmetros inválidos")
                return
            try:
                limit = int(query.get("limit", ["100"])[0])
                offset = int(query.get("offset", ["0"])[0])
            except ValueError:
                self._bad_request("parâmetros inválidos")
                return
            from radar import eligibility
            self._serve_study(eligibility.pending_audit, limit=limit, offset=offset,
                              contest_id=query.get("contest_id", [None])[0],
                              cause=query.get("cause", [None])[0])
        elif path == "/api/elegibilidade/revisao":
            query = parse_qs(parts.query)
            if set(query) - {"limit", "profile"}:
                self._bad_request("parâmetros inválidos")
                return
            try:
                limit = int(query.get("limit", ["50"])[0])
            except ValueError:
                self._bad_request("parâmetros inválidos")
                return
            from radar import eligibility
            self._serve_study(eligibility.compatibility_review, limit=limit,
                              profile=query.get("profile", [None])[0])
        elif path == "/api/elegibilidade/destaques":
            query = parse_qs(parts.query)
            if set(query) - {"limit", "profile"}:
                self._bad_request("parâmetros inválidos")
                return
            try:
                limit = int(query.get("limit", ["12"])[0])
            except ValueError:
                self._bad_request("parâmetros inválidos")
                return
            from radar import eligibility
            self._serve_study(eligibility.highlights, limit=limit,
                              profile=query.get("profile", [None])[0])
        elif path == "/api/quadro-vagas":
            query = parse_qs(parts.query)
            if set(query) - {"contest_id", "version_id"}:
                self._bad_request("parâmetros inválidos")
                return
            from radar import vacancy_columns
            self._serve_study(vacancy_columns.report,
                              contest_id=query.get("contest_id", [None])[0],
                              version_id=query.get("version_id", [None])[0])
        elif path == "/api/carteira/destaques":
            query = parse_qs(parts.query)
            if set(query) - {"limit"}:
                self._bad_request("parâmetros inválidos")
                return
            try:
                limit = int(query.get("limit", ["12"])[0])
            except ValueError:
                self._bad_request("parâmetros inválidos")
                return
            from radar import portfolio
            self._serve_study(portfolio.portfolio_highlights, limit=limit)
        elif path == "/api/carteira/dossie":
            query = parse_qs(parts.query)
            if set(query) - {"contest_id", "role_id", "scope"} \
                    or "contest_id" not in query:
                self._bad_request("contest_id obrigatório")
                return
            from radar import portfolio
            self._serve_study(portfolio.portfolio_dossier, query["contest_id"][0],
                              role_id=query.get("role_id", [None])[0],
                              scope=query.get("scope", [None])[0])
        elif path == "/api/prazos/calendario":
            query = parse_qs(parts.query)
            allowed = {"limit", "offset", "contest_id", "group", "state", "urgency"}
            if set(query) - allowed:
                self._bad_request("parâmetros inválidos")
                return
            try:
                limit = int(query.get("limit", ["100"])[0])
                offset = int(query.get("offset", ["0"])[0])
            except ValueError:
                self._bad_request("parâmetros inválidos")
                return
            from radar import deadline_calendar
            self._serve_study(deadline_calendar.calendar, limit=limit, offset=offset,
                              contest_id=query.get("contest_id", [None])[0],
                              group=query.get("group", [None])[0],
                              state=query.get("state", [None])[0],
                              urgency=query.get("urgency", [None])[0])
        elif path == "/api/prazos/auditoria":
            query = parse_qs(parts.query)
            allowed = {"limit", "offset", "contest_id", "group", "cause"}
            if set(query) - allowed:
                self._bad_request("parâmetros inválidos")
                return
            try:
                limit = int(query.get("limit", ["50"])[0])
                offset = int(query.get("offset", ["0"])[0])
            except ValueError:
                self._bad_request("parâmetros inválidos")
                return
            from radar import deadline_audit
            self._serve_study(deadline_audit.audit_conflicts, limit=limit, offset=offset,
                              contest_id=query.get("contest_id", [None])[0],
                              group=query.get("group", [None])[0],
                              cause=query.get("cause", [None])[0])
        elif path == "/api/prazos/caso":
            query = parse_qs(parts.query)
            if set(query) - {"contest_id", "group", "escopo"} \
                    or "contest_id" not in query or "group" not in query:
                self._bad_request("contest_id e group obrigatórios")
                return
            from radar import deadline_audit
            self._serve_study(deadline_audit.case_file,
                              contest_id=query["contest_id"][0],
                              group=query["group"][0],
                              escopo=query.get("escopo", [None])[0])
        elif path == "/api/prazos/revalidacao":
            query = parse_qs(parts.query)
            if set(query) - {"limit"}:
                self._bad_request("parâmetros inválidos")
                return
            try:
                limit = int(query.get("limit", ["5"])[0])
            except ValueError:
                self._bad_request("parâmetros inválidos")
                return
            from radar import deadline_revalidation
            self._serve_study(deadline_revalidation.plan, limit=limit)
        elif path == "/api/prazos/revalidacao/historico":
            query = parse_qs(parts.query)
            allowed = {"limit", "offset", "contest_id", "group"}
            if set(query) - allowed:
                self._bad_request("parâmetros inválidos")
                return
            try:
                limit = int(query.get("limit", ["50"])[0])
                offset = int(query.get("offset", ["0"])[0])
            except ValueError:
                self._bad_request("parâmetros inválidos")
                return
            from radar import deadline_revalidation
            self._serve_study(deadline_revalidation.history, limit=limit, offset=offset,
                              contest_id=query.get("contest_id", [None])[0],
                              grupo=query.get("group", [None])[0])
        elif path == "/api/documentos/nominais-destino":
            query = parse_qs(parts.query)
            allowed = {"limit", "offset", "contest_id", "destination"}
            if set(query) - allowed:
                self._bad_request("parâmetros inválidos")
                return
            try:
                limit = int(query.get("limit", ["200"])[0])
                offset = int(query.get("offset", ["0"])[0])
            except ValueError:
                self._bad_request("parâmetros inválidos")
                return
            from radar import nominal_destination
            self._serve_study(nominal_destination.nominal_destinations, limit=limit,
                              offset=offset,
                              contest_id=query.get("contest_id", [None])[0],
                              destination=query.get("destination", [None])[0])
        elif path == "/api/cobertura/estados":
            query = parse_qs(parts.query)
            if set(query) - {"limit"}:
                self._bad_request("parâmetros inválidos")
                return
            try:
                limit = int(query.get("limit", ["5000"])[0])
            except ValueError:
                self._bad_request("limit inválido")
                return
            if limit < 0:
                self._bad_request("limit inválido")
                return
            from radar import coverage_states
            self._serve_study(coverage_states.coverage_report, limit=limit)
        elif path == "/api/campos-decisivos":
            query = parse_qs(parts.query)
            if set(query) - {"limit", "contest_id"}:
                self._bad_request("parâmetros inválidos")
                return
            try:
                limit = int(query.get("limit", ["200"])[0])
            except ValueError:
                self._bad_request("limit inválido")
                return
            if limit < 0:
                self._bad_request("limit inválido")
                return
            from radar import decisive_fields
            contest_ids = query.get("contest_id") or None
            self._serve_study(decisive_fields.decisive_report,
                              contest_ids=contest_ids, limit=limit)
        elif path == "/api/conflitos":
            query = parse_qs(parts.query)
            if set(query) - {"limit", "contest_id"}:
                self._bad_request("parâmetros inválidos")
                return
            try:
                limit = int(query.get("limit", ["200"])[0])
            except ValueError:
                self._bad_request("limit inválido")
                return
            if limit < 0:
                self._bad_request("limit inválido")
                return
            from radar import version_conflicts
            self._serve_study(version_conflicts.conflicts,
                              contest_id=(query.get("contest_id") or [None])[0],
                              limit=limit)
        elif path == "/api/editais-faltantes":
            query = parse_qs(parts.query)
            if set(query) - {"limit", "source"}:
                self._bad_request("parâmetros inválidos")
                return
            try:
                limit = int(query.get("limit", ["50"])[0])
            except ValueError:
                self._bad_request("limit inválido")
                return
            if limit < 1:
                self._bad_request("limit inválido")
                return
            from radar import acquisition
            self._serve_study(acquisition.targets,
                              source_id=(query.get("source") or [None])[0], limit=limit)
        elif path == "/api/pipeline/parciais":
            query = parse_qs(parts.query)
            if set(query) - {"limit"}:
                self._bad_request("parâmetros inválidos")
                return
            try:
                limit = int(query.get("limit", ["500"])[0])
            except ValueError:
                self._bad_request("limit inválido")
                return
            if limit < 1:
                self._bad_request("limit inválido")
                return
            from radar import page_batches
            self._serve_study(page_batches.batch_report, limit=limit)
        elif path == "/api/pipeline/escopo-regional":
            query = parse_qs(parts.query)
            if set(query) - {"version_id"} or "version_id" not in query:
                self._bad_request("version_id obrigatório")
                return
            from radar import regional_scope
            version_id = query["version_id"][0]
            try:
                self._serve_study(regional_scope.scope_report, version_id=version_id)
            except ValueError as error:
                self._bad_request(str(error))
        elif path == "/api/revisao/duplicidades":
            query = parse_qs(parts.query)
            if set(query) - {"limit", "contest_id", "field"}:
                self._bad_request("parâmetros inválidos")
                return
            try:
                limit = int(query.get("limit", ["50"])[0])
            except ValueError:
                self._bad_request("limit inválido")
                return
            from radar import review
            self._serve_study(review.duplicate_groups,
                              contest_id=query.get("contest_id", [None])[0],
                              field_name=query.get("field", [None])[0], limit=limit)
        elif path == "/api/pipeline/ocr":
            query = parse_qs(parts.query)
            if set(query) - {"limit"}:
                self._bad_request("parâmetros inválidos")
                return
            try:
                limit = int(query.get("limit", ["100"])[0])
            except ValueError:
                self._bad_request("limit inválido")
                return
            from radar import ocr
            self._serve_study(ocr.ocr_report, limit=limit)
        elif path == "/api/pipeline/duplicidades":
            query = parse_qs(parts.query)
            if set(query) - {"limit"}:
                self._bad_request("parâmetros inválidos")
                return
            try:
                limit = int(query.get("limit", ["100"])[0])
            except ValueError:
                self._bad_request("limit inválido")
                return
            from radar import pipeline
            self._serve_study(pipeline.duplicate_report, limit=limit)
        elif path == "/api/pipeline/cobertura":
            query = parse_qs(parts.query)
            if set(query) - {"limit"}:
                self._bad_request("parâmetros inválidos")
                return
            try:
                limit = int(query.get("limit", ["500"])[0])
            except ValueError:
                self._bad_request("limit inválido")
                return
            from radar import pipeline
            self._serve_study(pipeline.contest_coverage, limit=limit)
        elif path == "/api/pipeline/documentos":
            query = parse_qs(parts.query)
            if set(query) - {"contest_id", "limit", "pending"}:
                self._bad_request("parâmetros inválidos")
                return
            try:
                limit = int(query.get("limit", ["100"])[0])
            except ValueError:
                self._bad_request("limit inválido")
                return
            pending_raw = query.get("pending", ["0"])[0].lower()
            if pending_raw not in ("0", "1", "true", "false"):
                self._bad_request("pending inválido")
                return
            from radar import pipeline
            self._serve_study(pipeline.audit_documents,
                              contest_id=query.get("contest_id", [None])[0],
                              limit=limit,
                              only_pending=pending_raw in ("1", "true"))
        elif path == "/api/fontes":
            if parts.query:
                self._bad_request("parâmetros inválidos")
                return
            from radar import budget
            self._serve_study(budget.state_report)
        elif path.startswith("/api/fontes/"):
            remainder = path[len("/api/fontes/"):]
            if not remainder or "/" in remainder or parts.query:
                self._bad_request("fonte inválida")
                return
            from radar import budget, connectors, source_policy
            try:
                source_policy.catalog.get_source(remainder)
            except KeyError:
                self._bad_request("fonte desconhecida")
                return
            def detail(db):
                try:
                    connector = connectors.get_connector(remainder).describe()
                    implemented = True
                except connectors.ConnectorError:
                    connector, implemented = None, False
                return {
                    "source": source_policy.catalog.get_source(remainder),
                    "connector": connector,
                    "implemented": implemented,
                    "policy": [source_policy.decision(remainder, content_type)
                               for content_type in
                               source_policy.catalog.get_source(remainder)["content"]],
                    "reviews": source_policy.review_history(db, remainder)["itens"],
                }
            self._serve_study(detail)
        elif path == "/api/fontes-consumo":
            query = parse_qs(parts.query)
            if set(query) - {"source_id", "limit"}:
                self._bad_request("parâmetros inválidos")
                return
            try:
                limit = int(query.get("limit", ["50"])[0])
            except ValueError:
                self._bad_request("limit inválido")
                return
            from radar import budget
            self._serve_study(budget.consumption_report,
                              source_id=query.get("source_id", [None])[0], limit=limit)
        elif path == "/api/revisao/fila":
            self._review_queue(parts)
        elif path == "/api/revisao/pilotos":
            if parts.query:
                self._bad_request("parâmetros inválidos")
                return
            from radar import pilot
            self._serve_study(pilot.available)
        elif path == "/api/revisao/piloto":
            query = parse_qs(parts.query)
            if set(query) - {"contest_id", "size"} or "contest_id" not in query:
                self._bad_request("contest_id obrigatório")
                return
            try:
                size = int(query.get("size", ["16"])[0])
            except ValueError:
                self._bad_request("tamanho inválido")
                return
            from radar import pilot
            self._serve_study(pilot.report, contest_id=query["contest_id"][0], size=size)
        elif path == "/api/revisao/identidades":
            query = parse_qs(parts.query)
            if set(query) - {"contest_id"} or "contest_id" not in query:
                self._bad_request("contest_id obrigatório")
                return
            from radar import identity_suggestions
            self._serve_study(identity_suggestions.report,
                              contest_id=query["contest_id"][0])
        elif path == "/api/revisao/grupos":
            query = parse_qs(parts.query)
            allowed = {"limit", "offset", "state", "field", "contest_id", "document_id",
                       "version_id", "contexto", "linha"}
            if set(query) - allowed:
                self._bad_request("parâmetros inválidos")
                return
            try:
                limit = int(query.get("limit", ["25"])[0])
                offset = int(query.get("offset", ["0"])[0])
            except ValueError:
                self._bad_request("parâmetros inválidos")
                return
            from radar import review_groups
            self._serve_study(review_groups.groups, limit=limit, offset=offset,
                              state=query.get("state", ["aberto"])[0],
                              field_name=query.get("field", [None])[0],
                              contest_id=query.get("contest_id", [None])[0],
                              document_id=query.get("document_id", [None])[0],
                              version_id=query.get("version_id", [None])[0],
                              contexto={"1": True, "0": False}.get(
                                  query.get("contexto", [None])[0]),
                              linha=query.get("linha", [None])[0])
        elif path.startswith("/api/revisao/proposta/"):
            proposal_id = path[len("/api/revisao/proposta/"):]
            if not proposal_id or "/" in proposal_id or parts.query:
                self._bad_request("proposta inválida")
                return
            from radar import review
            self._serve_study(review.proposal_detail, proposal_id)
        elif path.startswith("/api/revisao/lotes/"):
            remainder = path[len("/api/revisao/lotes/"):]
            if remainder.endswith("/exportar"):
                lote_id = remainder[:-len("/exportar")]
                if not lote_id or "/" in lote_id or parts.query:
                    self._bad_request("lote inválido")
                    return
                from radar import review
                self._serve_study(review.export_batch, lote_id)
            else:
                if not remainder or "/" in remainder or parts.query:
                    self._bad_request("lote inválido")
                    return
                from radar import review
                self._serve_study(review.batch_status, remainder)
        elif path == "/api/documentos/bloqueados":
            query = parse_qs(parts.query)
            if set(query) - {"contest_id", "limit", "state"}:
                self._bad_request("parâmetros inválidos")
                return
            try:
                limit = int(query.get("limit", ["200"])[0])
            except ValueError:
                self._bad_request("limit inválido")
                return
            states = query.get("state", [None])[0]
            from radar import document_ingest
            self._serve_study(document_ingest.blocked_report,
                              contest_id=query.get("contest_id", [None])[0],
                              states=states, limit=limit)
        elif path == "/api/cobertura":
            if parts.query:
                self._send_no_content(HTTPStatus.BAD_REQUEST)
            else:
                self._serve_study(data_quality.audit)
        elif path == "/api/cobertura/resumo":
            if parts.query:
                self._send_no_content(HTTPStatus.BAD_REQUEST)
            else:
                self._serve_study(data_quality.summary)
        elif path == "/api/lacunas":
            query = parse_qs(parts.query)
            try:
                limit = int(query.get("limit", ["50"])[0])
            except ValueError:
                self._bad_request("limit inválido")
                return
            if limit < 1 or set(query) - {"limit"}:
                self._bad_request("parâmetros inválidos")
            else:
                self._serve_study(data_quality.gaps, limit=limit)
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
        elif path == "/api/estudos/perfil":
            if parts.query:
                self._send_no_content(HTTPStatus.BAD_REQUEST)
            else:
                self._serve_study(knowledge_store.list_profile)
        elif path == "/api/estudos/conteudo":
            query = parse_qs(parts.query)
            contest_id = query.get("contest_id", [None])[0]
            if set(query) - {"contest_id"} or not contest_id:
                self._send_no_content(HTTPStatus.BAD_REQUEST)
            else:
                self._serve_study(knowledge_store.resolve_program, contest_id)
        elif path == "/api/estudos/preparacao":
            query = parse_qs(parts.query)
            contest_id = query.get("contest_id", [None])[0]
            if set(query) - {"contest_id"} or not contest_id:
                self._send_no_content(HTTPStatus.BAD_REQUEST)
            else:
                self._serve_study(knowledge_store.preparation_report, contest_id)
        elif path == "/api/estudos/exportar":
            if parts.query:
                self._send_no_content(HTTPStatus.BAD_REQUEST)
            else:
                self._serve_study(study_backup.export_study_data)
        # --- Prática: flashcards, questões e simulados (Fase 23) ---
        elif path == "/api/estudos/flashcards":
            query = parse_qs(parts.query)
            if set(query) - {"incluir_arquivados"}:
                self._send_no_content(HTTPStatus.BAD_REQUEST)
            else:
                self._serve_study(practice_store.list_flashcards,
                                  include_archived=query.get("incluir_arquivados", ["0"])[0] in ("1", "true"))
        elif path == "/api/estudos/flashcards/fila":
            query = parse_qs(parts.query)
            try:
                limit = int(query.get("limit", ["20"])[0])
            except ValueError:
                self._send_no_content(HTTPStatus.BAD_REQUEST)
                return
            if limit < 1 or set(query) - {"limit"}:
                self._send_no_content(HTTPStatus.BAD_REQUEST)
            else:
                self._serve_study(practice_store.study_queue, limit=limit)
        elif path == "/api/estudos/flashcards/estatisticas":
            if parts.query:
                self._send_no_content(HTTPStatus.BAD_REQUEST)
            else:
                self._serve_study(practice_store.flashcard_stats)
        elif path == "/api/estudos/questoes":
            query = parse_qs(parts.query)
            if set(query) - {"incluir_arquivadas", "disciplina", "topico"}:
                self._send_no_content(HTTPStatus.BAD_REQUEST)
            else:
                self._serve_study(practice_store.list_questions,
                                  include_archived=query.get("incluir_arquivadas", ["0"])[0] in ("1", "true"),
                                  disciplina=query.get("disciplina", [None])[0],
                                  topico=query.get("topico", [None])[0])
        elif path == "/api/estudos/tentativas":
            query = parse_qs(parts.query)
            try:
                limit = int(query.get("limit", ["200"])[0])
            except ValueError:
                self._send_no_content(HTTPStatus.BAD_REQUEST)
                return
            if limit < 1 or set(query) - {"limit", "simulado_id"}:
                self._send_no_content(HTTPStatus.BAD_REQUEST)
            else:
                self._serve_study(practice_store.list_attempts, limit=limit,
                                  simulado_id=query.get("simulado_id", [None])[0])
        elif path == "/api/estudos/desempenho":
            if parts.query:
                self._send_no_content(HTTPStatus.BAD_REQUEST)
            else:
                self._serve_study(practice_store.performance_report)
        elif path.startswith("/api/estudos/simulados/"):
            if parts.query:
                self._bad_request("rota dinâmica de simulado não aceita parâmetros")
                return
            rest = path[len("/api/estudos/simulados/"):]
            if rest.endswith("/resultado"):
                exam_id = rest[:-len("/resultado")]
                if exam_id and "/" not in exam_id:
                    self._serve_exam(lambda: practice_store.exam_result(self.server.db_path, exam_id))
                    return
            elif rest.endswith("/questoes"):
                exam_id = rest[:-len("/questoes")]
                if exam_id and "/" not in exam_id:
                    self._serve_exam(lambda: practice_store.exam_questions(self.server.db_path, exam_id))
                    return
            elif rest.endswith("/resumo"):
                exam_id = rest[:-len("/resumo")]
                if exam_id and "/" not in exam_id:
                    self._serve_exam(lambda: practice_store.exam_summary(self.server.db_path, exam_id))
                    return
            elif rest and "/" not in rest:
                self._serve_exam(lambda: practice_store.get_exam(self.server.db_path, rest))
                return
            self._send_no_content(HTTPStatus.NOT_FOUND)
        elif path == "/api/estudos/midia" or path.startswith("/api/estudos/midia/"):
            media_id = path[len("/api/estudos/midia/"):] if path.startswith("/api/estudos/midia/") else ""
            if parts.query or not media_id or "/" in media_id:
                self._bad_request("midia inválida")
                return
            self._serve_media(media_id)
        elif path == "/api/estudos/pacotes":
            query = parse_qs(parts.query)
            try:
                limit = int(query.get("limit", ["50"])[0])
            except ValueError:
                self._bad_request("limit inválido")
                return
            if limit < 1 or set(query) - {"limit"}:
                self._bad_request("parâmetros inválidos")
            else:
                self._serve_study(packages.list_packages, limit=limit)
        elif path == "/api/estudos/pacotes/exportar":
            query = parse_qs(parts.query)
            licenca = query.get("licenca", ["propria"])[0]
            tipo = query.get("tipo", ["misto"])[0]
            nome = query.get("nome", ["Pacote"])[0]
            if set(query) - {"licenca", "tipo", "nome"}:
                self._bad_request("parâmetros inválidos")
                return
            try:
                blob = packages.export_package(self.server.db_path, nome=nome, tipo=tipo,
                                               licenca=licenca)
            except ValueError as error:
                self._bad_request(str(error))
                return
            self._send(HTTPStatus.OK, "application/zip",
                       blob, {"Content-Disposition": 'attachment; filename="radar-pacote.zip"'})
        elif path == "/api/estudos/simulados":
            query = parse_qs(parts.query)
            try:
                limit = int(query.get("limit", ["50"])[0])
            except ValueError:
                self._send_no_content(HTTPStatus.BAD_REQUEST)
                return
            if limit < 1 or set(query) - {"limit"}:
                self._send_no_content(HTTPStatus.BAD_REQUEST)
            else:
                self._serve_study(practice_store.list_exams, limit=limit)
        elif path in ("/", "/index.html"):
            self._serve_file("index.html")
        elif path in _ASSET_ROUTES:
            self._serve_file(_ASSET_ROUTES[path])
        else:
            self._send_no_content(HTTPStatus.NOT_FOUND)

    def _method_not_allowed(self, allow="GET"):
        self._send_no_content(HTTPStatus.METHOD_NOT_ALLOWED, {"Allow": allow})

    def do_POST(self):
        from radar import study_store, knowledge_store, study_backup, practice_store, packages, media
        parts = urlsplit(self.path)
        path = parts.path
        if path.startswith("/api/alertas/") and not parts.query:
            alert_id = path[len("/api/alertas/"):]
            if alert_id and "/" not in alert_id:
                self._alert_action(alert_id)
                return
        if path.startswith("/api/associacoes/") and not parts.query:
            document_id = path[len("/api/associacoes/"):]
            if not document_id or "/" in document_id:
                self._send_no_content(HTTPStatus.NOT_FOUND)
                return
            from radar import identity
            body = self._read_json()
            if body is None:
                return
            state = body.get("state")
            contest_id = body.get("contest_id")
            evidence = body.get("evidence")
            if evidence is None:
                evidence = {"motivo": "decisão humana de associação"}
            self._serve_study(identity.record_association, document_id, contest_id, state,
                              evidence, decided_by=body.get("decided_by"),
                              note=body.get("note"),
                              dry_run=bool(body.get("dry_run", False)))
            return
        if path == "/api/identidade/reparar":
            if parts.query:
                self._bad_request("parâmetros inválidos")
                return
            from radar import identity
            body = self._read_json()
            if body is None:
                return
            self._serve_study(identity.apply_repair,
                              decided_by=body.get("decided_by"),
                              note=body.get("note"),
                              dry_run=bool(body.get("dry_run", True)))
            return
        if path.startswith("/api/revisao/proposta/") and not parts.query:
            proposal_id = path[len("/api/revisao/proposta/"):]
            if not proposal_id or "/" in proposal_id:
                self._bad_request("proposta inválida")
                return
            from radar import review
            body = self._read_json()
            if body is None:
                return
            if not body.get("evidence_sha256"):
                # Decisão pela interface sempre declara a impressão da evidência vista.
                self._bad_request("evidence_sha256 obrigatório")
                return
            self._serve_study(review.decide_proposal, proposal_id, body.get("decision"),
                              reviewer=body.get("reviewer"), reason=body.get("reason"),
                              origin="interface",
                              value=body.get("value"),
                              expected_evidence_sha256=body.get("evidence_sha256"),
                              lote_id=body.get("lote_id"),
                              expected_scope_snapshot=body.get("scope_snapshot"))
            return
        if path == "/api/reconciliacao":
            if parts.query:
                self._bad_request("parâmetros inválidos")
                return
            from radar import role_identity
            body = self._read_json()
            if body is None:
                return
            self._serve_study(role_identity.decide_reconciliation,
                              contest_id=body.get("contest_id"),
                              label=body.get("label"), state=body.get("state"),
                              reviewer=body.get("reviewer"), reason=body.get("reason"),
                              role_id=body.get("role_id"), nature=body.get("nature"),
                              evidence=body.get("evidence"),
                              expected_previous_id=body.get("previous_id"),
                              dry_run=body.get("dry_run", True) is not False)
            return
        if path == "/api/prazos/verificar-documento":
            if parts.query:
                self._bad_request("parâmetros inválidos")
                return
            from radar import deadline_revalidation
            body = self._read_json()
            if body is None:
                return
            version_id = body.get("version_id")
            if not isinstance(version_id, str) or not version_id.strip():
                self._bad_request("version_id obrigatório")
                return
            dry_run = body.get("dry_run", True) is not False
            self._serve_study(deadline_revalidation.verify_version, version_id,
                              contest_id=body.get("contest_id"),
                              grupo=body.get("group"), escopo=body.get("escopo"),
                              apply=not dry_run,
                              checked_by=body.get("checked_by") or "operador local")
            return
        if path == "/api/prazos/revalidacao":
            if parts.query:
                self._bad_request("parâmetros inválidos")
                return
            from radar import deadline_revalidation
            body = self._read_json()
            if body is None:
                return
            try:
                limit = int(body.get("limit", 5))
            except (TypeError, ValueError):
                self._bad_request("limite inválido")
                return
            dry_run = body.get("dry_run", True) is not False
            only = None
            if body.get("contest_id") or body.get("group") or body.get("escopo"):
                only = {"contest_id": body.get("contest_id"),
                        "grupo": body.get("group"),
                        "escopo": body.get("escopo")}
            self._serve_study(deadline_revalidation.execute, limit=limit,
                              apply=not dry_run, only=only,
                              checked_by=body.get("checked_by") or "operador local")
            return
        if path == "/api/revisao/selecionar":
            if parts.query:
                self._bad_request("parâmetros inválidos")
                return
            from radar import review
            body = self._read_json()
            if body is None:
                return
            self._serve_study(review.select_current_value, body.get("proposal_id"),
                              body.get("reviewer"), body.get("reason"),
                              origin="interface")
            return
        if path == "/api/revisao/lotes":
            if parts.query:
                self._bad_request("parâmetros inválidos")
                return
            from radar import review
            body = self._read_json()
            if body is None:
                return
            self._serve_study(review.open_batch, created_by=body.get("created_by"),
                              filters=body.get("filters"), size=body.get("size", 20),
                              origin=body.get("origin") or "interface",
                              note=body.get("note"))
            return
        if path.startswith("/api/revisao/lotes/") and not parts.query:
            lote_id = path[len("/api/revisao/lotes/"):]
            if not lote_id or "/" in lote_id:
                self._bad_request("lote inválido")
                return
            from radar import review
            body = self._read_json()
            if body is None:
                return
            self._serve_study(review.batch_step, lote_id, body.get("action"))
            return
        if path == "/api/revisao/importar":
            if parts.query:
                self._bad_request("parâmetros inválidos")
                return
            from radar import review
            body = self._read_json(max_len=4 * 1024 * 1024)
            if body is None:
                return
            self._serve_study(review.import_decisions, body.get("payload"),
                              reviewer=body.get("reviewer"), reason=body.get("reason"),
                              origin="importacao",
                              dry_run=bool(body.get("dry_run", True)))
            return
        if path == "/api/documentos/importar":
            if parts.query:
                self._bad_request("parâmetros inválidos")
                return
            from radar import document_ingest
            body = self._read_json(max_len=32 * 1024 * 1024)
            if body is None:
                return
            import base64
            try:
                content = base64.b64decode(body.get("content_base64") or "", validate=True)
            except (ValueError, TypeError):
                self._bad_request("conteúdo base64 inválido")
                return
            self._serve_study(document_ingest.ingest_manual_document,
                              body.get("document_id"), content,
                              declared_origin=body.get("declared_origin"),
                              channel=body.get("channel") or "upload_local",
                              declared_by=body.get("declared_by"),
                              original_url=body.get("original_url"),
                              note=body.get("note"),
                              dry_run=bool(body.get("dry_run", True)))
            return
        if path == "/api/documentos/tipos":
            if parts.query:
                self._bad_request("parâmetros inválidos")
                return
            from radar import enrichment
            body = self._read_json()
            if body is None:
                return
            self._serve_study(enrichment.backfill_document_types,
                              dry_run=bool(body.get("dry_run", True)))
            return
        if path == "/api/documentos/reprocessar":
            if parts.query:
                self._bad_request("parâmetros inválidos")
                return
            from radar import reprocess
            body = self._read_json()
            if body is None:
                return
            self._serve_study(reprocess.reprocess_editais,
                              dry_run=bool(body.get("dry_run", True)),
                              limit=body.get("limit"))
            return
        if path == "/api/cobertura/papeis":
            if parts.query:
                self._bad_request("parâmetros inválidos")
                return
            from radar import enrichment
            body = self._read_json()
            if body is None:
                return
            self._serve_study(enrichment.materialize_document_roles,
                              dry_run=bool(body.get("dry_run", True)))
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
        if path == "/api/estudos/perfil":
            if parts.query:
                self._send_no_content(HTTPStatus.BAD_REQUEST)
                return
            body = self._read_json()
            if body is not None:
                self._serve_study(knowledge_store.set_profile,
                                  disciplina=body.get("disciplina"), rotulo=body.get("rotulo"),
                                  nivel=body.get("nivel") or "nao_avaliado",
                                  revisar=bool(body.get("revisar")),
                                  confianca=body.get("confianca"),
                                  observacoes=body.get("observacoes"),
                                  origem=body.get("origem") or "usuario")
            return
        if path == "/api/estudos/lacuna":
            if parts.query:
                self._send_no_content(HTTPStatus.BAD_REQUEST)
                return
            body = self._read_json()
            if body is not None:
                self._serve_study(knowledge_store.send_gap_to_study, body.get("contest_id"),
                                  body.get("conceito_key"))
            return
        if path == "/api/estudos/importar":
            if parts.query:
                self._send_no_content(HTTPStatus.BAD_REQUEST)
                return
            body = self._read_json(max_len=2_000_000)
            if body is None:
                return
            payload = body.get("payload") if isinstance(body.get("payload"), dict) else body
            try:
                report = study_backup.import_study_data(self.server.db_path, payload,
                                                        dry_run=bool(body.get("dry_run")))
            except sqlite3.Error:
                self._send(HTTPStatus.SERVICE_UNAVAILABLE, "application/json; charset=utf-8",
                           b'{"error":"Migracao documental pendente"}')
                return
            except Exception as error:  # payload inesperado não deve derrubar a conexão
                body_err = json.dumps({"ok": False, "errors": [f"importação falhou: {type(error).__name__}"]},
                                      ensure_ascii=False).encode("utf-8")
                self._send(HTTPStatus.BAD_REQUEST, "application/json; charset=utf-8", body_err)
                return
            status = HTTPStatus.OK if report.get("ok") else HTTPStatus.BAD_REQUEST
            out = json.dumps(report, ensure_ascii=False, default=str).encode("utf-8")
            self._send(status, "application/json; charset=utf-8", out)
            return
        if path == "/api/estudos/flashcards":
            if parts.query:
                self._send_no_content(HTTPStatus.BAD_REQUEST)
                return
            body = self._read_json(max_len=32768)
            if body is None:
                return
            action = body.get("action") or "create"
            if action == "create":
                self._serve_study(practice_store.create_flashcard,
                                  frente=body.get("frente"), verso=body.get("verso"),
                                  disciplina_id=body.get("disciplina_id"),
                                  topico_id=body.get("topico_id"),
                                  contest_id=body.get("contest_id") or "",
                                  conceito_key=body.get("conceito_key"),
                                  tags=body.get("tags"), fonte=body.get("fonte"),
                                  licenca=body.get("licenca"))
            elif action == "update":
                self._serve_study(practice_store.update_flashcard, body.get("id"),
                                  frente=body.get("frente"), verso=body.get("verso"),
                                  tags=body.get("tags"), estado=body.get("estado"))
            elif action == "review":
                self._serve_study(practice_store.review_flashcard, body.get("id"),
                                  body.get("qualidade"))
            else:
                self._bad_request("ação de flashcard inválida")
            return
        if path == "/api/estudos/questoes":
            if parts.query:
                self._send_no_content(HTTPStatus.BAD_REQUEST)
                return
            body = self._read_json(max_len=32768)
            if body is None:
                return
            action = body.get("action") or "create"
            if action == "create":
                self._serve_study(practice_store.create_question,
                                  enunciado=body.get("enunciado"),
                                  alternativas=body.get("alternativas"),
                                  gabarito=body.get("gabarito"),
                                  tipo=body.get("tipo") or "escolha_unica",
                                  comentario=body.get("comentario"),
                                  disciplina=body.get("disciplina"),
                                  topico=body.get("topico"),
                                  dificuldade=body.get("dificuldade"),
                                  tags=body.get("tags"), fonte=body.get("fonte"),
                                  licenca=body.get("licenca"),
                                  procedencia=body.get("procedencia"),
                                  conceito_key=body.get("conceito_key"))
            elif action == "update":
                self._serve_study(practice_store.update_question, body.get("id"),
                                  enunciado=body.get("enunciado"),
                                  alternativas=body.get("alternativas"),
                                  gabarito=body.get("gabarito"),
                                  comentario=body.get("comentario"),
                                  disciplina=body.get("disciplina"),
                                  topico=body.get("topico"),
                                  dificuldade=body.get("dificuldade"),
                                  tags=body.get("tags"))
            elif action == "archive":
                self._serve_study(practice_store.archive_question, body.get("id"))
            else:
                self._bad_request("ação de questão inválida")
            return
        if path == "/api/estudos/tentativas":
            if parts.query:
                self._send_no_content(HTTPStatus.BAD_REQUEST)
                return
            body = self._read_json(max_len=32768)
            if body is None:
                return
            self._serve_study(practice_store.answer_question, body.get("questao_id"),
                              body.get("resposta"),
                              duracao_segundos=body.get("duracao_segundos"),
                              origem="pratica")
            return
        if path == "/api/estudos/simulados":
            if parts.query:
                self._send_no_content(HTTPStatus.BAD_REQUEST)
                return
            body = self._read_json(max_len=32768)
            if body is None:
                return
            modo = body.get("modo") or "tradicional"
            if modo in ("adaptativa", "revisao_erros", "personalizada"):
                self._serve_study(practice_store.create_adaptive_session,
                                  nome=body.get("nome"), limit=body.get("limit") if body.get("limit") is not None else 10,
                                  modo=modo, duracao_segundos=body.get("duracao_segundos"),
                                  seed=body.get("seed"), disciplina=body.get("disciplina"),
                                  topico=body.get("topico"))
                return
            self._serve_study(practice_store.create_exam,
                              nome=body.get("nome"),
                              limit=body.get("limit") if body.get("limit") is not None else 10,
                              duracao_segundos=body.get("duracao_segundos"),
                              seed=body.get("seed"),
                              shuffle=body.get("shuffle", True),
                              exclude_answered=body.get("exclude_answered", True),
                              disciplina=body.get("disciplina"), topico=body.get("topico"),
                              dificuldade=body.get("dificuldade"), tags=body.get("tags"))
            return
        if path.startswith("/api/estudos/simulados/") and not parts.query:
            rest = path[len("/api/estudos/simulados/"):]
            parts_rest = rest.split("/")
            if len(parts_rest) == 2 and parts_rest[0] and parts_rest[1] in (
                    "responder", "finalizar", "marcar", "posicao", "proxima"):
                exam_id, verb = parts_rest
                body = self._read_json(max_len=32768)
                if body is None:
                    return
                if verb == "responder":
                    self._serve_study(practice_store.save_exam_answer, exam_id,
                                      body.get("ordem"), body.get("resposta"))
                elif verb == "marcar":
                    self._serve_study(practice_store.set_exam_mark, exam_id,
                                      body.get("ordem"), bool(body.get("marcada")))
                elif verb == "posicao":
                    self._serve_study(practice_store.set_exam_position, exam_id,
                                      body.get("ordem"))
                elif verb == "proxima":
                    self._serve_study(practice_store.next_adaptive_question, exam_id)
                else:
                    self._serve_study(practice_store.finish_exam, exam_id)
                return
        if path.startswith("/api/estudos/flashcards/") and not parts.query:
            rest = path[len("/api/estudos/flashcards/"):]
            pieces = rest.split("/")
            if len(pieces) == 2 and pieces[0] and pieces[1] == "imagem":
                flashcard_id = pieces[0]
                body = self._read_json(max_len=12_000_000)
                if body is None:
                    return
                payload = self._decode_base64(body.get("dados_base64"),
                                              max_bytes=media.DEFAULT_MAX_BYTES)
                if payload is None:
                    return
                self._serve_study(practice_store.attach_flashcard_image, flashcard_id, payload,
                                  licenca=body.get("licenca"))
                return
        if path == "/api/estudos/pacotes/previa":
            if parts.query:
                self._bad_request("parâmetros inválidos")
                return
            body = self._read_json(max_len=60_000_000)
            if body is None:
                return
            payload = self._decode_base64(body.get("dados_base64"),
                                          max_bytes=packages.MAX_TOTAL_BYTES)
            if payload is None:
                return
            try:
                preview = packages.preview_package(self.server.db_path, payload)
            except packages.PackageError as error:
                self._bad_request(str(error))
                return
            except (KeyError, TypeError, ValueError, AttributeError):
                self._bad_request("pacote com estrutura inválida")
                return
            self._send(HTTPStatus.OK, "application/json; charset=utf-8",
                       json.dumps(preview, ensure_ascii=False, default=str).encode("utf-8"))
            return
        if path == "/api/estudos/pacotes/importar":
            if parts.query:
                self._bad_request("parâmetros inválidos")
                return
            body = self._read_json(max_len=60_000_000)
            if body is None:
                return
            payload = self._decode_base64(body.get("dados_base64"),
                                          max_bytes=packages.MAX_TOTAL_BYTES)
            if payload is None:
                return
            try:
                report = packages.import_package(self.server.db_path, payload,
                                                 dry_run=bool(body.get("dry_run")))
            except packages.PackageError as error:
                self._bad_request(str(error))
                return
            except (KeyError, TypeError, ValueError, AttributeError):
                self._bad_request("pacote com estrutura inválida")
                return
            except sqlite3.Error:
                self._send(HTTPStatus.SERVICE_UNAVAILABLE, "application/json; charset=utf-8",
                           b'{"error":"Migracao documental pendente"}')
                return
            self._send(HTTPStatus.OK, "application/json; charset=utf-8",
                       json.dumps(report, ensure_ascii=False, default=str).encode("utf-8"))
            return
        self._method_not_allowed()

    def do_PUT(self):
        self._verb_not_allowed()

    def do_DELETE(self):
        from radar import knowledge_store, practice_store
        parts = urlsplit(self.path)
        if parts.path.startswith("/api/estudos/flashcards/") and not parts.query:
            rest = parts.path[len("/api/estudos/flashcards/"):]
            pieces = rest.split("/")
            if len(pieces) == 2 and pieces[0] and pieces[1] == "imagem":
                self._serve_study(practice_store.remove_flashcard_image, pieces[0])
                return
        if parts.path == "/api/estudos/perfil":
            query = parse_qs(parts.query)
            key = query.get("conceito_key", [None])[0]
            if set(query) - {"conceito_key"} or not key:
                self._bad_request("conceito_key obrigatório")
                return
            try:
                removed = knowledge_store.delete_profile(self.server.db_path, key)
            except sqlite3.Error:
                self._send(HTTPStatus.SERVICE_UNAVAILABLE, "application/json; charset=utf-8",
                           b'{"error":"Migracao documental pendente"}')
                return
            if not removed:
                self._send_no_content(HTTPStatus.NOT_FOUND)
                return
            self._send(HTTPStatus.OK, "application/json; charset=utf-8", b'{"removed":true}')
            return
        self._verb_not_allowed()

    def do_PATCH(self):
        self._verb_not_allowed()

    def _verb_not_allowed(self):
        path = urlsplit(self.path).path
        post_paths = ("/api/preferencias", "/api/estudos/disciplinas", "/api/estudos/topicos",
                      "/api/estudos/progresso", "/api/estudos/sessoes", "/api/estudos/revisoes",
                      "/api/estudos/perfil", "/api/estudos/lacuna", "/api/estudos/importar",
                      "/api/estudos/flashcards", "/api/estudos/questoes",
                      "/api/estudos/tentativas", "/api/estudos/simulados",
                      "/api/reconciliacao", "/api/prazos/revalidacao",
                      "/api/prazos/verificar-documento")
        allow = "GET, POST" if path in post_paths else "GET"
        if path == "/api/estudos/perfil":
            allow = "GET, POST, DELETE"
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
