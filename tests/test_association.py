"""Diagnóstico de associações documento–concurso e classificação por fonte (Fase 26)."""

import tempfile
import unittest
from contextlib import closing
from pathlib import Path
from uuid import uuid4

from radar import association, document_types
from radar.document_store import connect_documents, migrate_document_schema

NOW = "2026-10-17T12:00:00+00:00"


class TypesTest(unittest.TestCase):
    def test_agregador_nunca_e_edital_mesmo_com_titulo_de_retificacao(self):
        self.assertEqual(
            document_types.classify_document(
                "1ª Retificação", "https://www.pciconcursos.com.br/noticias/x"),
            "pagina_agregador")

    def test_banca_pagina(self):
        self.assertEqual(
            document_types.classify_document(
                "Concurso TJ AP", "https://conhecimento.fgv.br/concursos"),
            "pagina_banca")

    def test_orgao_publico(self):
        self.assertEqual(
            document_types.classify_document(
                "Concursos abertos", "https://www.gov.br/receitafederal/concursos"),
            "pagina_orgao")

    def test_titulo_de_ato_manda_em_fonte_oficial(self):
        self.assertEqual(
            document_types.classify_document(
                "EDITAL Nº 8, DE 14 DE OUTUBRO DE 2026",
                "https://www.in.gov.br/web/dou/-/edital"),
            "edital_abertura")

    def test_desconhecido_continua_outro(self):
        self.assertEqual(document_types.classify_document("x", "https://exemplo.com/a"),
                         "outro")

    def test_kind_nao_promove_pagina(self):
        for tipo in document_types.PAGE_TYPES:
            self.assertEqual(document_types.kind_for(tipo), "outro")

    def test_host_of(self):
        self.assertEqual(document_types.host_of("https://WWW.PCIconcursos.com.br/x"),
                         "www.pciconcursos.com.br")
        self.assertEqual(document_types.host_of(None), "")


class AssociationBase(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.db = str(Path(self.tmp.name) / "a.sqlite3")
        migrate_document_schema(self.db)

    def contest(self, cid, competition_id):
        obs = str(uuid4())
        with closing(connect_documents(self.db)) as conn, conn:
            conn.execute("INSERT INTO concursos_identidade (id,created_at) VALUES (?,?)",
                         (cid, NOW))
            conn.execute(
                "INSERT INTO observacoes_concurso (id,contest_id,source_url,competition_id,"
                "observed_at) VALUES (?,?,?,?,?)",
                (obs, cid, "https://fonte.test/", competition_id, NOW))
        return obs

    def document(self, contest_id, obs, *, kind="edital", tipo=None, title="Edital",
                 url=None):
        doc = str(uuid4())
        with closing(connect_documents(self.db)) as conn, conn:
            conn.execute(
                "INSERT INTO documentos (id,contest_id,observation_id,kind,official_url,title,"
                "discovered_at,discovery_url,discovery_method,tipo_documental) "
                "VALUES (?,?,?,?,?,?,?,?,?,?)",
                (doc, contest_id, obs, kind, url or f"https://oficial.test/{doc}",
                 title, NOW, "https://oficial.test/", "manual", tipo))
        return doc


class AssociationTest(AssociationBase):
    def test_identidade_de_secao_do_dou_e_suspeita(self):
        obs = self.contest("c1", "DOU-S3")
        for index in range(3):
            self.document("c1", obs, title=f"EDITAL DE {index} DE OUTUBRO DE 2026")
        report = association.suspect_associations(self.db)
        reasons = {item["reason"] for item in report["itens"]}
        self.assertIn("identidade_de_secao", reasons)
        self.assertIn("muitos_atos_sem_propostas", reasons)
        self.assertEqual(report["concursos_afetados"], 1)

    def test_concurso_normal_nao_e_acusado(self):
        obs = self.contest("c1", "quadrix-3056")
        self.document("c1", obs, title="Edital nº 1 (abertura)")
        self.assertEqual(association.suspect_associations(self.db)["itens"], [])

    def test_titulos_divergentes(self):
        obs = self.contest("c1", "quadrix-1")
        self.document("c1", obs, title="Edital nº 1 (abertura)", tipo="edital_abertura")
        self.document("c1", obs, title="Edital nº 7 (abertura)", tipo="edital_abertura")
        reasons = {i["reason"] for i in association.suspect_associations(self.db)["itens"]}
        self.assertIn("titulos_divergentes", reasons)

    def test_documento_compartilhado_entre_concursos(self):
        first = self.contest("c1", "banca-1")
        second = self.contest("c2", "banca-2")
        url = "https://oficial.test/mesmo.pdf"
        self.document("c1", first, url=url)
        self.document("c2", second, url=url)
        reasons = {i["reason"] for i in association.suspect_associations(self.db)["itens"]}
        self.assertIn("documento_compartilhado", reasons)

    def test_relatorio_nao_altera_nada(self):
        obs = self.contest("c1", "DOU-S3")
        self.document("c1", obs, title="EDITAL A")
        with closing(connect_documents(self.db)) as conn:
            before = (conn.execute("SELECT COUNT(*) FROM documentos").fetchone()[0],
                      conn.execute("SELECT COUNT(*) FROM propostas_campo").fetchone()[0],
                      conn.execute("SELECT COUNT(*) FROM evidencias").fetchone()[0])
        association.suspect_associations(self.db)
        with closing(connect_documents(self.db)) as conn:
            after = (conn.execute("SELECT COUNT(*) FROM documentos").fetchone()[0],
                     conn.execute("SELECT COUNT(*) FROM propostas_campo").fetchone()[0],
                     conn.execute("SELECT COUNT(*) FROM evidencias").fetchone()[0])
        self.assertEqual(before, after)

    def test_schema_ilegivel_falha_alto(self):
        with self.assertRaises(ValueError):
            association.suspect_associations(str(Path(self.tmp.name) / "nao.sqlite3"))


if __name__ == "__main__":
    unittest.main()
