"""Prova real do pipeline documental com o Anexo I do edital 001/2026 (Guajará-Mirim).

A fixture foi recortada do HTML público da matéria 3E102D15 do Diário Oficial dos
Municípios de Rondônia; preserva o texto real das tabelas e do parágrafo de
inscrições. O objetivo é verificar que o pipeline extrai os quantitativos do
quadro de vagas com evidência, sem replicar o total indígena por cargo.
"""

import json
import unittest
from pathlib import Path

from radar.document_extract import extract_blocks
from radar.document_fields import extract_field_proposals

FIXTURE = Path(__file__).parent / "fixtures" / "documents" / "edital-guajara-anexo-i.html"


class RealEditalExtractTest(unittest.TestCase):
    def setUp(self):
        self.html = FIXTURE.read_bytes()
        self.blocks = extract_blocks(self.html, "text/html; charset=utf-8")

    def _proposals(self):
        return extract_field_proposals(self.blocks, "v", "c")

    def test_table_rows_are_citable_blocks(self):
        joined = " || ".join(b["text"] for b in self.blocks)
        self.assertIn("VAGAS TOTAIS", joined)
        self.assertIn("INDÍGENAS", joined)

    def test_quota_table_preserves_totals_and_per_role_indigenous(self):
        proposals = self._proposals()
        for proposal in proposals:
            evidence = proposal["evidence"]
            block = self.blocks[evidence["block_index"]]
            self.assertEqual(block["text"][evidence["start_offset"]:evidence["end_offset"]],
                             evidence["quote"])

        totals = {(p["field_name"], json.loads(p["value_json"])) for p in proposals
                  if p["ambiguity_reason"] is None}
        self.assertIn(("immediate_vacancies", 107), totals)
        self.assertIn(("indigenous_vacancies", 3), totals)

        ambiguous_indigenous = sorted(
            json.loads(p["value_json"]) for p in proposals
            if p["field_name"] == "indigenous_vacancies" and p["ambiguity_reason"])
        self.assertEqual(ambiguous_indigenous, [0, 0, 1, 2])
        self.assertNotIn(3, ambiguous_indigenous)
        self.assertTrue(all(p["role_id"] is None for p in proposals))

    def test_simple_vagas_table_yields_per_role_immediate(self):
        # Nova capacidade: vagas imediatas por cargo do quadro de cotas (VAGAS TOTAIS);
        # "69 + CR*" na tabela simples dá 69 e não vira reserva.
        per_role = sorted(json.loads(p["value_json"]) for p in self._proposals()
                          if p["field_name"] == "immediate_vacancies" and p["ambiguity_reason"])
        self.assertEqual(per_role, [3, 3, 32, 69])
        self.assertFalse(any(p["field_name"] == "reserve_vacancies" for p in self._proposals()))

    def test_total_107_is_not_duplicated_across_tables(self):
        totals = [p for p in self._proposals()
                  if p["field_name"] == "immediate_vacancies" and p["ambiguity_reason"] is None]
        self.assertEqual([json.loads(p["value_json"]) for p in totals], [107])

    def test_registration_period_in_full_text_form(self):
        proposals = self._proposals()
        dates = {p["field_name"]: json.loads(p["value_json"]) for p in proposals
                 if p["field_name"] in ("registration_start", "registration_end")}
        self.assertEqual(dates.get("registration_start"), "2026-07-10")
        self.assertEqual(dates.get("registration_end"), "2026-07-30")

    def test_does_not_turn_reserve_into_zero(self):
        proposals = self._proposals()
        self.assertFalse(any(p["field_name"] == "reserve_vacancies" for p in proposals))

    def test_table_proposals_never_inherit_document_role(self):
        scoped = extract_field_proposals(self.blocks, "v", "c", role_id="r")
        self.assertFalse(any(p["extraction_method"].startswith("tabela") for p in scoped))
        contest_scope = [p for p in self._proposals()
                         if p["extraction_method"].startswith("tabela")]
        self.assertTrue(contest_scope)
        self.assertTrue(all(p["role_id"] is None for p in contest_scope))

    def test_second_table_does_not_leak_into_quota_proposals(self):
        html = (b"<table><tr><td>CARGO</td><td>VAGAS TOTAIS</td><td>PCD (10%)</td>"
                b"<td>NEGROS (25%)</td><td>IND\xc3\x8dGENAS (3%)</td><td>QUILOMBOLAS (2%)</td>"
                b"<td>AMPLA</td></tr>"
                b"<tr><td>Cargo A</td><td>10</td><td>1</td><td>2</td><td>1</td><td>0</td><td>6</td></tr>"
                b"<tr><td>TOTAL</td><td>10</td><td>1</td><td>2</td><td>1</td><td>0</td><td>6</td></tr></table>"
                b"<table><tr><td>OUTRA TABELA</td><td>99</td><td>9</td><td>9</td><td>9</td>"
                b"<td>9</td><td>9</td></tr></table>")
        blocks = extract_blocks(html, "text/html")
        proposals = extract_field_proposals(blocks, "v", "c")
        values = sorted(json.loads(p["value_json"]) for p in proposals
                        if p["field_name"] == "immediate_vacancies")
        self.assertEqual(values, [10, 10])
        self.assertNotIn(99, values)

    def test_text_form_inverted_period_is_a_diagnostic(self):
        from radar.document_fields import invalid_registration_period
        inverted = extract_blocks(
            b"<p>Inscricoes do dia 30 de julho de 2026 ao dia 10 de julho de 2026.</p>", "text/html")
        self.assertTrue(invalid_registration_period(inverted))
        valid = extract_blocks(
            b"<p>Inscricoes do dia 10 de julho de 2026 ao dia 30 de julho de 2026.</p>", "text/html")
        self.assertFalse(invalid_registration_period(valid))
