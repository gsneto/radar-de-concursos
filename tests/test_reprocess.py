"""Reprocessamento idempotente de editais já analisados (Fase 26)."""

import tempfile
import unittest
from contextlib import closing
from pathlib import Path
from uuid import uuid4

from radar import reprocess
from radar.document_store import connect_documents, migrate_document_schema

NOW = "2026-10-17T12:00:00+00:00"

# Página de PDF como o extrator realmente produz: um único parágrafo, sem quebras de linha.
PDF_PAGE = (
    "MUNICÍPIO DE TESTE | CONCURSO PÚBLICO 2026 1 EDITAL Nº 01/2026 "
    "1. DAS DISPOSIÇÕES 1.1 As provas serão realizadas na cidade de Palmas, no Estado do "
    "Tocantins (TO). ANEXO I – CONTEÚDO PROGRAMÁTICO CARGO: ANALISTA "
    "BLOCO I CONHECIMENTOS GERAIS 1. Língua Portuguesa. Interpretação de texto. "
    "2. Matemática. Raciocínio lógico. 3. Noções de Informática. Planilhas eletrônicas.")


class ReprocessBase(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.db = str(Path(self.tmp.name) / "r.sqlite3")
        migrate_document_schema(self.db)
        self._write("INSERT INTO concursos_identidade (id,created_at) VALUES (?,?)",
                    ("c1", NOW))
        self.observation_id = str(uuid4())
        self._write(
            "INSERT INTO observacoes_concurso (id,contest_id,source_url,competition_id,"
            "observed_at) VALUES (?,?,?,?,?)",
            (self.observation_id, "c1", "https://oficial.test/", "obs-1", NOW))
        self.document_id, self.version_id = str(uuid4()), str(uuid4())
        self._write(
            "INSERT INTO documentos (id,contest_id,observation_id,kind,official_url,title,"
            "discovered_at,discovery_url,discovery_method,tipo_documental) "
            "VALUES (?,?,?,?,?,?,?,?,?,?)",
            (self.document_id, "c1", self.observation_id, "edital",
             "https://oficial.test/edital.pdf", "Edital nº 1 (abertura)", NOW,
             "https://oficial.test/", "manual", "edital_abertura"))
        self._write(
            "INSERT INTO versoes_documento (id,document_id,sha256,fetched_at,fetched_url,"
            "content_type,byte_size,local_path,extraction_state) VALUES (?,?,?,?,?,?,?,?,?)",
            (self.version_id, self.document_id, "a" * 64, NOW,
             "https://oficial.test/edital.pdf", "application/pdf", len(PDF_PAGE), "x",
             "parcial"))
        # Bloco já analisado, exatamente como o extrator grava (uma página por bloco).
        self._write(
            "INSERT INTO blocos_documento (id,version_id,page_number,locator,start_offset,"
            "end_offset,text) VALUES (?,?,?,?,?,?,?)",
            (str(uuid4()), self.version_id, 1, "página 1", 0, len(PDF_PAGE), PDF_PAGE))

    def _write(self, sql, params):
        with closing(connect_documents(self.db)) as conn, conn:
            conn.execute(sql, params)

    def counts(self):
        with closing(connect_documents(self.db)) as conn:
            return (conn.execute("SELECT COUNT(*) FROM propostas_campo").fetchone()[0],
                    conn.execute("SELECT COUNT(*) FROM evidencias").fetchone()[0],
                    conn.execute("SELECT COUNT(*) FROM blocos_documento").fetchone()[0])


class ProposeTest(ReprocessBase):
    def test_gera_propostas_de_conteudo_e_local(self):
        with closing(connect_documents(self.db)) as conn:
            proposals = reprocess.propose_for_version(conn, self.version_id)
        fields = {p["field_name"] for p in proposals}
        self.assertIn("exam_location", fields)
        self.assertIn("conteudo_topico", fields)
        self.assertIn("conteudo_secao", fields)

    def test_citacao_e_literal_no_bloco(self):
        with closing(connect_documents(self.db)) as conn:
            for proposal in reprocess.propose_for_version(conn, self.version_id):
                evidence = proposal["evidence"]
                self.assertEqual(
                    PDF_PAGE[evidence["start_offset"]:evidence["end_offset"]],
                    evidence["quote"])

    def test_versao_inexistente_falha(self):
        with closing(connect_documents(self.db)) as conn:
            with self.assertRaises(ValueError):
                reprocess.propose_for_version(conn, "nao-existe")


class IdempotencyTest(ReprocessBase):
    def test_dry_run_nao_grava(self):
        before = self.counts()
        report = reprocess.reprocess_version(self.db, self.version_id, dry_run=True)
        self.assertGreater(report["novas"], 0)
        self.assertEqual(self.counts(), before)

    def test_grava_e_reprocessar_nao_duplica(self):
        first = reprocess.reprocess_version(self.db, self.version_id, dry_run=False)
        self.assertGreater(first["gravadas"], 0)
        after_first = self.counts()
        second = reprocess.reprocess_version(self.db, self.version_id, dry_run=False)
        self.assertEqual(second["novas"], 0)
        self.assertEqual(second["ignoradas"], first["geradas"])
        self.assertEqual(self.counts(), after_first)

    def test_nao_reescreve_blocos(self):
        before = self.counts()[2]
        reprocess.reprocess_version(self.db, self.version_id, dry_run=False)
        self.assertEqual(self.counts()[2], before)

    def test_propostas_novas_sao_ambiguas(self):
        reprocess.reprocess_version(self.db, self.version_id, dry_run=False)
        with closing(connect_documents(self.db)) as conn:
            rows = conn.execute("SELECT ambiguity_reason FROM propostas_campo").fetchall()
        self.assertTrue(rows)
        for (reason,) in rows:
            self.assertTrue(reason, "nenhuma proposta pode nascer confirmada")


class BatchTest(ReprocessBase):
    def test_lote_so_considera_edital(self):
        # Documento de resultado não deve ser reprocessado como edital.
        other = str(uuid4())
        self._write(
            "INSERT INTO documentos (id,contest_id,observation_id,kind,official_url,title,"
            "discovered_at,discovery_url,discovery_method,tipo_documental) "
            "VALUES (?,?,?,?,?,?,?,?,?,?)",
            (other, "c1", self.observation_id, "outro", "https://oficial.test/resultado",
             "Resultado final", NOW, "https://oficial.test/", "manual", "resultado"))
        report = reprocess.reprocess_editais(self.db, dry_run=True)
        self.assertEqual(report["concursos"], 1)

    def test_lote_respeita_escopo_por_concurso(self):
        self._write("INSERT INTO concursos_identidade (id,created_at) VALUES (?,?)",
                    ("c2", NOW))
        report = reprocess.reprocess_editais(self.db, dry_run=True, contest_ids=["c2"])
        self.assertEqual(report["concursos"], 0)


class SafetyTest(ReprocessBase):
    def test_propostas_e_evidencias_existentes_nao_mudam(self):
        reprocess.reprocess_version(self.db, self.version_id, dry_run=False)
        with closing(connect_documents(self.db)) as conn:
            before = conn.execute(
                "SELECT id,field_name,value_json,evidence_id FROM propostas_campo "
                "ORDER BY id").fetchall()
            before_ev = conn.execute(
                "SELECT id,quote,start_offset,end_offset FROM evidencias ORDER BY id").fetchall()
        reprocess.reprocess_version(self.db, self.version_id, dry_run=False)
        with closing(connect_documents(self.db)) as conn:
            after = conn.execute(
                "SELECT id,field_name,value_json,evidence_id FROM propostas_campo "
                "ORDER BY id").fetchall()
            after_ev = conn.execute(
                "SELECT id,quote,start_offset,end_offset FROM evidencias ORDER BY id").fetchall()
        self.assertEqual(before, after)
        self.assertEqual(before_ev, after_ev)

    def test_locator_da_evidencia_e_o_do_bloco(self):
        reprocess.reprocess_version(self.db, self.version_id, dry_run=False)
        with closing(connect_documents(self.db)) as conn:
            rows = conn.execute("SELECT DISTINCT locator FROM evidencias").fetchall()
        self.assertIn(("página 1",), rows)


if __name__ == "__main__":
    unittest.main()
