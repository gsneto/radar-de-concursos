"""Reconciliação de cargos por código oficial (HTML ↔ PDF)."""

import tempfile
import unittest
from contextlib import closing
from pathlib import Path

from radar import quadrix_source as qx
from radar.document_fields import LABEL_PREFIX
from radar.document_store import (connect_documents, ensure_observation, ensure_role,
                                  migrate_document_schema)
from radar.role_reconciliation import reconcile_proposals_by_code


def _proposal(label, field="immediate_vacancies", value='"1"'):
    return {"contest_id": "c", "role_id": None, "field_name": field, "value_json": value,
            "value_type": "integer", "extraction_method": "t", "ambiguity_reason": LABEL_PREFIX + label,
            "evidence": {}}


class ReconcileTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.db = str(Path(self.tmp.name) / "db.sqlite3")
        migrate_document_schema(self.db)
        self.obs = ensure_observation(self.db, "https://www.quadrix.org.br/informacoes/1/", "quadrix-1")
        with closing(connect_documents(self.db)) as conn:
            self.contest = conn.execute("SELECT contest_id FROM observacoes_concurso WHERE id=?",
                                        (self.obs,)).fetchone()[0]

    def _table(self, *rows):
        return [{"code": c, "name": n, "education": e} for c, n, e in rows]

    def test_associates_by_code(self):
        table = self._table(("404", "Analista de Informática - Curitiba", "Superior"))
        proposals = [_proposal("404 ANALISTA DE INFORMÁTICA")]
        result = reconcile_proposals_by_code(self.db, self.contest, self.obs, table, proposals)
        self.assertEqual(result["assigned"], 1)
        self.assertEqual(result["created"], 1)
        self.assertIsNotNone(proposals[0]["role_id"])
        with closing(connect_documents(self.db)) as conn:
            code = conn.execute("SELECT code FROM cargos_identidade WHERE id=?",
                                (proposals[0]["role_id"],)).fetchone()[0]
        self.assertEqual(code, "404")

    def test_idempotent_reuse(self):
        table = self._table(("404", "Analista de Informática", "Superior"))
        first = reconcile_proposals_by_code(self.db, self.contest, self.obs, table,
                                            [_proposal("404 ANALISTA DE INFORMÁTICA")])
        second = reconcile_proposals_by_code(self.db, self.contest, self.obs, table,
                                             [_proposal("404 ANALISTA DE INFORMÁTICA")])
        self.assertEqual(first["created"], 1)
        self.assertEqual(second["reused"], 1)
        self.assertEqual(second["created"], 0)
        with closing(connect_documents(self.db)) as conn:
            n = conn.execute("SELECT count(*) FROM cargos_identidade WHERE code='404'").fetchone()[0]
        self.assertEqual(n, 1)

    def test_code_absent_from_html_is_pending(self):
        table = self._table(("404", "Analista de Informática", "Superior"))
        proposals = [_proposal("999 CARGO DESCONHECIDO")]
        result = reconcile_proposals_by_code(self.db, self.contest, self.obs, table, proposals)
        self.assertEqual(result["pending"], 1)
        self.assertIsNone(proposals[0]["role_id"])

    def test_code_without_digits_is_pending(self):
        result = reconcile_proposals_by_code(self.db, self.contest, self.obs, [], [_proposal("CARGO X")])
        self.assertEqual(result["pending"], 1)

    def test_conflicting_name_is_ambiguous(self):
        table = self._table(("404", "Analista de Informática", "Superior"))
        proposals = [_proposal("404 MERENDEIRA ESCOLAR")]
        result = reconcile_proposals_by_code(self.db, self.contest, self.obs, table, proposals)
        self.assertEqual(result["ambiguous"], 1)
        self.assertIsNone(proposals[0]["role_id"])

    def test_duplicate_code_in_html_is_ambiguous(self):
        table = self._table(("404", "Analista de Informática", "Superior"),
                            ("404", "Outro Cargo", "Superior"))
        proposals = [_proposal("404 ANALISTA DE INFORMÁTICA")]
        result = reconcile_proposals_by_code(self.db, self.contest, self.obs, table, proposals)
        self.assertEqual(result["ambiguous"], 1)

    def test_already_assigned_is_not_reassigned(self):
        table = self._table(("404", "Analista de Informática", "Superior"))
        proposals = [_proposal("404 ANALISTA DE INFORMÁTICA")]
        proposals[0]["role_id"] = "existing"
        result = reconcile_proposals_by_code(self.db, self.contest, self.obs, table, proposals)
        self.assertEqual(result["assigned"], 0)

    def test_code_is_contextual_to_contest(self):
        # O mesmo código em outro concurso não colide (identidade por concurso).
        other_obs = ensure_observation(self.db, "https://www.quadrix.org.br/informacoes/2/", "quadrix-2")
        with closing(connect_documents(self.db)) as conn:
            other = conn.execute("SELECT contest_id FROM observacoes_concurso WHERE id=?",
                                 (other_obs,)).fetchone()[0]
        table = self._table(("404", "Analista de Informática", "Superior"))
        reconcile_proposals_by_code(self.db, self.contest, self.obs, table,
                                    [_proposal("404 ANALISTA DE INFORMÁTICA")])
        reconcile_proposals_by_code(self.db, other, other_obs, table,
                                    [_proposal("404 ANALISTA DE INFORMÁTICA")])
        with closing(connect_documents(self.db)) as conn:
            n = conn.execute("SELECT count(*) FROM cargos_identidade WHERE code='404'").fetchone()[0]
        self.assertEqual(n, 2)

    def test_name_variation_does_not_crash(self):
        # Regressão: variação benigna de nome no mesmo código não pode abortar.
        table = self._table(("404", "Analista de Informática - Curitiba", "Superior"))
        first = reconcile_proposals_by_code(self.db, self.contest, self.obs, table,
                                            [_proposal("404 ANALISTA DE INFORMÁTICA")])
        table2 = self._table(("404", "Analista de Informática", "Superior"))
        second = reconcile_proposals_by_code(self.db, self.contest, self.obs, table2,
                                             [_proposal("404 ANALISTA DE INFORMÁTICA")])
        self.assertEqual(first["assigned"], 1)
        self.assertEqual(second["reused"], 1)


class LinkContestProposalsTest(unittest.TestCase):
    def test_links_existing_proposals_in_db(self):
        import tempfile
        from contextlib import closing as _closing
        from pathlib import Path
        from radar.document_store import (connect_documents, ensure_observation,
                                          migrate_document_schema, register_document, record_version,
                                          record_analysis)
        tmp = tempfile.TemporaryDirectory(); self.addCleanup(tmp.cleanup)
        db = str(Path(tmp.name) / "db.sqlite3"); migrate_document_schema(db)
        obs = ensure_observation(db, "https://www.quadrix.org.br/informacoes/1/", "quadrix-1")
        with _closing(connect_documents(db)) as conn:
            contest = conn.execute("SELECT contest_id FROM observacoes_concurso WHERE id=?",
                                   (obs,)).fetchone()[0]
        doc = register_document(db, dict(observation_id=obs, kind="outro",
            official_url="https://anexos-r2.selecao.net.br/uploads/x/e.pdf", title="Edital",
            discovery_url="https://www.quadrix.org.br/", discovery_method="automatico",
            discovered_at="2026-10-16T12:00:00+00:00"))
        block = dict(page_number=2, locator="p", start_offset=0, end_offset=1, text="x")
        version = record_version(db, doc, b"%PDF-1.4 x", dict(fetched_at="2026-10-16T12:00:00+00:00",
            fetched_url="https://anexos-r2.selecao.net.br/uploads/x/e.pdf", content_type="application/pdf"))
        record_analysis(db, version, [block], [dict(contest_id=contest, role_id=None,
            field_name="immediate_vacancies", value_json="0", value_type="integer",
            extraction_method="t", ambiguity_reason=LABEL_PREFIX + "404 ANALISTA DE INFORMÁTICA",
            evidence=dict(block_index=0, quote="x", start_offset=0, end_offset=1))])
        from radar.role_reconciliation import link_contest_proposals
        result = link_contest_proposals(db, contest, obs, [{"code": "404",
            "name": "Analista de Informática", "education": "Superior"}])
        self.assertEqual(result["assigned"], 1)
        with _closing(connect_documents(db)) as conn:
            role_id = conn.execute("SELECT role_id FROM propostas_campo WHERE contest_id=?",
                                   (contest,)).fetchone()[0]
        self.assertIsNotNone(role_id)


class ParseCargoTableTest(unittest.TestCase):
    HTML = ("<table><thead><tr><th>Cód.</th><th class='cargo'>Vaga</th>"
            "<th>Escolaridade</th><th>Taxa de Inscrição</th></tr></thead><tbody>"
            "<tr class='impar'><td align='center'>200</td>"
            "<td class='cargo'>Auxiliar Administrativo - Curitiba</td><td>Médio</td>"
            "<td>R$ 66,00</td></tr>"
            "<tr class='par'><td align='center'>404</td>"
            "<td class='cargo'>Analista de Informática</td><td>Superior</td>"
            "<td>R$ 100,00</td></tr></tbody></table>")

    def test_parses_code_name_education(self):
        roles = qx.parse_cargo_table(self.HTML)
        self.assertEqual([r["code"] for r in roles], ["200", "404"])
        self.assertEqual(roles[1]["name"], "Analista de Informática")
        self.assertEqual(roles[1]["education"], "Superior")

    def test_page_without_table_is_empty(self):
        self.assertEqual(qx.parse_cargo_table("<html><body>sem tabela</body></html>"), [])


if __name__ == "__main__":
    unittest.main()
