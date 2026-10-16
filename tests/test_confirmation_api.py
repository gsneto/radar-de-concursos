"""Contrato HTTP e CLI da fila de confirmação (sem afetar a lista v1)."""

import http.client
import json
import tempfile
import threading
import unittest
from pathlib import Path

from radar.__main__ import build_parser
from radar.document_store import ensure_observation, migrate_document_schema, register_document
from radar.server import create_server

_TS = "2026-10-16T12:00:00+00:00"


class ConfirmationApiTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.db = str(Path(self.tmp.name) / "test.db")
        self.server = create_server(self.db, port=0)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        self.addCleanup(self.thread.join, 5)
        self.addCleanup(self.server.server_close)
        self.addCleanup(self.server.shutdown)

    def request(self, path, method="GET"):
        client = http.client.HTTPConnection("127.0.0.1", self.server.server_address[1], timeout=5)
        try:
            client.request(method, path)
            response = client.getresponse()
            return response.status, response.read()
        finally:
            client.close()

    def _seed(self):
        migrate_document_schema(self.db)
        from radar import confirmation
        observation_id = ensure_observation(
            self.db, "https://www.pciconcursos.com.br/noticias/x-1", "pci-1")
        register_document(self.db, {
            "observation_id": observation_id, "kind": "outro",
            "official_url": "https://www.pciconcursos.com.br/noticias/x-1", "title": "Concurso X",
            "discovery_url": "https://www.pciconcursos.com.br/noticias/x-1",
            "discovery_method": "automatico", "discovered_at": _TS, "issuer": "PCI Concursos (agregador)",
            "inline_content": b"<p>d</p>", "inline_content_type": "text/html"})
        confirmation.enqueue_pending(self.db)

    def test_unmigrated_confirmation_is_service_unavailable(self):
        before = self.request("/api/concursos")[1]
        self.assertEqual(self.request("/api/confirmacao")[0], 503)
        self.assertEqual(self.request("/api/concursos")[1], before)

    def test_confirmation_status_and_v1_preserved(self):
        self._seed()
        before = self.request("/api/concursos")[1]
        status, body = self.request("/api/confirmacao")
        self.assertEqual(status, 200)
        payload = json.loads(body)
        self.assertEqual(payload["counts"]["pendente"], 1)
        self.assertIn("upcoming", payload)
        self.assertEqual(self.request("/api/concursos")[1], before)

    def test_confirmation_rejects_query_and_write_methods(self):
        migrate_document_schema(self.db)
        self.assertEqual(self.request("/api/confirmacao?x=1")[0], 400)
        self.assertEqual(self.request("/api/confirmacao", method="POST")[0], 405)


class ConfirmationCliTest(unittest.TestCase):
    def test_parser_wires_confirmation_commands(self):
        parser = build_parser()
        for argv in (["confirmacao-status", "--db", "x"],
                     ["confirmacao-reconciliar", "--db", "x"],
                     ["confirmacao-lote", "--db", "x", "--limit", "3"],
                     ["confirmacao-item", "--db", "x", "--observation-id", "o"]):
            self.assertTrue(callable(parser.parse_args(argv).func), argv)


if __name__ == "__main__":
    unittest.main()
