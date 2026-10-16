"""Reconciliação humana de rótulos de cargo do documento com identidades canônicas."""

import sqlite3
import tempfile
import unittest
from contextlib import closing
from pathlib import Path

from radar.document_extract import extract_blocks
from radar.document_fields import LABEL_PREFIX, extract_field_proposals
from radar.document_review import reconcile_role_label, review_proposal, select_current_value
from radar.document_store import (
    get_competition_details,
    migrate_document_schema,
    record_analysis,
    record_version,
    register_document,
)

FIXTURE = Path(__file__).parent / "fixtures" / "documents" / "edital-guajara-anexo-i.html"


class ReconcileRoleTest(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.db = str(Path(tmp.name) / "db.sqlite3")
        migrate_document_schema(self.db)
        with closing(sqlite3.connect(self.db)) as conn:
            conn.execute("INSERT INTO concursos_identidade VALUES ('c','2026-10-10T00:00:00+00:00')")
            conn.execute("INSERT INTO concursos_identidade VALUES ('other','2026-10-10T00:00:00+00:00')")
            conn.execute("INSERT INTO observacoes_concurso VALUES ('o','c','https://guajaramirim.ro.gov.br/a/','1/2026','2026-10-10T00:00:00+00:00')")
            conn.execute("INSERT INTO cargos_identidade (id,contest_id,name,specialty,created_at) VALUES ('r1','c','Professor de Educação Infantil',NULL,'2026-10-10T00:00:00+00:00')")
            conn.execute("INSERT INTO cargos_identidade (id,contest_id,name,specialty,created_at) VALUES ('r2','c','Professor Anos Iniciais',NULL,'2026-10-10T00:00:00+00:00')")
            conn.execute("INSERT INTO cargos_identidade (id,contest_id,name,specialty,created_at) VALUES ('foreign','other','Outro',NULL,'2026-10-10T00:00:00+00:00')")
            conn.commit()
        url = "https://guajaramirim.ro.gov.br/edital.html"
        self.doc = register_document(self.db, dict(observation_id="o", kind="edital",
            official_url=url, title="Edital", discovery_url=url, discovery_method="manual",
            discovered_at="2026-10-10T00:00:00+00:00"))
        content = FIXTURE.read_bytes()
        self.version = record_version(self.db, self.doc, content, dict(
            fetched_at="2026-10-10T01:00:00+00:00", fetched_url=url, content_type="text/html"))
        blocks = extract_blocks(content, "text/html; charset=utf-8")
        record_analysis(self.db, self.version, blocks,
                        extract_field_proposals(blocks, self.version, "c", None))
        self.detail = get_competition_details(self.db, "c")
        self.cargo = next(p for p in self.detail["proposals"]
                          if p["field_name"] == "immediate_vacancies" and p["value"] == 69)
        self.label = self.cargo["ambiguity_reason"][len(LABEL_PREFIX):]

    def test_reconcile_links_label_to_role_and_preserves_evidence(self):
        reconcile_role_label(self.db, "c", self.label, "r1", "Ana", "cargo conferido no Anexo I")
        detail = get_competition_details(self.db, "c")
        proposal = next(p for p in detail["proposals"] if p["id"] == self.cargo["id"])
        self.assertEqual(proposal["reconciled_role_id"], "r1")
        self.assertEqual(proposal["role_id"], None)
        self.assertEqual(proposal["evidence"]["quote"], self.cargo["evidence"]["quote"])
        self.assertEqual(proposal["evidence"]["version_id"], self.cargo["evidence"]["version_id"])
        self.assertEqual(detail["role_reconciliations"][0]["role_id"], "r1")

    def test_reconcile_rejects_label_without_evidence(self):
        with self.assertRaisesRegex(ValueError, "sem evid"):
            reconcile_role_label(self.db, "c", "Cargo Inexistente", "r1", "Ana", "tentativa")

    def test_reconcile_rejects_conflicting_mapping(self):
        reconcile_role_label(self.db, "c", self.label, "r1", "Ana", "primeira decisão")
        with self.assertRaisesRegex(ValueError, "outro cargo"):
            reconcile_role_label(self.db, "c", self.label, "r2", "Beto", "mudança de ideia")
        detail = get_competition_details(self.db, "c")
        proposal = next(p for p in detail["proposals"] if p["id"] == self.cargo["id"])
        self.assertEqual(proposal["reconciled_role_id"], "r1")
        self.assertEqual(len(detail["role_reconciliations"]), 1)

    def test_reconcile_is_idempotent_for_same_role(self):
        first = reconcile_role_label(self.db, "c", self.label, "r1", "Ana", "decisão")
        second = reconcile_role_label(self.db, "c", self.label, "r1", "Ana", "repetição")
        self.assertEqual(first, second)
        with closing(sqlite3.connect(self.db)) as conn:
            self.assertEqual(conn.execute("SELECT count(*) FROM reconciliacoes_cargo").fetchone()[0], 1)

    def test_reconcile_rejects_role_from_other_contest(self):
        with self.assertRaisesRegex(ValueError, "outro concurso"):
            reconcile_role_label(self.db, "c", self.label, "foreign", "Ana", "cargo de outro")

    def test_selection_uses_reconciled_role(self):
        reconcile_role_label(self.db, "c", self.label, "r1", "Ana", "cargo conferido no Anexo I")
        review_proposal(self.db, self.cargo["id"], "validado", "Ana", "conferido")
        select_current_value(self.db, self.cargo["id"], "Ana", "escolha fundamentada")
        values = get_competition_details(self.db, "c")["current_values"]
        entry = next(v for v in values if v["proposal_id"] == self.cargo["id"])
        self.assertEqual(entry["role_id"], "r1")
        self.assertTrue(entry["active"])

    def test_global_total_is_not_duplicated_nor_reconciled(self):
        totals = [p for p in self.detail["proposals"]
                  if p["field_name"] == "immediate_vacancies" and p["value"] == 107]
        self.assertEqual(len(totals), 1)
        self.assertIsNone(totals[0]["role_id"])
        self.assertIsNone(totals[0]["ambiguity_reason"])
        self.assertIsNone(totals[0]["reconciled_role_id"])


class EnsureRoleReconcileTest(unittest.TestCase):
    """Fluxo completo de atribuição: criar cargo do documento e reconciliar o rótulo."""

    def test_role_created_from_document_label_can_be_reconciled_and_selected(self):
        from radar.document_store import ensure_observation, ensure_role
        with tempfile.TemporaryDirectory() as temp:
            db = str(Path(temp) / "db.sqlite3")
            migrate_document_schema(db)
            obs = ensure_observation(db, "https://guajaramirim.ro.gov.br/a/", "X/2026")
            with closing(sqlite3.connect(db)) as conn:
                contest = conn.execute("SELECT contest_id FROM observacoes_concurso WHERE id=?",
                                       (obs,)).fetchone()[0]
            annex = (Path(__file__).parent / "fixtures" / "documents"
                     / "edital-guajara-anexo-i.html").read_bytes()
            url = "https://guajaramirim.ro.gov.br/edital.html"
            doc = register_document(db, dict(observation_id=obs, kind="edital", official_url=url,
                title="Edital", discovery_url=url, discovery_method="manual",
                discovered_at="2026-10-10T00:00:00+00:00"))
            version = record_version(db, doc, annex, dict(fetched_at="2026-10-10T01:00:00+00:00",
                fetched_url=url, content_type="text/html"))
            blocks = extract_blocks(annex, "text/html; charset=utf-8")
            record_analysis(db, version, blocks,
                            extract_field_proposals(blocks, version, contest, None))
            proposal = next(p for p in get_competition_details(db, contest)["proposals"]
                            if p["field_name"] == "immediate_vacancies" and p["value"] == 69)
            label = proposal["ambiguity_reason"][len(LABEL_PREFIX):]
            role_id = ensure_role(db, contest, obs, label)
            reconcile_role_label(db, contest, label, role_id, "Ana", "cargo do próprio documento")
            review_proposal(db, proposal["id"], "validado", "Ana", "conferido no quadro")
            select_current_value(db, proposal["id"], "Ana", "escolha humana")
            values = get_competition_details(db, contest)["current_values"]
            entry = next(v for v in values if v["proposal_id"] == proposal["id"])
            self.assertEqual(entry["role_id"], role_id)
            self.assertTrue(entry["active"])
