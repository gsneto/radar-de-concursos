import json
import tempfile
import unittest
import urllib.request
from pathlib import Path
from threading import Thread

from radar.document_store import migrate_document_schema
from radar.server import create_server


class TestServerLessons(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.NamedTemporaryFile(suffix=".sqlite3", delete=False)
        self.tmp.close()
        self.db_path = self.tmp.name
        migrate_document_schema(self.db_path)
        from radar.real_exam_questions import seed_real_questions
        seed_real_questions(self.db_path)
        self.server = create_server(self.db_path, host="127.0.0.1", port=0)
        self.port = self.server.server_port
        self.thread = Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()

    def tearDown(self):
        self.server.shutdown()
        self.server.server_close()
        Path(self.db_path).unlink(missing_ok=True)

    def _get(self, path):
        req = urllib.request.Request(f"http://127.0.0.1:{self.port}{path}")
        with urllib.request.urlopen(req) as resp:
            return resp.status, json.loads(resp.read().decode("utf-8"))

    def test_get_lessons(self):
        status, data = self._get("/api/estudos/aulas")
        self.assertEqual(status, 200)
        self.assertIn("aulas", data)
        self.assertTrue(len(data["aulas"]) >= 6)

        # Filter by disciplina
        status, data_bd = self._get("/api/estudos/aulas?disciplina=Banco%20de%20Dados")
        self.assertEqual(status, 200)
        self.assertTrue(all(a["disciplina"] == "Banco de Dados" for a in data_bd["aulas"]))

    def test_get_lesson_detail(self):
        status, data = self._get("/api/estudos/aulas/bd-01")
        self.assertEqual(status, 200)
        self.assertIn("aula", data)
        self.assertEqual(data["aula"]["id"], "bd-01")
        self.assertIn("radiografia_bancas", data["aula"])
        self.assertIn("pontos_criticos", data["aula"])

    def test_get_bancas(self):
        status, data = self._get("/api/estudos/bancas")
        self.assertEqual(status, 200)
        self.assertIn("bancas", data)
        self.assertTrue(len(data["bancas"]) >= 4)
        bancas_dict = data["bancas"]
        self.assertIn("fgv", bancas_dict)
        self.assertIn("cebraspe", bancas_dict)
        self.assertIn("quadrix", bancas_dict)
        self.assertIn("ibfc", bancas_dict)
        self.assertIn("nome", bancas_dict["fgv"])


if __name__ == "__main__":
    unittest.main()
