"""Testes para o diretório completo de Organizadoras (~350 bancas), Acervo de Provas Anteriores e Extrator."""

from __future__ import annotations

import http.client
import json
import tempfile
import threading
import unittest
from pathlib import Path

from radar import api_contract
from radar.document_store import migrate_document_schema
from radar.server import create_server

ROOT = Path(__file__).resolve().parent.parent


class OrganizersAndExamPapersTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.db = str(Path(self.tmp.name) / "radar.sqlite3")
        migrate_document_schema(self.db)

    def test_organizers_catalog_contains_pci_list_and_reconciles_aliases(self):
        from radar import organizers_catalog

        res = organizers_catalog.list_organizers(self.db)
        self.assertGreaterEqual(res["total"], 340)
        slugs = {item["slug"] for item in res["itens"]}
        self.assertIn("a-s-instituto", slugs)
        self.assertIn("cebraspe", slugs)
        self.assertIn("fgv", slugs)
        self.assertIn("fcc", slugs)
        self.assertIn("vunesp", slugs)
        self.assertIn("ifbaiano", slugs)
        self.assertIn("ufba", slugs)
        self.assertIn("univasf", slugs)
        self.assertIn("zambini", slugs)

        # Reconciliação de aliases e variações
        self.assertEqual(organizers_catalog.resolve_organizer_slug("CESPE / UnB"), "cebraspe")
        self.assertEqual(organizers_catalog.resolve_organizer_slug("FGV Conhecimento"), "fgv")
        self.assertEqual(organizers_catalog.resolve_organizer_slug("Fundação Carlos Chagas (FCC)"), "fcc")

        fgv = next(item for item in res["itens"] if item["slug"] == "fgv")
        self.assertTrue(fgv["tem_raio_x_ti"])
        self.assertEqual(fgv["raio_x_id"], "fgv")

    def test_exam_papers_seed_ti_depth_and_surface_careers_plus_extractor(self):
        from radar import exam_papers, practice_store

        seeded = exam_papers.list_exam_papers(self.db)
        self.assertGreaterEqual(seeded["total"], 18)
        self.assertGreaterEqual(seeded["por_carreira"].get("ti", 0), 10)
        # Superfície pronta para expansão nas demais áreas
        for area in ("administrativa", "fiscal", "tribunais", "policial", "educacao"):
            self.assertGreaterEqual(seeded["por_carreira"].get(area, 0), 1, area)

        ti_only = exam_papers.list_exam_papers(self.db, carreira="ti")
        self.assertTrue(all(p["carreira"] == "ti" for p in ti_only["itens"]))
        self.assertTrue(any(p["questoes_count"] > 0 for p in ti_only["itens"]))

        # Extrator automático de prova oficial + gabarito
        sample_exam_text = """
        1. Em bancos de dados relacionais, qual comando DDL remove completamente a estrutura de uma tabela e seus índices do catálogo?
        A) DELETE FROM tabela
        B) TRUNCATE TABLE tabela
        C) DROP TABLE tabela
        D) ALTER TABLE tabela
        E) REVOKE ALL ON tabela

        2. No protocolo TCP/IP, qual porta padrão é associada nativamente ao tráfego HTTPS sobre TLS?
        A) 22
        B) 53
        C) 80
        D) 443
        E) 3306
        """
        sample_gabarito = "1 - C\n2: D"

        created = exam_papers.import_exam_paper(
            self.db,
            {
                "titulo": "Analista Judiciário - Apoio Especializado (TI)",
                "cargo": "Analista Judiciário - TI",
                "orgao": "TRT 5ª Região (BA)",
                "banca": "FCC",
                "ano": 2024,
                "nivel": "superior",
                "carreira": "ti",
                "disciplina_padrao": "Banco de Dados",
                "edital_ou_prova_url": "https://www.concursosfcc.com.br/concursos/trt5/prova_ti.pdf",
                "texto_prova": sample_exam_text,
                "texto_gabarito": sample_gabarito,
            },
        )
        self.assertEqual(created["questoes_extraidas"], 2)
        paper_tag = f"prova:{created['prova']['id']}"
        all_qs = practice_store.list_questions(self.db)
        extracted = [q for q in all_qs if paper_tag in (q.get("tags") or [])]
        self.assertEqual(len(extracted), 2)

    def test_http_endpoints_and_api_contract(self):
        server = create_server(self.db, port=0)
        port = server.server_address[1]
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        self.addCleanup(lambda: (server.shutdown(), server.server_close()))

        conn = http.client.HTTPConnection("127.0.0.1", port, timeout=10)
        self.addCleanup(conn.close)

        conn.request("GET", "/api/organizadoras?letra=F")
        resp = conn.getresponse()
        body = json.loads(resp.read().decode("utf-8"))
        self.assertEqual(resp.status, 200)
        self.assertTrue(all(it["nome"].upper().startswith("F") for it in body["itens"]))

        conn.request("GET", "/api/estudos/provas?carreira=ti")
        resp2 = conn.getresponse()
        body2 = json.loads(resp2.read().decode("utf-8"))
        self.assertEqual(resp2.status, 200)
        self.assertGreaterEqual(len(body2["itens"]), 10)

        contract = api_contract.verify(str(ROOT / "radar" / "server.py"))
        self.assertTrue(contract["ok"], contract)


if __name__ == "__main__":
    unittest.main()
