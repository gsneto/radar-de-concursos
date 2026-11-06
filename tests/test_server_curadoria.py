"""Testes do endpoint POST /api/curadoria/executar."""

import http.client
import json
import threading
import unittest

from radar.server import create_server
from tests.test_autonomous_curator import make_test_db


class ServerCuradoriaTest(unittest.TestCase):
    def setUp(self):
        self.tmp, self.db_path = make_test_db()
        self.server = create_server(self.db_path, host="127.0.0.1", port=0)
        self.port = self.server.server_port
        self.thread = threading.Thread(target=self.server.serve_forever)
        self.thread.daemon = True
        self.thread.start()

    def tearDown(self):
        self.server.shutdown()
        self.server.server_close()
        self.thread.join(timeout=5)
        self.tmp.cleanup()

    def test_post_curadoria_executar(self):
        conn = http.client.HTTPConnection("127.0.0.1", self.port, timeout=5)
        headers = {
            "Content-Type": "application/json",
            "Origin": f"http://127.0.0.1:{self.port}",
        }
        body = json.dumps({"dry_run": True, "limit": 10})
        conn.request("POST", "/api/curadoria/executar", body=body, headers=headers)
        res = conn.getresponse()
        data = json.loads(res.read().decode("utf-8"))
        conn.close()

        self.assertEqual(res.status, 200)
        self.assertEqual(data["status"], "sucesso")
        self.assertTrue(data["dry_run"])
        self.assertIn("novas_revisoes", data)


if __name__ == "__main__":
    unittest.main()
