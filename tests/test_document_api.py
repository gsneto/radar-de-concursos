"""Contrato HTTP documental sem efeito colateral na lista v1."""

import http.client
import json
import tempfile
import threading
import unittest
from pathlib import Path

from radar.collector import collect
from radar.document_store import migrate_document_schema, sync_v1_identifiers
from radar.server import create_server
from radar.storage import upsert_records


class DocumentApiTest(unittest.TestCase):
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

    def test_unmigrated_details_and_index_are_read_only(self):
        before = self.request("/api/concursos")[1]
        self.assertEqual(self.request("/api/concursos/identidades")[0], 503)
        self.assertEqual(self.request("/api/concursos/00000000-0000-4000-8000-000000000001/detalhes")[0], 503)
        self.assertEqual(self.request("/api/concursos")[1], before)
        self.assertFalse(Path(self.db).exists())

    def test_index_and_details_require_explicit_sync(self):
        html = (Path(__file__).parent / "fixtures" / "guajara-oficial.html").read_text(encoding="utf-8")
        upsert_records(self.db, collect(html, "2026-10-10T12:00:00+00:00"))
        before = self.request("/api/concursos")[1]
        migrate_document_schema(self.db)
        self.assertEqual(json.loads(self.request("/api/concursos/identidades")[1]), [])
        sync_v1_identifiers(self.db)
        status, body = self.request("/api/concursos/identidades")
        self.assertEqual(status, 200)
        identity = json.loads(body)[0]
        status, body = self.request(f"/api/concursos/{identity['id']}/detalhes")
        self.assertEqual(status, 200)
        detail = json.loads(body)
        self.assertEqual(len(detail["roles"]), 4)
        self.assertEqual(detail["coverage"]["state"], "nao_auditada")
        self.assertEqual(detail["documents"], [])
        self.assertNotIn(b"local_path", body)
        self.assertEqual(self.request("/api/concursos")[1], before)

    def test_invalid_and_missing_uuid(self):
        migrate_document_schema(self.db)
        self.assertEqual(self.request("/api/concursos/not-an-id/detalhes")[0], 400)
        self.assertEqual(self.request("/api/concursos/00000000-0000-4000-8000-000000000001/detalhes")[0], 404)
        self.assertEqual(self.request("/api/concursos/identidades/detalhes")[0], 400)
        self.assertEqual(self.request("/api/concursos/identidades", method="POST")[0], 405)
        self.assertEqual(self.request("/api/concursos/00000000-0000-4000-8000-000000000001/detalhes", method="HEAD")[0], 405)
