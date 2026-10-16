"""Contrato HTTP e CLI da operação autônoma (alertas e saúde), sem afetar a v1."""

import http.client
import json
import tempfile
import threading
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

from radar.__main__ import build_parser
from radar import ops
from radar.document_store import ensure_observation, migrate_document_schema, register_document
from radar.server import create_server

_TS = "2026-10-16T12:00:00+00:00"


class OpsApiTest(unittest.TestCase):
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

    def request(self, path, method="GET", body=None):
        client = http.client.HTTPConnection("127.0.0.1", self.server.server_address[1], timeout=5)
        try:
            headers = {"Content-Type": "application/json"} if body is not None else {}
            client.request(method, path, body=body, headers=headers)
            response = client.getresponse()
            return response.status, response.read()
        finally:
            client.close()

    def _seed_alert(self):
        migrate_document_schema(self.db)
        ops.generate_alerts(self.db, now=ops._now())
        from radar.document_store import connect_documents
        from contextlib import closing
        with closing(connect_documents(self.db)) as conn:
            conn.execute("BEGIN IMMEDIATE")
            ops._insert_alert(conn, kind="novo_candidato", severity="info",
                              dedup_key="k1", title="Novo candidato")
            conn.commit()

    def test_alerts_endpoint_lists_and_counts(self):
        self._seed_alert()
        before = self.request("/api/concursos")[1]
        status, body = self.request("/api/alertas")
        self.assertEqual(status, 200)
        payload = json.loads(body)
        self.assertEqual(payload["counts"]["total"], 1)
        self.assertEqual(payload["alerts"][0]["title"], "Novo candidato")
        self.assertEqual(self.request("/api/concursos")[1], before)  # v1 intacto

    def test_alerts_unseen_filter(self):
        self._seed_alert()
        status, body = self.request("/api/alertas?unseen=1")
        self.assertEqual(status, 200)
        self.assertEqual(len(json.loads(body)["alerts"]), 1)

    def test_alerts_rejects_bad_query(self):
        migrate_document_schema(self.db)
        self.assertEqual(self.request("/api/alertas?x=1")[0], 400)
        self.assertEqual(self.request("/api/alertas?limit=abc")[0], 400)
        self.assertEqual(self.request("/api/alertas", method="POST")[0], 405)

    def test_health_endpoint(self):
        migrate_document_schema(self.db)
        status, body = self.request("/api/saude")
        self.assertEqual(status, 200)
        payload = json.loads(body)
        self.assertIn("status", payload)
        self.assertIn("database", payload)

    def test_unmigrated_alerts_is_service_unavailable(self):
        self.assertEqual(self.request("/api/alertas")[0], 503)

    def test_triage_endpoint(self):
        self._seed_alert()
        before = self.request("/api/concursos")[1]
        status, body = self.request("/api/triagem")
        self.assertEqual(status, 200)
        payload = json.loads(body)
        self.assertIn("groups", payload)
        self.assertIn("counts", payload)
        self.assertEqual(self.request("/api/concursos")[1], before)  # v1 intacto

    def test_alert_action_marks_seen(self):
        self._seed_alert()
        alert_id = json.loads(self.request("/api/alertas")[1])["alerts"][0]["id"]
        status, _ = self.request(f"/api/alertas/{alert_id}", method="POST",
                                 body=json.dumps({"action": "seen"}))
        self.assertEqual(status, 200)
        after = json.loads(self.request("/api/alertas")[1])
        self.assertEqual(after["counts"]["unseen"], 0)

    def test_alert_action_snooze_and_reopen(self):
        self._seed_alert()
        alert_id = json.loads(self.request("/api/alertas")[1])["alerts"][0]["id"]
        future = (datetime.now(timezone.utc) + timedelta(days=2)).isoformat()
        self.assertEqual(self.request(f"/api/alertas/{alert_id}", method="POST",
                                      body=json.dumps({"action": "snooze", "until": future}))[0], 200)
        self.assertEqual(json.loads(self.request("/api/triagem")[1])["groups"], [])
        self.assertEqual(self.request(f"/api/alertas/{alert_id}", method="POST",
                                      body=json.dumps({"action": "reopen"}))[0], 200)

    def test_alert_action_rejects_bad_requests(self):
        self._seed_alert()
        alert_id = json.loads(self.request("/api/alertas")[1])["alerts"][0]["id"]
        self.assertEqual(self.request(f"/api/alertas/{alert_id}", method="POST",
                                      body=json.dumps({"action": "x"}))[0], 400)
        self.assertEqual(self.request(f"/api/alertas/{alert_id}", method="POST",
                                      body=json.dumps({"action": "snooze"}))[0], 400)
        self.assertEqual(self.request("/api/alertas/inexistente", method="POST",
                                      body=json.dumps({"action": "seen"}))[0], 404)
        self.assertEqual(self.request("/api/alertas", method="POST",
                                      body=json.dumps({"action": "seen"}))[0], 405)


class OpsCliTest(unittest.TestCase):
    def test_parser_wires_ops_commands(self):
        parser = build_parser()
        for argv in (["ops-ciclo"], ["ops-saude"], ["ops-alertas", "--unseen"],
                     ["ops-alerta-marcar", "--id", "x"], ["ops-config", "--write"]):
            self.assertTrue(callable(parser.parse_args(argv).func), argv)


if __name__ == "__main__":
    unittest.main()
