"""Contrato HTTP de monitoramento, sem afetar a lista v1."""

import http.client
import json
import tempfile
import threading
import unittest
from pathlib import Path

from radar.collector import SOURCE_URL, collect
from radar.document_store import migrate_document_schema
from radar.monitoring import run_cycle
from radar.server import create_server
from radar.storage import upsert_records

_FIXTURE = Path(__file__).parent / "fixtures" / "guajara-oficial.html"
_TS = "2026-10-15T12:00:00+00:00"


class MonitoringApiTest(unittest.TestCase):
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

    def test_unmigrated_status_is_service_unavailable_and_v1_untouched(self):
        before = self.request("/api/concursos")[1]
        self.assertEqual(self.request("/api/monitoramento")[0], 503)
        self.assertEqual(self.request("/api/concursos")[1], before)

    def test_status_after_cycle_and_v1_preserved(self):
        upsert_records(self.db, collect(_FIXTURE.read_text(encoding="utf-8"), _TS))
        migrate_document_schema(self.db)
        before = self.request("/api/concursos")[1]
        url = "https://guajaramirim.ro.gov.br/e.pdf"

        def discover(html, observation_id):
            return [dict(observation_id=observation_id, kind="edital", official_url=url, title="Edital",
                         discovery_url=SOURCE_URL, discovery_method="automatico", discovered_at=_TS)]

        def transport(u, timeout, limit):
            return dict(status=200, final_url=u, content_type="application/pdf", peer_ip="8.8.8.8", body=b"%PDF-1.4\nx")

        run_cycle(self.db, sources=[{"source_url": SOURCE_URL, "fetch": lambda: "x", "discover": discover}],
                  transport=transport)
        status, body = self.request("/api/monitoramento")
        self.assertEqual(status, 200)
        payload = json.loads(body)
        self.assertEqual(payload["last_cycle"]["state"], "concluido")
        self.assertEqual(payload["last_cycle"]["documents_new"], 1)
        self.assertEqual(len(payload["sources"]), 1)
        self.assertEqual(payload["sources"][0]["source_url"], SOURCE_URL)
        self.assertNotIn(b"local_path", body)
        self.assertEqual(self.request("/api/concursos")[1], before)

    def test_status_rejects_query_and_write_methods(self):
        migrate_document_schema(self.db)
        self.assertEqual(self.request("/api/monitoramento?x=1")[0], 400)
        self.assertEqual(self.request("/api/monitoramento", method="POST")[0], 405)


if __name__ == "__main__":
    unittest.main()
