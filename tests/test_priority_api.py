"""API aditiva de priorização e preferências, sem afetar o contrato v1."""

import http.client
import json
import tempfile
import threading
import unittest
from contextlib import closing
from datetime import datetime, timezone
from pathlib import Path

from radar.document_store import (connect_documents, ensure_observation, migrate_document_schema,
                                  record_analysis, record_version, register_document)
from radar.server import create_server


def _now():
    return datetime.now(timezone.utc).isoformat()


class PriorityApiTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        root = Path(self.tmp.name)
        self.db = str(root / "test.db")
        self.config = str(root / "radar_ops.json")
        migrate_document_schema(self.db)
        self._seed_contest("k1", [("indigenous_vacancies", 4),
                                  ("si_compatibility", "aceito_expressamente"),
                                  ("exam_location", "Salvador/BA")])
        self.server = create_server(self.db, port=0, config_path=self.config)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        self.addCleanup(self.thread.join, 5)
        self.addCleanup(self.server.server_close)
        self.addCleanup(self.server.shutdown)

    def _seed_contest(self, key, proposals):
        obs = ensure_observation(self.db, f"https://exemplo.test/{key}", key)
        with closing(connect_documents(self.db)) as conn:
            contest_id = conn.execute("SELECT contest_id FROM observacoes_concurso WHERE id=?",
                                      (obs,)).fetchone()[0]
        did = register_document(self.db, dict(
            observation_id=obs, kind="outro", official_url=f"https://exemplo.test/{key}/e.pdf",
            title="Edital", discovery_url=f"https://exemplo.test/{key}",
            discovery_method="automatico", discovered_at=_now()))
        blocks = [{"page_number": 1, "locator": "p", "start_offset": 0, "end_offset": 1, "text": "x"}]
        props = [dict(contest_id=contest_id, role_id=None, field_name=f,
                      value_json=json.dumps(v), value_type="string" if isinstance(v, str) else "integer",
                      extraction_method="t", ambiguity_reason=None,
                      evidence=dict(block_index=0, quote="x", start_offset=0, end_offset=1))
                 for f, v in proposals]
        version = record_version(self.db, did, b"%PDF-1.4 x", dict(
            fetched_at=_now(), fetched_url=f"https://exemplo.test/{key}/e.pdf",
            content_type="application/pdf"))
        record_analysis(self.db, version, blocks, props)

    def request(self, path, method="GET", body=None):
        client = http.client.HTTPConnection("127.0.0.1", self.server.server_address[1], timeout=5)
        try:
            headers = {"Content-Type": "application/json"} if body is not None else {}
            client.request(method, path, body=body, headers=headers)
            response = client.getresponse()
            return response.status, response.read()
        finally:
            client.close()

    def test_prioridades_endpoint(self):
        before = self.request("/api/concursos")[1]
        status, body = self.request("/api/prioridades")
        self.assertEqual(status, 200)
        payload = json.loads(body)
        self.assertIn("items", payload)
        self.assertTrue(payload["items"])
        item = payload["items"][0]
        self.assertIn("factors", item)
        self.assertIn("location", item)
        self.assertIn("distance", item)
        self.assertEqual(self.request("/api/concursos")[1], before)  # v1 intacto

    def test_prioridades_rejects_bad_query(self):
        self.assertEqual(self.request("/api/prioridades?x=1")[0], 400)
        self.assertEqual(self.request("/api/prioridades?limit=abc")[0], 400)
        self.assertEqual(self.request("/api/prioridades", method="POST")[0], 405)

    def test_preferencias_get_defaults(self):
        status, body = self.request("/api/preferencias")
        self.assertEqual(status, 200)
        payload = json.loads(body)
        self.assertEqual(payload["interest_states"], ["BA", "PE"])

    def test_preferencias_post_persists_and_reflects(self):
        status, body = self.request("/api/preferencias", method="POST", body=json.dumps({
            "reference_uf": "BA", "reference_municipio": "Salvador",
            "interest_states": ["BA"], "practical_distance_km": 200, "priority": "potencial"}))
        self.assertEqual(status, 200)
        saved = json.loads(body)
        self.assertEqual(saved["reference_uf"], "BA")
        # GET reflete o que foi salvo (persistiu no arquivo de config temporário).
        status, body = self.request("/api/preferencias")
        self.assertEqual(json.loads(body)["reference_municipio"], "Salvador")

    def test_preferencias_post_rejects_invalid(self):
        status, body = self.request("/api/preferencias", method="POST",
                                    body=json.dumps({"reference_uf": "ZZ"}))
        self.assertEqual(status, 400)
        self.assertIn("error", json.loads(body))

    def test_preferencias_post_rejects_bad_body(self):
        self.assertEqual(self.request("/api/preferencias", method="POST", body="not-json")[0], 400)
        self.assertEqual(self.request("/api/preferencias?x=1", method="POST",
                                      body=json.dumps({}))[0], 400)

    def test_preferences_do_not_leak_into_v1(self):
        self.request("/api/preferencias", method="POST", body=json.dumps({"reference_uf": "BA"}))
        payload = json.loads(self.request("/api/concursos")[1])
        for record in payload:
            self.assertNotIn("preferences", record)
            self.assertEqual(len(record), 18)  # contrato v1 preservado

    def test_prioridades_rejects_non_positive_limit(self):
        self.assertEqual(self.request("/api/prioridades?limit=0")[0], 400)
        self.assertEqual(self.request("/api/prioridades?limit=-5")[0], 400)

    def test_preferencias_preserves_other_config_keys(self):
        # Regressão I6: gravar preferências não pode apagar o restante do config.
        with open(self.config, "w", encoding="utf-8") as fh:
            json.dump({"db_path": "data/radar.sqlite3", "batch_limit": 10}, fh)
        self.request("/api/preferencias", method="POST", body=json.dumps({"reference_uf": "PE"}))
        saved = json.loads(Path(self.config).read_text(encoding="utf-8"))
        self.assertEqual(saved["db_path"], "data/radar.sqlite3")
        self.assertEqual(saved["batch_limit"], 10)
        self.assertEqual(saved["preferences"]["reference_uf"], "PE")

    def test_preferencias_write_failure_returns_500(self):
        # Regressão I7: falha de escrita não pode derrubar a conexão sem resposta.
        bad = create_server(self.db, port=0, config_path=str(Path(self.tmp.name) / "nope" / "c.json"))
        thread = threading.Thread(target=bad.serve_forever, daemon=True)
        thread.start()
        try:
            client = http.client.HTTPConnection("127.0.0.1", bad.server_address[1], timeout=5)
            client.request("POST", "/api/preferencias", body=json.dumps({"reference_uf": "BA"}),
                           headers={"Content-Type": "application/json"})
            response = client.getresponse()
            status = response.status
            response.read()
            client.close()
        finally:
            bad.shutdown()
            bad.server_close()
            thread.join(5)
        self.assertEqual(status, 500)


if __name__ == "__main__":
    unittest.main()
