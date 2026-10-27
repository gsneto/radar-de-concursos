"""Testes do servidor HTTP loopback do GSN Concursos (Task 2 — server).

Cobrem, com ``http.client`` e servidor real em porta efêmera (port=0):
- ``GET /api/concursos`` com banco vazio (200, JSON, array vazio);
- ``GET /api/concursos`` com registros persistidos (contrato correto);
- ``GET /`` serve a página estática ``web/index.html``;
- assets locais ``/styles.css`` e ``/app.js`` (e variantes ``/web/...``);
- ``POST /api/concursos`` e métodos de escrita retornam 405;
- caminhos desconhecidos (incluindo tentativa de path traversal) retornam 404.
"""

from __future__ import annotations

import http.client
import json
import sqlite3
import tempfile
import threading
import unittest
from pathlib import Path

from radar import storage
from radar.server import create_server

# Campos exatos do contrato v1, na ordem da spec.
CONTRACT_FIELDS = [
    "competition_id",
    "competition",
    "agency",
    "role",
    "education",
    "immediate_vacancies",
    "reserve_vacancies",
    "indigenous_vacancies",
    "registration_start",
    "registration_end",
    "registration_status",
    "exam_date",
    "exam_location",
    "work_location",
    "source_name",
    "source_url",
    "evidence_url",
    "verified_at",
]


def make_record(role="Professor de Educação Infantil"):
    return {
        "competition_id": "001/2026",
        "competition": "Concurso público da educação",
        "agency": "Prefeitura Municipal de Guajará-Mirim/RO (SEMED)",
        "role": role,
        "education": None,
        "immediate_vacancies": 69,
        "reserve_vacancies": None,
        "indigenous_vacancies": None,
        "registration_start": "2026-07-10",
        "registration_end": "2026-07-30",
        "registration_status": "encerradas conforme período divulgado",
        "exam_date": None,
        "exam_location": None,
        "work_location": None,
        "source_name": "Prefeitura Municipal de Guajará-Mirim/RO",
        "source_url": "https://guajaramirim.ro.gov.br/artigo/",
        "evidence_url": "https://guajaramirim.ro.gov.br/artigo/",
        "verified_at": "2026-10-09T12:00:00-04:00",
    }


class ServerTestCase(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.db_path = str(Path(self._tmp.name) / "radar.db")
        # port=0 pede porta efêmera; o servidor liga mas não inicia serve_forever.
        self.server = create_server(self.db_path, host="127.0.0.1", port=0)
        self.port = self.server.server_address[1]
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()

    def tearDown(self):
        self.server.shutdown()
        self.server.server_close()
        self.thread.join(timeout=5)
        self._tmp.cleanup()

    def request(self, method, path):
        conn = http.client.HTTPConnection("127.0.0.1", self.port, timeout=5)
        try:
            conn.request(method, path)
            response = conn.getresponse()
            status = response.status
            headers = {k.lower(): v for k, v in response.getheaders()}
            body = response.read()
            return status, headers, body
        finally:
            conn.close()


class ApiEmptyTest(ServerTestCase):
    def test_empty_api_returns_json_array(self):
        status, headers, body = self.request("GET", "/api/concursos")
        self.assertEqual(status, 200)
        self.assertIn("application/json", headers.get("content-type", ""))
        self.assertEqual(json.loads(body.decode("utf-8")), [])

    def test_invalid_database_schema_returns_error_instead_of_empty_success(self):
        db = sqlite3.connect(self.db_path)
        try:
            db.execute("CREATE TABLE concursos (broken TEXT)")
            db.commit()
        finally:
            db.close()
        status, headers, body = self.request("GET", "/api/concursos")
        self.assertEqual(status, 500)
        self.assertIn("application/json", headers.get("content-type", ""))
        self.assertEqual(json.loads(body), {"error": "Falha ao consultar dados locais"})


class ApiRecordsTest(ServerTestCase):
    def test_api_returns_persisted_records_with_contract(self):
        storage.upsert_records(self.db_path, [make_record()])
        status, headers, body = self.request("GET", "/api/concursos")
        self.assertEqual(status, 200)
        self.assertIn("application/json", headers.get("content-type", ""))
        data = json.loads(body.decode("utf-8"))
        self.assertEqual(len(data), 1)
        self.assertEqual(list(data[0].keys()), CONTRACT_FIELDS)
        self.assertEqual(data[0]["immediate_vacancies"], 69)
        self.assertIsNone(data[0]["reserve_vacancies"])


class StaticServingTest(ServerTestCase):
    def test_index_serves_html_page(self):
        status, headers, body = self.request("GET", "/")
        self.assertEqual(status, 200)
        self.assertIn("text/html", headers.get("content-type", ""))
        self.assertIn("GSN Concursos", body.decode("utf-8"))

    def test_styles_css_is_served(self):
        status, headers, body = self.request("GET", "/styles.css")
        self.assertEqual(status, 200)
        self.assertIn("text/css", headers.get("content-type", ""))
        self.assertTrue(len(body) > 0)

    def test_app_js_is_served(self):
        status, headers, body = self.request("GET", "/app.js")
        self.assertEqual(status, 200)
        self.assertIn("javascript", headers.get("content-type", ""))
        self.assertIn("/api/concursos", body.decode("utf-8"))

    def test_web_prefixed_assets_are_served(self):
        status, _, _ = self.request("GET", "/web/styles.css")
        self.assertEqual(status, 200)
        status, _, _ = self.request("GET", "/web/app.js")
        self.assertEqual(status, 200)


class MethodAndPathTest(ServerTestCase):
    def test_post_to_api_returns_405(self):
        status, headers, _ = self.request("POST", "/api/concursos")
        self.assertEqual(status, 405)
        self.assertIn("GET", headers.get("allow", ""))

    def test_put_to_api_returns_405(self):
        status, _, _ = self.request("PUT", "/api/concursos")
        self.assertEqual(status, 405)

    def test_unknown_path_serves_spa_and_missing_asset_404(self):
        # O app React é uma SPA: rota de navegação sem extensão devolve o index;
        # arquivo inexistente com extensão continua 404 (não engole erro).
        status, headers, body = self.request("GET", "/nao-existe")
        self.assertEqual(status, 200)
        self.assertIn("text/html", headers.get("content-type", ""))
        self.assertIn(b"<div id=\"root\">", body)
        status, _, _ = self.request("GET", "/nao-existe.js")
        self.assertEqual(status, 404)

    def test_unknown_api_path_is_404_not_spa(self):
        # O fallback de SPA não pode mascarar rotas de API inexistentes.
        for path in ("/api/nao-existe", "/api/estudos/inexistente", "/api"):
            status, _, body = self.request("GET", path)
            self.assertEqual(status, 404, path)
            self.assertNotIn(b"<div id=\"root\">", body, path)

    def test_path_traversal_is_blocked(self):
        for path in ("/../radar/collector.py", "/web/../radar/storage.py", "/..%2fsecret"):
            status, _, body = self.request("GET", path)
            self.assertEqual(status, 404, "path %r deve ser bloqueado" % path)
            self.assertNotIn(b"def collect", body)


if __name__ == "__main__":
    unittest.main()
