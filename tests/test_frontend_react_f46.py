"""Fase 46 — entrega do app React pelo servidor Python (spec §10/§11/§14).

O build ``web-react/dist`` é versionado, então ``python -m radar serve`` deve servir
o app sem Node. Estes testes falham se o build sumir, ficar inconsistente ou se o
servidor deixar de separar app, UI legada e API.
"""

from __future__ import annotations

import http.client
import re
import tempfile
import threading
import unittest
from pathlib import Path

from radar import api_contract
from radar.server import DIST_DIR, create_server

ROOT = Path(__file__).resolve().parent.parent


class DistBuildTest(unittest.TestCase):
    def test_index_existe_e_referencia_assets_existentes(self):
        index = DIST_DIR / "index.html"
        self.assertTrue(index.is_file(), "rode `npm run build` em web-react/")
        html = index.read_text(encoding="utf-8")
        self.assertIn('<div id="root">', html)
        assets = re.findall(r'(?:src|href)="/(assets/[^"]+)"', html)
        self.assertTrue(any(a.endswith(".js") for a in assets), assets)
        self.assertTrue(any(a.endswith(".css") for a in assets), assets)
        for asset in assets:
            self.assertTrue((DIST_DIR / asset).is_file(), f"asset ausente: {asset}")

    def test_build_versionado_no_git(self):
        # Sem isso, um clone novo não teria o app (spec §12).
        ignore = (ROOT / ".gitignore").read_text(encoding="utf-8")
        self.assertIn("!web-react/dist/", ignore)


class ReactServingTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls._tmp = tempfile.TemporaryDirectory()
        cls.server = create_server(str(Path(cls._tmp.name) / "radar.sqlite3"), port=0)
        cls.port = cls.server.server_address[1]
        cls._thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls._thread.start()

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()
        cls._tmp.cleanup()

    def get(self, path):
        conn = http.client.HTTPConnection("127.0.0.1", self.port, timeout=10)
        try:
            conn.request("GET", path)
            response = conn.getresponse()
            return response.status, dict(response.getheaders()), response.read()
        finally:
            conn.close()

    def test_raiz_serve_o_app_sem_cache(self):
        status, headers, body = self.get("/")
        self.assertEqual(status, 200)
        self.assertIn(b'<div id="root">', body)
        self.assertEqual(headers.get("Cache-Control"), "no-cache")

    def test_assets_com_hash_tem_cache_longo(self):
        html = (DIST_DIR / "index.html").read_text(encoding="utf-8")
        js = re.search(r'src="(/assets/[^"]+\.js)"', html).group(1)
        status, headers, body = self.get(js)
        self.assertEqual(status, 200)
        self.assertIn("javascript", headers.get("Content-Type", ""))
        self.assertIn("immutable", headers.get("Cache-Control", ""))
        self.assertGreater(len(body), 0)

    def test_rotas_do_app_caem_no_fallback_spa(self):
        for path in ("/oportunidades", "/estudos/simulados", "/dossie/abc"):
            status, _, body = self.get(path)
            self.assertEqual(status, 200, path)
            self.assertIn(b'<div id="root">', body, path)

    def test_legacy_serve_a_ui_vanilla(self):
        status, _, body = self.get("/legacy/")
        self.assertEqual(status, 200)
        self.assertNotIn(b'<div id="root">', body)
        self.assertIn(b'id="view-root"', body)

    def test_api_desconhecida_nao_vira_app(self):
        status, _, body = self.get("/api/rota-que-nao-existe")
        self.assertEqual(status, 404)
        self.assertNotIn(b'<div id="root">', body)

    def test_traversal_bloqueado(self):
        for path in ("/assets/../../radar/server.py", "/legacy/../radar/server.py"):
            status, _, body = self.get(path)
            self.assertNotEqual(status, 200, path)
            self.assertNotIn(b"import", body, path)

    def test_contrato_da_api_continua_verde(self):
        result = api_contract.verify(str(ROOT / "radar" / "server.py"))
        self.assertTrue(result["ok"], result)


if __name__ == "__main__":
    unittest.main()
