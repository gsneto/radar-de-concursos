import sqlite3
import tempfile
import unittest
from pathlib import Path

from radar.document_store import migrate_document_schema
from radar.my_contests import (
    add_my_contest,
    init_my_contests,
    list_my_contests,
    remove_my_contest,
)


class TestMyContests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.NamedTemporaryFile(suffix=".sqlite3", delete=False)
        self.tmp.close()
        self.db_path = self.tmp.name
        migrate_document_schema(self.db_path)
        conn = sqlite3.connect(self.db_path)
        init_my_contests(conn)

        # Seed a contest and observation
        cur = conn.cursor()
        cur.execute(
            "INSERT INTO concursos_identidade (id, created_at, estado_identidade) VALUES (?, datetime('now'), 'confirmada')",
            ("contest-1",),
        )
        cur.execute(
            "INSERT INTO observacoes_concurso (id, contest_id, source_url, competition_id, observed_at, tipo_identidade) VALUES (?, ?, ?, ?, datetime('now'), 'certame')",
            ("obs-1", "contest-1", "https://fgv.br/concurso1", "fgv-ti-2026"),
        )
        cur.execute(
            """INSERT INTO documentos (id, contest_id, observation_id, kind, official_url, discovery_url, discovery_method, title, published_at, discovered_at)
               VALUES (?, ?, ?, 'edital', ?, ?, 'automatico', ?, '2026-11-01', datetime('now'))""",
            ("doc-1", "contest-1", "obs-1", "https://fgv.br/edital.pdf", "https://fgv.br", "Edital de Abertura"),
        )
        cur.execute(
            "INSERT INTO cargos_identidade (id, contest_id, name, specialty, created_at) VALUES (?, ?, ?, ?, datetime('now'))",
            ("cargo-1", "contest-1", "Analista de TI", "Desenvolvimento de Software"),
        )
        conn.commit()
        conn.close()

    def tearDown(self):
        Path(self.db_path).unlink(missing_ok=True)

    def test_add_and_list_my_contest(self):
        res = add_my_contest(self.db_path, contest_id="contest-1", role_id="cargo-1", notes="Meu concurso foco")
        self.assertTrue(res["ok"])
        self.assertEqual(res["contest_id"], "contest-1")

        my_list = list_my_contests(self.db_path)
        self.assertEqual(len(my_list), 1)
        item = my_list[0]
        self.assertEqual(item["contest_id"], "contest-1")
        self.assertEqual(item["role_name"], "Analista de TI")
        self.assertEqual(item["banca"], "FGV Conhecimento")
        self.assertIsNotNone(item["orgao"])
        self.assertEqual(item["notes"], "Meu concurso foco")
        self.assertEqual(item["status"], "ativo")

    def test_add_idempotency(self):
        res1 = add_my_contest(self.db_path, contest_id="contest-1")
        self.assertTrue(res1["ok"])
        res2 = add_my_contest(self.db_path, contest_id="contest-1", notes="Atualizado")
        self.assertTrue(res2["ok"])

        my_list = list_my_contests(self.db_path)
        self.assertEqual(len(my_list), 1)
        self.assertEqual(my_list[0]["notes"], "Atualizado")

    def test_remove_my_contest(self):
        add_my_contest(self.db_path, contest_id="contest-1")
        self.assertEqual(len(list_my_contests(self.db_path)), 1)

        removed = remove_my_contest(self.db_path, contest_id="contest-1")
        self.assertTrue(removed)
        self.assertEqual(len(list_my_contests(self.db_path)), 0)

        # Removing non-existent
        removed2 = remove_my_contest(self.db_path, contest_id="contest-1")
        self.assertFalse(removed2)


import http.client
import json
import threading
from radar.server import create_server


class TestServerMyContests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.NamedTemporaryFile(suffix=".sqlite3", delete=False)
        self.tmp.close()
        self.db_path = self.tmp.name
        migrate_document_schema(self.db_path)
        conn = sqlite3.connect(self.db_path)
        init_my_contests(conn)
        conn.close()

        self.server = create_server(self.db_path, host="127.0.0.1", port=0)
        self.port = self.server.server_port
        self.thread = threading.Thread(target=self.server.serve_forever)
        self.thread.daemon = True
        self.thread.start()

    def tearDown(self):
        self.server.shutdown()
        self.server.server_close()
        self.thread.join(timeout=5)
        Path(self.db_path).unlink(missing_ok=True)

    def test_http_api_flow(self):
        # 1. GET /api/meus-concursos (initial empty)
        conn = http.client.HTTPConnection("127.0.0.1", self.port, timeout=5)
        conn.request("GET", "/api/meus-concursos")
        res = conn.getresponse()
        self.assertEqual(res.status, 200)
        data = json.loads(res.read().decode())
        self.assertEqual(data["total"], 0)
        self.assertEqual(data["itens"], [])

        # 2. POST /api/meus-concursos
        headers = {
            "Content-Type": "application/json",
            "Origin": f"http://127.0.0.1:{self.port}",
        }
        body = json.dumps({"contest_id": "test-c1", "role_id": "role-1", "notes": "Foco principal"})
        conn.request("POST", "/api/meus-concursos", body=body, headers=headers)
        res = conn.getresponse()
        self.assertEqual(res.status, 201)
        res_data = json.loads(res.read().decode())
        self.assertTrue(res_data["ok"])

        # 3. GET /api/meus-concursos (1 item)
        conn.request("GET", "/api/meus-concursos")
        res = conn.getresponse()
        self.assertEqual(res.status, 200)
        data = json.loads(res.read().decode())
        self.assertEqual(data["total"], 1)
        self.assertEqual(data["itens"][0]["contest_id"], "test-c1")

        # 4. DELETE /api/meus-concursos/test-c1
        del_headers = {
            "Origin": f"http://127.0.0.1:{self.port}",
        }
        conn.request("DELETE", "/api/meus-concursos/test-c1", headers=del_headers)
        res = conn.getresponse()
        self.assertEqual(res.status, 200)
        del_data = json.loads(res.read().decode())
        self.assertTrue(del_data["ok"])
        self.assertTrue(del_data["removed"])

        # 5. GET /api/meus-concursos (empty again)
        conn.request("GET", "/api/meus-concursos")
        res = conn.getresponse()
        self.assertEqual(res.status, 200)
        data = json.loads(res.read().decode())
        self.assertEqual(data["total"], 0)


if __name__ == "__main__":
    unittest.main()
