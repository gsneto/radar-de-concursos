"""Fluxo de retificação: documento distinto, vínculo, conflito e revisão.

A fixture de retificação é SINTÉTICA (ver comentário no arquivo): não é um
documento oficial. O documento original é a fixture derivada do Anexo I real.
"""

import json
import sqlite3
import tempfile
import unittest
from contextlib import closing
from pathlib import Path

from radar.document_extract import extract_blocks
from radar.document_fields import extract_field_proposals
from radar.document_review import review_proposal, select_current_value
from radar.document_store import (
    get_competition_details,
    link_amendment,
    migrate_document_schema,
    record_analysis,
    record_version,
    register_document,
)

ORIGINAL = Path(__file__).parent / "fixtures" / "documents" / "edital-guajara-anexo-i.html"
AMENDMENT = Path(__file__).parent / "fixtures" / "documents" / "retificacao-sintetica.html"


class AmendmentTest(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.db = str(Path(tmp.name) / "db.sqlite3")
        migrate_document_schema(self.db)
        with closing(sqlite3.connect(self.db)) as conn:
            conn.execute("INSERT INTO concursos_identidade VALUES ('c','2026-10-10T00:00:00+00:00')")
            conn.execute("INSERT INTO concursos_identidade VALUES ('other','2026-10-10T00:00:00+00:00')")
            conn.execute("INSERT INTO observacoes_concurso VALUES ('o','c','https://guajaramirim.ro.gov.br/a/','1/2026','2026-10-10T00:00:00+00:00')")
            conn.commit()
        self.original = self._ingest(
            ORIGINAL.read_bytes(), "https://guajaramirim.ro.gov.br/edital.html",
            "edital", "2026-10-10T01:00:00+00:00")
        self.amendment = self._ingest(
            AMENDMENT.read_bytes(), "https://guajaramirim.ro.gov.br/retificacao.html",
            "retificacao", "2026-10-10T02:00:00+00:00")

    def _ingest(self, content, url, kind, at):
        doc = register_document(self.db, dict(observation_id="o", kind=kind,
            official_url=url, title=kind, discovery_url=url, discovery_method="manual",
            discovered_at=at))
        version = record_version(self.db, doc, content, dict(
            fetched_at=at, fetched_url=url, content_type="text/html"))
        blocks = extract_blocks(content, "text/html; charset=utf-8")
        record_analysis(self.db, version, blocks,
                        extract_field_proposals(blocks, version, "c", None))
        return {"doc": doc, "version": version}

    def _proposal(self, detail, field, value):
        return next(p for p in detail["proposals"]
                    if p["field_name"] == field and p["value"] == value)

    def _conflict(self, detail, field, reason_prefix=None):
        for conflict in detail["conflicts"]:
            if conflict["field_name"] != field:
                continue
            if reason_prefix is not None and not (conflict["scope_label"] or "").startswith(reason_prefix):
                continue
            return conflict
        return None

    def test_amendment_is_separate_document_linked_to_original(self):
        link_amendment(self.db, self.amendment["doc"], self.original["doc"], "Ana", "retificação do mesmo certame")
        detail = get_competition_details(self.db, "c")
        docs = {d["id"]: d for d in detail["documents"]}
        self.assertEqual(len(docs), 2)
        self.assertNotEqual(self.original["doc"], self.amendment["doc"])
        self.assertIn(self.original["doc"], docs[self.amendment["doc"]]["related_document_ids"])
        self.assertEqual(docs[self.original["doc"]]["related_document_ids"], [])

    def test_original_version_and_evidence_preserved(self):
        before = get_competition_details(self.db, "c")
        original_evidence = {p["id"]: p["evidence"]["quote"]
                             for p in before["proposals"] if p["evidence"]["version_id"] == self.original["version"]}
        self.assertTrue(original_evidence)
        link_amendment(self.db, self.amendment["doc"], self.original["doc"], "Ana", "vínculo")
        after = get_competition_details(self.db, "c")
        original_evidence_after = {p["id"]: p["evidence"]["quote"]
                                   for p in after["proposals"] if p["evidence"]["version_id"] == self.original["version"]}
        self.assertEqual(original_evidence, original_evidence_after)

    def test_conflict_detected_on_same_scope_and_no_false_conflict(self):
        detail = get_competition_details(self.db, "c")
        infant = "Prof. Magistério Nível II 30 h"
        indigenous = self._conflict(detail, "indigenous_vacancies", reason_prefix=infant)
        self.assertIsNotNone(indigenous)
        self.assertEqual(sorted(v["value"] for v in indigenous["values"]), [2, 3])
        period = self._conflict(detail, "registration_end")
        self.assertIsNotNone(period)
        self.assertEqual(sorted(v["value"] for v in period["values"]),
                         ["2026-07-30", "2026-07-31"])
        # 69 == 69 no mesmo escopo: não há conflito.
        self.assertIsNone(self._conflict(detail, "immediate_vacancies", reason_prefix=infant))
        # Escopos diferentes não geram conflito falso: a cota 0 do cargo Intérprete
        # não se mistura com o total global.
        interpreter = "Prof. Magistério Nível II – Intérprete de Libras"
        self.assertIsNone(self._conflict(detail, "indigenous_vacancies", reason_prefix=interpreter))
        global_conflict = next(c for c in detail["conflicts"]
                               if c["field_name"] == "indigenous_vacancies" and c["scope_type"] == "contest")
        self.assertEqual(sorted(v["value"] for v in global_conflict["values"]), [3, 4])

    def test_no_automatic_promotion_before_review(self):
        detail = get_competition_details(self.db, "c")
        self.assertEqual(detail["current_values"], [])

    def test_selection_after_review_preserves_provenance(self):
        link_amendment(self.db, self.amendment["doc"], self.original["doc"], "Ana", "vínculo")
        detail = get_competition_details(self.db, "c")
        proposal = next(p for p in detail["proposals"]
                        if p["evidence"]["version_id"] == self.amendment["version"]
                        and p["field_name"] == "indigenous_vacancies" and p["value"] == 3)
        review_proposal(self.db, proposal["id"], "validado", "Ana", "retificação confere")
        select_current_value(self.db, proposal["id"], "Ana", "valor retificado vigente")
        detail = get_competition_details(self.db, "c")
        entry = next(v for v in detail["current_values"] if v["proposal_id"] == proposal["id"])
        self.assertTrue(entry["active"])
        self.assertEqual(entry["evidence"]["version_id"], self.amendment["version"])
        self.assertEqual(entry["evidence"]["document_id"], self.amendment["doc"])

    def test_reprocessing_same_amendment_is_idempotent(self):
        again = register_document(self.db, dict(observation_id="o", kind="retificacao",
            official_url="https://guajaramirim.ro.gov.br/retificacao.html", title="retificacao",
            discovery_url="https://guajaramirim.ro.gov.br/retificacao.html",
            discovery_method="manual", discovered_at="2026-10-10T03:00:00+00:00"))
        self.assertEqual(again, self.amendment["doc"])
        same = record_version(self.db, self.amendment["doc"], AMENDMENT.read_bytes(),
            dict(fetched_at="2026-10-10T03:00:00+00:00",
                 fetched_url="https://guajaramirim.ro.gov.br/retificacao.html", content_type="text/html"))
        self.assertEqual(same, self.amendment["version"])
        first_link = link_amendment(self.db, self.amendment["doc"], self.original["doc"], "Ana", "vínculo")
        second_link = link_amendment(self.db, self.amendment["doc"], self.original["doc"], "Ana", "vínculo")
        self.assertEqual(first_link, second_link)
        detail = get_competition_details(self.db, "c")
        self.assertEqual(len(detail["documents"]), 2)

    def test_substantive_change_creates_new_version(self):
        changed = AMENDMENT.read_bytes().replace(b"31 de julho de 2026", b"01 de agosto de 2026")
        new_version = record_version(self.db, self.amendment["doc"], changed,
            dict(fetched_at="2026-10-10T04:00:00+00:00",
                 fetched_url="https://guajaramirim.ro.gov.br/retificacao.html", content_type="text/html"))
        self.assertNotEqual(new_version, self.amendment["version"])
        with closing(sqlite3.connect(self.db)) as conn:
            previous = conn.execute("SELECT previous_version_id FROM versoes_documento WHERE id=?",
                                    (new_version,)).fetchone()[0]
        self.assertEqual(previous, self.amendment["version"])

    def test_rejects_invalid_links(self):
        with self.assertRaisesRegex(ValueError, "si mesmo"):
            link_amendment(self.db, self.amendment["doc"], self.amendment["doc"], "Ana", "erro")
        with self.assertRaisesRegex(ValueError, "retifica"):
            link_amendment(self.db, self.original["doc"], self.amendment["doc"], "Ana", "original como retificação")
        with closing(sqlite3.connect(self.db)) as conn:
            conn.execute("INSERT INTO observacoes_concurso VALUES ('o2','other','https://x.gov.br/a/','2/2026','2026-10-10T00:00:00+00:00')")
            conn.commit()
        foreign = register_document(self.db, dict(observation_id="o2", kind="retificacao",
            official_url="https://guajaramirim.ro.gov.br/outro.html", title="outro",
            discovery_url="https://guajaramirim.ro.gov.br/outro.html",
            discovery_method="manual", discovered_at="2026-10-10T05:00:00+00:00"))
        with self.assertRaisesRegex(ValueError, "concursos diferentes"):
            link_amendment(self.db, foreign, self.original["doc"], "Ana", "concurso errado")
        with self.assertRaisesRegex(ValueError, "inexistente"):
            link_amendment(self.db, self.amendment["doc"], "nao-existe", "Ana", "sem documento")
