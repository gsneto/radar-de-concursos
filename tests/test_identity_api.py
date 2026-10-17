"""API de identidade, fila de associações e reparação (Fase 27)."""

import http.client
import json
import tempfile
import threading
import unittest
from contextlib import closing
from pathlib import Path

from radar.document_store import (
    connect_documents,
    ensure_observation,
    migrate_document_schema,
    register_document,
)
from radar.server import create_server

NOW = "2026-10-17T12:00:00+00:00"


class IdentityApiTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.db = str(Path(self.tmp.name) / "api.sqlite3")
        migrate_document_schema(self.db)
        self.container = ensure_observation(
            self.db, "https://www.in.gov.br/leiturajornal?secao=do3", "DOU-S3")
        self.certame = ensure_observation(
            self.db, "https://conhecimento.fgv.br/concursos/x", "tjap26")
        self.document_id = register_document(self.db, {
            "observation_id": self.container, "kind": "edital",
            "official_url": "https://www.in.gov.br/web/dou/-/a",
            "title": "EDITAL Nº 8", "discovery_url": "https://www.in.gov.br/x",
            "discovery_method": "automatico", "discovered_at": NOW,
            "issuer": "Orgao A", "published_at": "2026-10-15"})
        self.server = create_server(self.db, port=0)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        self.addCleanup(self.thread.join, 5)
        self.addCleanup(self.server.server_close)
        self.addCleanup(self.server.shutdown)

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

    def _contest(self):
        with closing(connect_documents(self.db)) as conn:
            return conn.execute("SELECT contest_id FROM observacoes_concurso WHERE id=?",
                                (self.certame,)).fetchone()[0]

    def test_identidade(self):
        status, body = self.request("/api/identidade")
        self.assertEqual(status, 200)
        payload = json.loads(body)
        self.assertEqual(payload["concursos"], 2)
        self.assertEqual(payload["containers"], 1)
        self.assertEqual(payload["certames"], 1)

    def test_fila_de_associacoes(self):
        status, body = self.request("/api/associacoes/fila?limit=10")
        self.assertEqual(status, 200)
        payload = json.loads(body)
        self.assertEqual(payload["total"], 1)
        self.assertEqual(payload["itens"][0]["estado"], "pendente")

    def test_fila_filtra_estado(self):
        status, body = self.request("/api/associacoes/fila?state=confirmada")
        self.assertEqual(status, 200)
        self.assertEqual(json.loads(body)["total"], 0)

    def test_revisar_associacao(self):
        contest = self._contest()
        status, body = self.request(
            f"/api/associacoes/{self.document_id}", "POST",
            json.dumps({"state": "confirmada", "contest_id": contest,
                        "decided_by": "revisor", "note": "confere"}))
        self.assertEqual(status, 200)
        self.assertFalse(json.loads(body)["duplicada"])
        with closing(connect_documents(self.db)) as conn:
            from radar.identity import current_association
            self.assertEqual(current_association(conn, self.document_id)["state"],
                             "confirmada")

    def test_revisar_sem_autor_falha(self):
        status, _ = self.request(
            f"/api/associacoes/{self.document_id}", "POST",
            json.dumps({"state": "confirmada", "contest_id": self._contest()}))
        self.assertEqual(status, 400)

    def test_reparar_dry_run(self):
        status, body = self.request("/api/identidade/reparar", "POST",
                                    json.dumps({"decided_by": "r", "note": "n"}))
        self.assertEqual(status, 200)
        self.assertTrue(json.loads(body)["dry_run"])
        with closing(connect_documents(self.db)) as conn:
            # dry-run não cria associação nova além da pendência já registrada
            self.assertEqual(conn.execute(
                "SELECT COUNT(*) FROM associacoes_documento").fetchone()[0], 1)

    def _contest_container(self):
        with closing(connect_documents(self.db)) as conn:
            return conn.execute("SELECT contest_id FROM observacoes_concurso WHERE id=?",
                                (self.container,)).fetchone()[0]

    def test_entradas_invalidas(self):
        self.assertEqual(self.request("/api/identidade?x=1")[0], 400)
        self.assertEqual(self.request("/api/associacoes/fila?limit=0")[0], 400)
        self.assertEqual(self.request("/api/associacoes/fila?x=1")[0], 400)
        self.assertEqual(self.request("/api/associacoes/fila?state=lixo")[0], 400)
        self.assertEqual(self.request("/api/identidade/reparar?x=1", "POST", "{}")[0], 400)
        self.assertEqual(self.request("/api/associacoes/", "POST", "{}")[0], 404)

    def test_contrato_v1_intacto(self):
        from radar.storage import CONTRACT_FIELDS
        self.assertEqual(CONTRACT_FIELDS, (
            "competition_id", "competition", "agency", "role", "education",
            "immediate_vacancies", "reserve_vacancies", "indigenous_vacancies",
            "registration_start", "registration_end", "registration_status", "exam_date",
            "exam_location", "work_location", "source_name", "source_url", "evidence_url",
            "verified_at"))
        self.assertEqual(json.loads(self.request("/api/concursos")[1]), [])


if __name__ == "__main__":
    unittest.main()
