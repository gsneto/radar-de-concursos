"""Materialização de identidades de cargo a partir do edital (Fase 25)."""

import tempfile
import unittest
from contextlib import closing
from pathlib import Path
from uuid import uuid4

from radar import enrichment
from radar.document_store import connect_documents, migrate_document_schema

NOW = "2026-10-17T12:00:00+00:00"
LABEL = "cargo do documento não reconciliado: "


class EnrichmentBase(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.db = str(Path(self.tmp.name) / "e.sqlite3")
        migrate_document_schema(self.db)
        self._write("INSERT INTO concursos_identidade (id,created_at) VALUES (?,?)",
                    ("c1", NOW))
        self._write("INSERT INTO concursos_identidade (id,created_at) VALUES (?,?)",
                    ("c2", NOW))
        self.observation_id = str(uuid4())
        self._write(
            "INSERT INTO observacoes_concurso (id,contest_id,source_url,competition_id,"
            "observed_at) VALUES (?,?,?,?,?)",
            (self.observation_id, "c1", "https://oficial.test/", "obs-1", NOW))
        self.document_id = str(uuid4())
        self.version_id = str(uuid4())
        self._write(
            "INSERT INTO documentos (id,contest_id,observation_id,kind,official_url,title,"
            "discovered_at,discovery_url,discovery_method) VALUES (?,?,?,?,?,?,?,?,?)",
            (self.document_id, "c1", self.observation_id, "edital", "https://oficial.test/a",
             "Edital", NOW, "https://oficial.test/", "manual"))
        self._write(
            "INSERT INTO versoes_documento (id,document_id,sha256,fetched_at,fetched_url,"
            "content_type,byte_size,local_path,extraction_state) VALUES (?,?,?,?,?,?,?,?,?)",
            (self.version_id, self.document_id, "a" * 64, NOW, "https://oficial.test/a",
             "application/pdf", 10, "x", "parcial"))

    def _write(self, sql, params):
        with closing(connect_documents(self.db)) as conn, conn:
            conn.execute(sql, params)

    def proposal(self, contest_id, reason, *, value="10", version_id=None):
        proposal_id, evidence_id, block_id = str(uuid4()), str(uuid4()), str(uuid4())
        version = version_id or self.version_id
        self._write(
            "INSERT INTO blocos_documento (id,version_id,page_number,locator,start_offset,"
            "end_offset,text) VALUES (?,?,?,?,?,?,?)",
            (block_id, version, 1, "p1", 0, 6, "trecho"))
        self._write(
            "INSERT INTO evidencias (id,version_id,block_id,quote,page_number,locator,"
            "start_offset,end_offset,captured_at) VALUES (?,?,?,?,?,?,?,?,?)",
            (evidence_id, version, block_id, "trecho", 1, "p1", 0, 6, NOW))
        self._write(
            "INSERT INTO propostas_campo (id,contest_id,role_id,field_name,value_json,"
            "value_type,evidence_id,extraction_method,ambiguity_reason,extracted_at) "
            "VALUES (?,?,?,?,?,?,?,?,?,?)",
            (proposal_id, contest_id, None, "immediate_vacancies", value, "integer",
             evidence_id, "tabela", reason, NOW))
        return proposal_id

    def roles(self):
        with closing(connect_documents(self.db)) as conn:
            return conn.execute(
                "SELECT contest_id,name FROM cargos_identidade ORDER BY contest_id,name"
            ).fetchall()


class CleanLabelTest(unittest.TestCase):
    def test_remove_sufixo_de_motivo_com_travessao_em(self):
        self.assertEqual(
            enrichment.clean_label("AGENTE DE APOIO EDUCACIONAL — requisitos presentes"),
            "AGENTE DE APOIO EDUCACIONAL")

    def test_remove_sufixo_de_bloco_com_hifen(self):
        self.assertEqual(enrichment.clean_label("200 Assistente - bloco 3"),
                         "200 Assistente")

    def test_preserva_travessao_en_do_nome_do_cargo(self):
        self.assertEqual(
            enrichment.clean_label("PROFESSOR IV – EDUCAÇÃO FÍSICA"),
            "PROFESSOR IV – EDUCAÇÃO FÍSICA")

    def test_recusa_rotulo_sintetico(self):
        self.assertIsNone(enrichment.clean_label("escolaridade declarada (ensino médio)"))
        self.assertIsNone(enrichment.clean_label("bloco 12"))

    def test_recusa_vazio_e_gigante(self):
        self.assertIsNone(enrichment.clean_label(""))
        self.assertIsNone(enrichment.clean_label("   "))
        self.assertIsNone(enrichment.clean_label("x" * 500))
        self.assertIsNone(enrichment.clean_label(None))

    def test_preserva_nome_com_hifen(self):
        # Nome real de cargo com hífen não pode ser truncado.
        self.assertEqual(enrichment.clean_label("TÉCNICO - ENFERMAGEM"),
                         "TÉCNICO - ENFERMAGEM")
        self.assertEqual(enrichment.clean_label("AGENTE ADMINISTRATIVO - NÍVEL MÉDIO"),
                         "AGENTE ADMINISTRATIVO - NÍVEL MÉDIO")

    def test_recusa_sem_letras(self):
        self.assertIsNone(enrichment.clean_label("12345"))


class CandidatesTest(EnrichmentBase):
    def test_agrupa_por_concurso_e_rotulo(self):
        self.proposal("c1", LABEL + "Cargo A")
        self.proposal("c1", LABEL + "Cargo A")
        self.proposal("c1", LABEL + "Cargo B")
        candidates = enrichment.document_role_candidates(self.db)
        by_label = {c["label"]: c["propostas"] for c in candidates}
        self.assertEqual(by_label, {"Cargo A": 2, "Cargo B": 1})

    def test_ignora_motivo_sem_rotulo(self):
        self.proposal("c1", "edições com múltiplos atos")
        self.assertEqual(enrichment.document_role_candidates(self.db), [])

    def test_marca_identidade_existente(self):
        self.proposal("c1", LABEL + "Cargo A")
        enrichment.materialize_document_roles(self.db, dry_run=False)
        candidates = enrichment.document_role_candidates(self.db)
        self.assertTrue(candidates[0]["identidade_existente"])

    def test_limpa_rotulo_contaminado(self):
        self.proposal("c1", LABEL + "Cargo A — requisitos presentes, mas não determinável")
        labels = [c["label"] for c in enrichment.document_role_candidates(self.db)]
        self.assertEqual(labels, ["Cargo A"])


class MaterializeTest(EnrichmentBase):
    def test_dry_run_nao_grava(self):
        self.proposal("c1", LABEL + "Cargo A")
        report = enrichment.materialize_document_roles(self.db)
        self.assertTrue(report["dry_run"])
        self.assertEqual(report["identidades_criadas"], 0)
        self.assertEqual(report["propostas_elegiveis"], 1)
        self.assertEqual(self.roles(), [])

    def test_cria_identidade_com_nome_do_documento(self):
        self.proposal("c1", LABEL + "Cargo A")
        report = enrichment.materialize_document_roles(self.db, dry_run=False)
        self.assertEqual(report["identidades_criadas"], 1)
        self.assertEqual(self.roles(), [("c1", "Cargo A")])

    def test_idempotente(self):
        self.proposal("c1", LABEL + "Cargo A")
        enrichment.materialize_document_roles(self.db, dry_run=False)
        second = enrichment.materialize_document_roles(self.db, dry_run=False)
        self.assertEqual(second["identidades_criadas"], 0)
        self.assertEqual(len(self.roles()), 1)

    def test_nao_reatribui_propostas(self):
        proposal_id = self.proposal("c1", LABEL + "Cargo A")
        enrichment.materialize_document_roles(self.db, dry_run=False)
        with closing(connect_documents(self.db)) as conn:
            row = conn.execute("SELECT role_id,ambiguity_reason FROM propostas_campo "
                               "WHERE id=?", (proposal_id,)).fetchone()
        self.assertIsNone(row[0], "proposta não pode ser reatribuída automaticamente")
        self.assertEqual(row[1], LABEL + "Cargo A")

    def test_nao_valida_nada(self):
        self.proposal("c1", LABEL + "Cargo A")
        enrichment.materialize_document_roles(self.db, dry_run=False)
        with closing(connect_documents(self.db)) as conn:
            self.assertEqual(conn.execute("SELECT COUNT(*) FROM revisoes_campo").fetchone()[0], 0)

    def test_escopo_por_concurso(self):
        self.proposal("c1", LABEL + "Cargo A")
        self.proposal("c2", LABEL + "Cargo B", version_id=self.version_id)
        report = enrichment.materialize_document_roles(self.db, dry_run=False,
                                                       contest_ids=["c1"])
        self.assertEqual(report["identidades_criadas"], 1)
        self.assertEqual(self.roles(), [("c1", "Cargo A")])

    def test_mesmo_rotulo_em_concursos_distintos_nao_se_funde(self):
        self.proposal("c1", LABEL + "Cargo A")
        self.proposal("c2", LABEL + "Cargo A")
        enrichment.materialize_document_roles(self.db, dry_run=False)
        self.assertEqual(self.roles(), [("c1", "Cargo A"), ("c2", "Cargo A")])


class SummaryTest(EnrichmentBase):
    def test_reconciliacao_com_rotulo_bruto_e_contabilizada(self):
        self.proposal("c1", LABEL + "Cargo A — continua na página seguinte")
        enrichment.materialize_document_roles(self.db, dry_run=False)
        with closing(connect_documents(self.db)) as conn:
            role_id = conn.execute("SELECT id FROM cargos_identidade").fetchone()[0]
        with closing(connect_documents(self.db)) as conn, conn:
            conn.execute(
                "INSERT INTO reconciliacoes_cargo VALUES (?,?,?,?,?,?,?)",
                (str(uuid4()), "c1", LABEL + "Cargo A — continua na página seguinte",
                 role_id, NOW, "revisor", "conferido"))
        summary = enrichment.unresolved_role_summary(self.db)
        self.assertEqual(summary["com_decisao_humana"], 1)
        self.assertEqual(summary["sem_decisao_humana"], 0)

    def test_resumo_antes_e_depois(self):
        self.proposal("c1", LABEL + "Cargo A")
        self.proposal("c1", LABEL + "Cargo B")
        before = enrichment.unresolved_role_summary(self.db)
        self.assertEqual(before["rotulos"], 2)
        self.assertEqual(before["com_identidade"], 0)
        enrichment.materialize_document_roles(self.db, dry_run=False)
        after = enrichment.unresolved_role_summary(self.db)
        self.assertEqual(after["com_identidade"], 2)
        self.assertEqual(after["sem_identidade"], 0)
        self.assertEqual(after["sem_decisao_humana"], 2)


class BackfillTypesTest(EnrichmentBase):
    def test_dry_run_nao_altera_tipo(self):
        self.proposal("c1", LABEL + "Cargo A")
        report = enrichment.backfill_document_types(self.db, dry_run=True)
        self.assertTrue(report["dry_run"])
        with closing(connect_documents(self.db)) as conn:
            self.assertIsNone(conn.execute(
                "SELECT tipo_documental FROM documentos WHERE id=?",
                (self.document_id,)).fetchone()[0])

    def test_classifica_pagina_de_agregador(self):
        with closing(connect_documents(self.db)) as conn, conn:
            conn.execute("UPDATE documentos SET official_url=?, title=? WHERE id=?",
                         ("https://www.pciconcursos.com.br/noticias/x", "Concurso",
                          self.document_id))
        report = enrichment.backfill_document_types(self.db, dry_run=False)
        self.assertEqual(report["classificados"], 1)
        with closing(connect_documents(self.db)) as conn:
            self.assertEqual(conn.execute(
                "SELECT tipo_documental FROM documentos WHERE id=?",
                (self.document_id,)).fetchone()[0], "pagina_agregador")

    def test_nao_sobrescreve_tipo_existente(self):
        with closing(connect_documents(self.db)) as conn, conn:
            conn.execute("UPDATE documentos SET tipo_documental='edital_abertura' WHERE id=?",
                         (self.document_id,))
        report = enrichment.backfill_document_types(self.db, dry_run=False)
        self.assertEqual(report["sem_tipo"], 0)

    def test_nao_altera_kind(self):
        with closing(connect_documents(self.db)) as conn, conn:
            conn.execute("UPDATE documentos SET official_url=? WHERE id=?",
                         ("https://www.pciconcursos.com.br/noticias/x", self.document_id))
        enrichment.backfill_document_types(self.db, dry_run=False)
        with closing(connect_documents(self.db)) as conn:
            self.assertEqual(conn.execute(
                "SELECT kind FROM documentos WHERE id=?", (self.document_id,)).fetchone()[0],
                "edital")


if __name__ == "__main__":
    unittest.main()
