"""API de cobertura, lacunas e materialização de papéis (Fase 25)."""

import http.client
import json
import tempfile
import threading
import unittest
from contextlib import closing
from pathlib import Path
from uuid import uuid4

from radar.document_store import connect_documents, migrate_document_schema
from radar.storage import CONTRACT_FIELDS
from radar.server import create_server

NOW = "2026-10-17T12:00:00+00:00"
LABEL = "cargo do documento não reconciliado: "


class CoverageApiTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.db = str(Path(self.tmp.name) / "api.sqlite3")
        migrate_document_schema(self.db)
        self._seed()
        self.server = create_server(self.db, port=0)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        self.addCleanup(self.thread.join, 5)
        self.addCleanup(self.server.server_close)
        self.addCleanup(self.server.shutdown)

    def _write(self, sql, params):
        with closing(connect_documents(self.db)) as conn, conn:
            conn.execute(sql, params)

    def _seed(self):
        self._write("INSERT INTO concursos_identidade (id,created_at) VALUES (?,?)",
                    ("c1", NOW))
        obs, doc, version = str(uuid4()), str(uuid4()), str(uuid4())
        block, evidence, proposal = str(uuid4()), str(uuid4()), str(uuid4())
        self._write(
            "INSERT INTO observacoes_concurso (id,contest_id,source_url,competition_id,"
            "observed_at) VALUES (?,?,?,?,?)",
            (obs, "c1", "https://oficial.test/", "obs-1", NOW))
        self._write(
            "INSERT INTO documentos (id,contest_id,observation_id,kind,official_url,title,"
            "discovered_at,discovery_url,discovery_method) VALUES (?,?,?,?,?,?,?,?,?)",
            (doc, "c1", obs, "edital", "https://oficial.test/a", "Edital", NOW,
             "https://oficial.test/", "manual"))
        self._write(
            "INSERT INTO versoes_documento (id,document_id,sha256,fetched_at,fetched_url,"
            "content_type,byte_size,local_path,extraction_state) VALUES (?,?,?,?,?,?,?,?,?)",
            (version, doc, "a" * 64, NOW, "https://oficial.test/a", "application/pdf", 10,
             "x", "parcial"))
        self._write(
            "INSERT INTO blocos_documento (id,version_id,page_number,locator,start_offset,"
            "end_offset,text) VALUES (?,?,?,?,?,?,?)",
            (block, version, 1, "p1", 0, 6, "trecho"))
        self._write(
            "INSERT INTO evidencias (id,version_id,block_id,quote,page_number,locator,"
            "start_offset,end_offset,captured_at) VALUES (?,?,?,?,?,?,?,?,?)",
            (evidence, version, block, "trecho", 1, "p1", 0, 6, NOW))
        self._write(
            "INSERT INTO propostas_campo (id,contest_id,role_id,field_name,value_json,"
            "value_type,evidence_id,extraction_method,ambiguity_reason,extracted_at) "
            "VALUES (?,?,?,?,?,?,?,?,?,?)",
            (proposal, "c1", None, "immediate_vacancies", "10", "integer", evidence,
             "tabela", LABEL + "Cargo A", NOW))

    def request(self, path, method="GET", body=None):
        client = http.client.HTTPConnection("127.0.0.1", self.server.server_address[1],
                                            timeout=5)
        try:
            headers = {"Content-Type": "application/json"} if body is not None else {}
            client.request(method, path, body=body, headers=headers)
            response = client.getresponse()
            return response.status, response.read()
        finally:
            client.close()

    def test_cobertura_completa(self):
        status, body = self.request("/api/cobertura")
        self.assertEqual(status, 200)
        payload = json.loads(body)
        self.assertEqual(payload["version"], "coverage_v1")
        self.assertEqual(payload["escopo"]["concursos"], 1)
        self.assertEqual(payload["escopo"]["com_edital_oficial"], 1)
        self.assertIn("dimensoes", payload)
        self.assertIn("causas", payload)

    def test_resumo(self):
        status, body = self.request("/api/cobertura/resumo")
        self.assertEqual(status, 200)
        payload = json.loads(body)
        self.assertIn("dimensoes_obrigatorias", payload)
        self.assertTrue(payload["limitacoes"])

    def test_lacunas(self):
        status, body = self.request("/api/lacunas?limit=5")
        self.assertEqual(status, 200)
        payload = json.loads(body)
        self.assertEqual(payload["total"], 1)
        self.assertEqual(payload["itens"][0]["contest_id"], "c1")
        self.assertEqual(payload["itens"][0]["tipo_tarefa"], "revisao_humana")

    def test_papeis_dry_run_nao_grava(self):
        status, body = self.request("/api/cobertura/papeis", "POST",
                                    json.dumps({"dry_run": True}))
        self.assertEqual(status, 200)
        self.assertTrue(json.loads(body)["dry_run"])
        with closing(connect_documents(self.db)) as conn:
            self.assertEqual(conn.execute("SELECT COUNT(*) FROM cargos_identidade").fetchone()[0], 0)

    def test_papeis_aplica(self):
        status, body = self.request("/api/cobertura/papeis", "POST",
                                    json.dumps({"dry_run": False}))
        self.assertEqual(status, 200)
        self.assertEqual(json.loads(body)["identidades_criadas"], 1)
        with closing(connect_documents(self.db)) as conn:
            row = conn.execute("SELECT name FROM cargos_identidade").fetchone()
        self.assertEqual(row[0], "Cargo A")

    def test_entradas_invalidas(self):
        self.assertEqual(self.request("/api/lacunas?limit=0")[0], 400)
        self.assertEqual(self.request("/api/lacunas?x=1")[0], 400)
        self.assertEqual(self.request("/api/cobertura?x=1")[0], 400)
        self.assertEqual(self.request("/api/cobertura/resumo?x=1")[0], 400)
        self.assertEqual(self.request("/api/cobertura/papeis?x=1", "POST", "{}")[0], 400)

    def test_contrato_v1_intacto(self):
        self.assertEqual(len(CONTRACT_FIELDS), 18, "contrato v1 tem exatamente 18 campos")
        status, body = self.request("/api/concursos")
        self.assertEqual(status, 200)
        self.assertIsInstance(json.loads(body), list)
        # a auditoria é aditiva: nenhum campo novo vaza para o contrato v1
        status, coverage = self.request("/api/cobertura")
        self.assertEqual(status, 200)
        payload = json.loads(coverage)
        for field in CONTRACT_FIELDS:
            self.assertNotIn(field, payload, "auditoria não deve expor campo do contrato v1")
        self.assertNotIn("dimensoes", json.loads(self.request("/api/concursos")[1]))


if __name__ == "__main__":
    unittest.main()
