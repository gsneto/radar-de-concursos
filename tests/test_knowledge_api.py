"""API e integração da Fase 22: conteúdo, perfil, preparação, lacuna, exportar/importar."""

import http.client
import json
import tempfile
import threading
import unittest
from contextlib import closing
from datetime import datetime, timezone
from pathlib import Path

from radar import knowledge_store, program_content, study_store
from radar.document_store import (connect_documents, ensure_observation, migrate_document_schema,
                                  record_analysis, record_version, register_document)
from radar.server import create_server


def _now():
    return datetime.now(timezone.utc).isoformat()


class KnowledgeApiTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.db = str(Path(self.tmp.name) / "t.sqlite3")
        migrate_document_schema(self.db)
        obs = ensure_observation(self.db, "https://exemplo.test/c1", "c1")
        with closing(connect_documents(self.db)) as conn:
            self.contest = conn.execute("SELECT contest_id FROM observacoes_concurso WHERE id=?",
                                        (obs,)).fetchone()[0]
        text = ("CONHECIMENTOS ESPECÍFICOS\nINFORMÁTICA\n1 Redes de computadores\n2 Banco de dados")
        did = register_document(self.db, dict(
            observation_id=obs, kind="outro", official_url="https://exemplo.test/c1/e.pdf",
            title="Edital", discovery_url="https://exemplo.test/c1",
            discovery_method="automatico", discovered_at=_now()))
        blocks = [{"page_number": 1, "locator": "p", "start_offset": 0,
                   "end_offset": len(text), "text": text}]
        props = program_content.extract_program_content(blocks, self.contest, label_prefix="x: ")
        version = record_version(self.db, did, b"%PDF-1.4 " + text.encode(), dict(
            fetched_at=_now(), fetched_url="https://exemplo.test/c1/e.pdf",
            content_type="application/pdf"))
        record_analysis(self.db, version, blocks, props)
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

    def test_conteudo_endpoint(self):
        v1_before = self.request("/api/concursos")[1]
        status, body = self.request(f"/api/estudos/conteudo?contest_id={self.contest}")
        self.assertEqual(status, 200)
        payload = json.loads(body)
        self.assertEqual(len(payload["topicos"]), 2)
        self.assertEqual(self.request("/api/concursos")[1], v1_before)  # v1 intacta

    def test_conteudo_exige_contest_id(self):
        self.assertEqual(self.request("/api/estudos/conteudo")[0], 400)
        self.assertEqual(self.request("/api/estudos/conteudo?x=1")[0], 400)

    def test_perfil_get_post(self):
        self.assertEqual(json.loads(self.request("/api/estudos/perfil")[1]), [])
        status, body = self.request("/api/estudos/perfil", "POST", json.dumps({
            "disciplina": "INFORMÁTICA", "rotulo": "Redes de computadores", "nivel": "basico"}))
        self.assertEqual(status, 200)
        self.assertEqual(json.loads(body)["nivel"], "basico")
        self.assertEqual(len(json.loads(self.request("/api/estudos/perfil")[1])), 1)

    def test_perfil_nivel_invalido(self):
        status, body = self.request("/api/estudos/perfil", "POST", json.dumps({
            "disciplina": "X", "rotulo": "Y", "nivel": "expert"}))
        self.assertEqual(status, 400)
        self.assertIn("error", json.loads(body))

    def test_preparacao_endpoint(self):
        self.request("/api/estudos/perfil", "POST", json.dumps({
            "disciplina": "INFORMÁTICA", "rotulo": "Redes de computadores", "nivel": "basico"}))
        status, body = self.request(f"/api/estudos/preparacao?contest_id={self.contest}")
        self.assertEqual(status, 200)
        payload = json.loads(body)
        self.assertEqual(payload["coverage"]["denominator"], 2)
        self.assertEqual(payload["coverage"]["pct"], 50)
        self.assertTrue(any(g["rotulo"] == "Banco de dados" for g in payload["gaps"]))
        self.assertIn("perspective", payload)  # classificação em três perspectivas exposta

    def test_importar_payload_invalido_nao_derruba_conexao(self):
        # Regressão: payload que passa na validação não pode causar exceção não tratada.
        payload = {"format": "radar-estudos", "format_version": 1, "data": {
            "disciplinas": [], "topicos": [], "progresso": [], "sessoes": [], "revisoes": [],
            "perfil": [{"conceito_key": "k", "nivel": "basico"}]}}
        status, body = self.request("/api/estudos/importar", "POST", json.dumps({"payload": payload}))
        self.assertEqual(status, 400)
        self.assertFalse(json.loads(body)["ok"])

    def test_lacuna_para_estudos(self):
        status, body = self.request(f"/api/estudos/conteudo?contest_id={self.contest}")
        key = next(t["conceito_key"] for t in json.loads(body)["topicos"] if t["value"] == "Banco de dados")
        status, body = self.request("/api/estudos/lacuna", "POST", json.dumps({
            "contest_id": self.contest, "conceito_key": key}))
        self.assertEqual(status, 200)
        self.assertTrue(json.loads(body)["created"])
        # Idempotente: segunda vez não cria.
        status, body = self.request("/api/estudos/lacuna", "POST", json.dumps({
            "contest_id": self.contest, "conceito_key": key}))
        self.assertFalse(json.loads(body)["created"])
        self.assertEqual(len(study_store.list_disciplinas(self.db)), 1)
        self.assertEqual(len(study_store.list_topicos(self.db)), 1)

    def test_exportar_endpoint(self):
        status, body = self.request("/api/estudos/exportar")
        self.assertEqual(status, 200)
        self.assertEqual(json.loads(body)["format"], "radar-estudos")

    def test_importar_endpoint(self):
        _, body = self.request("/api/estudos/exportar")
        payload = json.loads(body)
        status, body = self.request("/api/estudos/importar", "POST",
                                    json.dumps({"payload": payload, "dry_run": True}))
        self.assertEqual(status, 200)
        self.assertTrue(json.loads(body)["dry_run"])
        # Formato inválido -> 400 com erro.
        status, body = self.request("/api/estudos/importar", "POST", json.dumps({"format": "x"}))
        self.assertEqual(status, 400)

    def test_metodos_invalidos(self):
        self.assertEqual(self.request("/api/estudos/conteudo", "PUT")[0], 405)
        self.assertEqual(self.request("/api/estudos/perfil", "PUT")[0], 405)

    def test_ranking_preservado(self):
        # A priorização continua funcionando junto do novo módulo.
        status, _ = self.request("/api/prioridades")
        self.assertEqual(status, 200)


class MatchingTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.db = str(Path(self.tmp.name) / "t.sqlite3")
        migrate_document_schema(self.db)

    def test_conceitos_equivalentes_entre_editais(self):
        # Mesmo tópico em dois editais com redação levemente diferente casa pelo conceito.
        from radar.preparation import conceito_key
        a = conceito_key("Informática", "Redes de computadores")
        b = conceito_key("INFORMATICA", "redes de computadores")
        self.assertEqual(a, b)

    def test_sinonimos_de_escrita_nao_fundem_disciplinas_diferentes(self):
        from radar.preparation import conceito_key
        self.assertNotEqual(conceito_key("Redes", "Segurança"),
                            conceito_key("Legislação", "Segurança"))

    def test_sem_duplicacao_ao_enviar_mesma_lacuna(self):
        obs = ensure_observation(self.db, "https://exemplo.test/c9", "c9")
        with closing(connect_documents(self.db)) as conn:
            contest = conn.execute("SELECT contest_id FROM observacoes_concurso WHERE id=?",
                                   (obs,)).fetchone()[0]
        text = "CONTEÚDO PROGRAMÁTICO\nDIREITO\n1 Administrativo"
        did = register_document(self.db, dict(
            observation_id=obs, kind="outro", official_url="https://exemplo.test/c9/e.pdf",
            title="E", discovery_url="https://exemplo.test/c9", discovery_method="automatico",
            discovered_at=_now()))
        blocks = [{"page_number": 1, "locator": "p", "start_offset": 0,
                   "end_offset": len(text), "text": text}]
        props = program_content.extract_program_content(blocks, contest, label_prefix="x: ")
        version = record_version(self.db, did, b"%PDF " + text.encode(), dict(
            fetched_at=_now(), fetched_url="https://exemplo.test/c9/e.pdf",
            content_type="application/pdf"))
        record_analysis(self.db, version, blocks, props)
        key = knowledge_store.resolve_program(self.db, contest)["topicos"][0]["conceito_key"]
        first = knowledge_store.send_gap_to_study(self.db, contest, key)
        second = knowledge_store.send_gap_to_study(self.db, contest, key)
        self.assertTrue(first["created"])
        self.assertFalse(second["created"])
        self.assertEqual(len(study_store.list_topicos(self.db)), 1)


if __name__ == "__main__":
    unittest.main()
