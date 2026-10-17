"""API da revisão humana, lotes, importação e documentos bloqueados (Fase 28)."""

import base64
import http.client
import json
import sqlite3
import tempfile
import threading
import unittest
from contextlib import closing
from pathlib import Path

from radar import review
from radar.document_store import (migrate_document_schema, record_analysis, record_version,
                                  register_document)
from radar.server import create_server

NOW = "2026-10-17T12:00:00+00:00"
PDF = b"%PDF-1.4\nconteudo"


class ReviewApiTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.db = str(Path(self.tmp.name) / "api.sqlite3")
        migrate_document_schema(self.db)
        with closing(sqlite3.connect(self.db)) as conn:
            conn.execute("INSERT INTO concursos_identidade (id,created_at) "
                         "VALUES ('c','2026-10-01T00:00:00+00:00')")
            conn.execute("INSERT INTO observacoes_concurso (id,contest_id,source_url,"
                         "competition_id,observed_at) VALUES ('o','c',"
                         "'https://concursos.ibfc.org.br/informacoes/485/','ibfc-485',"
                         "'2026-10-01T00:00:00+00:00')")
            conn.commit()
        self.blocked_url = ("https://anexos.cdn.selecao.net.br/uploads/747/concursos/485/"
                            "anexos/aaa.pdf")
        self.blocked = register_document(self.db, dict(
            observation_id="o", kind="edital", official_url=self.blocked_url,
            title="Edital bloqueado", discovery_url="https://concursos.ibfc.org.br/informacoes/485/",
            discovery_method="automatico", discovered_at=NOW, published_at="2026-10-01",
            tipo_documental="edital_abertura"))
        doc = register_document(self.db, dict(
            observation_id="o", kind="edital",
            official_url="https://anexos-r2.selecao.net.br/uploads/747/concursos/485/anexos/bbb.pdf",
            title="Edital acessível", discovery_url="https://concursos.ibfc.org.br/informacoes/485/",
            discovery_method="automatico", discovered_at=NOW, published_at="2026-10-01",
            tipo_documental="edital_abertura"))
        version = record_version(self.db, doc, PDF, dict(
            fetched_at=NOW,
            fetched_url="https://anexos-r2.selecao.net.br/uploads/747/concursos/485/anexos/bbb.pdf",
            content_type="application/pdf"))
        text = "10 vagas imediatas. Inscrições até 01/11/2026."
        q1, q2 = "10 vagas imediatas", "Inscrições até 01/11/2026"
        i1, i2 = text.index(q1), text.index(q2)
        record_analysis(self.db, version,
                        [dict(text=text, start_offset=0, end_offset=len(text),
                              page_number=1, locator="p.1")],
                        [dict(contest_id="c", role_id=None, field_name="immediate_vacancies",
                              value_json="10", value_type="integer", extraction_method="regex",
                              evidence=dict(block_index=0, quote=q1, start_offset=i1,
                                            end_offset=i1 + len(q1))),
                         dict(contest_id="c", role_id=None, field_name="registration_end",
                              value_json='"2026-11-01"', value_type="string",
                              extraction_method="cronograma",
                              evidence=dict(block_index=0, quote=q2, start_offset=i2,
                                            end_offset=i2 + len(q2)))])
        self.proposal = review.review_queue(self.db, field_name="immediate_vacancies",
                                           now=NOW)["items"][0]["proposal_id"]
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

    def test_fila_paginada(self):
        status, body = self.request("/api/revisao/fila?limit=1&offset=0")
        self.assertEqual(status, 200)
        payload = json.loads(body)
        self.assertEqual(payload["total"], 2)
        self.assertEqual(len(payload["items"]), 1)
        self.assertTrue(payload["has_more"])

    def test_fila_com_filtros(self):
        status, body = self.request("/api/revisao/fila?field=registration_end")
        self.assertEqual(status, 200)
        self.assertEqual(json.loads(body)["total"], 1)

    def test_fila_recusa_parametros_invalidos(self):
        self.assertEqual(self.request("/api/revisao/fila?x=1")[0], 400)
        self.assertEqual(self.request("/api/revisao/fila?limit=0")[0], 400)
        self.assertEqual(self.request("/api/revisao/fila?state=lixo")[0], 400)
        self.assertEqual(self.request("/api/revisao/fila?conflict=2")[0], 400)

    def test_detalhe_da_proposta(self):
        status, body = self.request(f"/api/revisao/proposta/{self.proposal}")
        self.assertEqual(status, 200)
        payload = json.loads(body)
        self.assertEqual(payload["proposal"]["value"], 10)
        self.assertTrue(payload["evidence"]["quote"])
        self.assertTrue(payload["evidence_sha256"])

    def test_decidir_e_idempotente(self):
        body = json.dumps({"decision": "validado", "reviewer": "Ana",
                           "reason": "conferido"})
        first = self.request(f"/api/revisao/proposta/{self.proposal}", "POST", body)
        second = self.request(f"/api/revisao/proposta/{self.proposal}", "POST", body)
        self.assertEqual(first[0], 200)
        self.assertFalse(json.loads(first[1])["duplicada"])
        self.assertTrue(json.loads(second[1])["duplicada"])

    def test_decidir_sem_justificativa_falha(self):
        status, _ = self.request(f"/api/revisao/proposta/{self.proposal}", "POST",
                                 json.dumps({"decision": "validado", "reviewer": "Ana"}))
        self.assertEqual(status, 400)

    def test_selecionar_exige_validacao(self):
        status, _ = self.request("/api/revisao/selecionar", "POST", json.dumps({
            "proposal_id": self.proposal, "reviewer": "Ana", "reason": "cedo"}))
        self.assertEqual(status, 400)
        self.request(f"/api/revisao/proposta/{self.proposal}", "POST", json.dumps({
            "decision": "validado", "reviewer": "Ana", "reason": "conferido"}))
        status, body = self.request("/api/revisao/selecionar", "POST", json.dumps({
            "proposal_id": self.proposal, "reviewer": "Ana", "reason": "vigente"}))
        self.assertEqual(status, 200)
        self.assertFalse(json.loads(body)["duplicada"])

    def test_lote_abre_navega_e_exporta(self):
        status, body = self.request("/api/revisao/lotes", "POST",
                                    json.dumps({"created_by": "Ana", "size": 2}))
        self.assertEqual(status, 200)
        lote = json.loads(body)
        lote_id = lote["lote_id"]
        self.assertEqual(lote["progresso"]["total"], 2)
        status, body = self.request(f"/api/revisao/lotes/{lote_id}/exportar")
        self.assertEqual(status, 200)
        self.assertEqual(len(json.loads(body)["itens"]), 2)
        status, body = self.request(f"/api/revisao/lotes/{lote_id}", "POST",
                                    json.dumps({"action": "pausar"}))
        self.assertEqual(json.loads(body)["state"], "pausado")

    def test_lote_inexistente_falha(self):
        self.assertEqual(self.request("/api/revisao/lotes/nao-existe")[0], 400)

    def test_importar_dry_run(self):
        _, body = self.request("/api/revisao/lotes", "POST",
                               json.dumps({"created_by": "Ana", "size": 2}))
        lote_id = json.loads(body)["lote_id"]
        _, exported = self.request(f"/api/revisao/lotes/{lote_id}/exportar")
        payload = json.loads(exported)
        payload["itens"][0]["decision"] = "validado"
        status, body = self.request("/api/revisao/importar", "POST", json.dumps({
            "payload": payload, "reviewer": "Ana", "reason": "importado"}))
        self.assertEqual(status, 200)
        self.assertTrue(json.loads(body)["dry_run"])
        self.assertEqual(json.loads(body)["aplicados"], 1)

    def test_documentos_bloqueados(self):
        from radar import document_ingest
        document_ingest.record_policy_block(
            self.db, self.blocked, "robots_disallow_anexos_cdn", detected_at=NOW)
        status, body = self.request("/api/documentos/bloqueados")
        self.assertEqual(status, 200)
        payload = json.loads(body)
        self.assertEqual(payload["por_estado"]["politica_robots"], 1)
        item = next(i for i in payload["itens"] if i["document_id"] == self.blocked)
        self.assertIn("alternatives", item)

    def test_importacao_manual_dry_run(self):
        status, body = self.request("/api/documentos/importar", "POST", json.dumps({
            "document_id": self.blocked,
            "content_base64": base64.b64encode(PDF).decode("ascii"),
            "declared_origin": "download manual", "declared_by": "Anton"}))
        self.assertEqual(status, 200)
        self.assertTrue(json.loads(body)["dry_run"])
        with closing(sqlite3.connect(self.db)) as conn:
            self.assertEqual(conn.execute(
                "SELECT COUNT(*) FROM ingestoes_documentais").fetchone()[0], 0)

    def test_importacao_manual_grava_com_hash(self):
        status, body = self.request("/api/documentos/importar", "POST", json.dumps({
            "document_id": self.blocked,
            "content_base64": base64.b64encode(PDF).decode("ascii"),
            "declared_origin": "download manual", "declared_by": "Anton",
            "dry_run": False}))
        self.assertEqual(status, 200)
        payload = json.loads(body)
        self.assertFalse(payload["duplicada"])
        with closing(sqlite3.connect(self.db)) as conn:
            self.assertEqual(conn.execute(
                "SELECT COUNT(*) FROM ingestoes_documentais").fetchone()[0], 1)

    def test_importacao_manual_recusa_base64_invalido(self):
        status, _ = self.request("/api/documentos/importar", "POST", json.dumps({
            "document_id": self.blocked, "content_base64": "não é base64",
            "declared_origin": "x", "declared_by": "Anton"}))
        self.assertEqual(status, 400)

    def test_rejeitar_associacao_sem_certame(self):
        from radar import identity
        from radar.document_store import connect_documents
        from contextlib import closing
        status, body = self.request(
            f"/api/associacoes/{self.blocked}", "POST",
            json.dumps({"state": "rejeitada", "decided_by": "Ana",
                        "note": "não há certame identificável"}))
        self.assertEqual(status, 200)
        with closing(connect_documents(self.db)) as conn:
            self.assertEqual(identity.current_association(conn, self.blocked)["state"],
                             "rejeitada")
            self.assertIsNone(identity.current_association(conn, self.blocked)["contest_id"])

    def test_contrato_v1_intacto(self):
        from radar.storage import CONTRACT_FIELDS
        self.assertEqual(len(CONTRACT_FIELDS), 18)
        self.assertEqual(json.loads(self.request("/api/concursos")[1]), [])


if __name__ == "__main__":
    unittest.main()
