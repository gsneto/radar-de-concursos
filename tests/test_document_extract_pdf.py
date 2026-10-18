"""Extração do quadro de cotas a partir do texto de PDF (edição oficial real).

A fixture é o texto da página 266 da edição 3E102D15 do Diário Oficial dos
Municípios de Rondônia, com o Anexo I (quadro geral de vagas). O bloco simula a
saída do pipeline de PDF, que colapsa o espaço em branco por página.
"""

import json
import unittest
from pathlib import Path

from radar.document_fields import LABEL_PREFIX, PDF_SCOPE_REASON, extract_field_proposals

FIXTURE = Path(__file__).parent / "fixtures" / "documents" / "edital-anexo-i-page.txt"

_HEADER = ("QUADRO GERAL DE VAGAS CARGO VAGAS TOTAIS PCD (10%) NEGROS (25%) "
           "INDÍGENAS (3%) QUILOMBOLAS (2%) AMPLA CONCORRÊNCIA ")


def _block(text, page=266):
    text = " ".join(text.split())
    return dict(page_number=page, locator=f"página {page}",
                start_offset=0, end_offset=len(text), text=text)


class PdfQuotaTableTest(unittest.TestCase):
    def setUp(self):
        self.blocks = [_block(FIXTURE.read_text(encoding="utf-8"))]
        self.proposals = extract_field_proposals(self.blocks, "v", "c")

    def _rows(self, field, reason_kind):
        return sorted(json.loads(p["value_json"]) for p in self.proposals
                      if p["field_name"] == field and p["extraction_method"] == "tabela-pdf"
                      and (p["ambiguity_reason"] == PDF_SCOPE_REASON if reason_kind == "total"
                           else (p["ambiguity_reason"] or "").startswith(LABEL_PREFIX)))

    def test_evidence_quotes_match_blocks(self):
        self.assertTrue(self.proposals)
        for proposal in self.proposals:
            evidence = proposal["evidence"]
            block = self.blocks[evidence["block_index"]]
            self.assertEqual(block["text"][evidence["start_offset"]:evidence["end_offset"]],
                             evidence["quote"])

    def test_totals_are_scope_ambiguous_and_per_role_quotas(self):
        self.assertEqual(self._rows("immediate_vacancies", "total"), [107])
        self.assertEqual(self._rows("indigenous_vacancies", "total"), [3])
        self.assertEqual(self._rows("immediate_vacancies", "cargo"), [3, 3, 32, 69])
        self.assertEqual(self._rows("indigenous_vacancies", "cargo"), [0, 0, 1, 2])

    def test_indigenous_total_is_not_replicated_per_role(self):
        self.assertNotIn(3, self._rows("indigenous_vacancies", "cargo"))

    def test_numeric_registration_period(self):
        dates = {p["field_name"]: json.loads(p["value_json"]) for p in self.proposals
                 if p["field_name"] in ("registration_start", "registration_end")}
        self.assertEqual(dates.get("registration_start"), "2026-07-10")
        self.assertEqual(dates.get("registration_end"), "2026-07-30")

    def test_exemption_period_is_not_registration_period(self):
        text = ("Os pedidos de isenção poderão ser feitos dia 21 de setembro de 2026 "
                "até as 16h do dia 22 de setembro de 2026.")
        proposals = extract_field_proposals([_block(text)], "v", "c")
        self.assertEqual([p for p in proposals
                          if p["field_name"] in ("registration_start", "registration_end")], [])

    def test_registration_period_with_anchor_is_extracted(self):
        text = ("As inscrições estarão abertas dia 21 de setembro de 2026 até as 16h "
                "do dia 30 de outubro de 2026.")
        proposals = extract_field_proposals([_block(text)], "v", "c")
        values = {p["field_name"]: json.loads(p["value_json"]) for p in proposals
                  if p["field_name"] in ("registration_start", "registration_end")}
        self.assertEqual(values.get("registration_start"), "2026-09-21")
        self.assertEqual(values.get("registration_end"), "2026-10-30")

    def test_unanchored_pdf_facts_are_scope_ambiguous(self):
        generic = [p for p in self.proposals if p["extraction_method"] == "regex"]
        self.assertTrue(generic)
        self.assertTrue(all(p["ambiguity_reason"] == PDF_SCOPE_REASON for p in generic))

    def test_label_ending_in_digit_does_not_corrupt_row(self):
        text = _HEADER + "Prof Nivel 2 69 7 17 2 1 42 TOTAL 69 7 17 2 1 42"
        proposals = extract_field_proposals([_block(text)], "v", "c")
        rows = {p["field_name"]: json.loads(p["value_json"]) for p in proposals
                if p["extraction_method"] == "tabela-pdf"
                and (p["ambiguity_reason"] or "").startswith(LABEL_PREFIX)}
        self.assertEqual(rows.get("immediate_vacancies"), 69)
        self.assertEqual(rows.get("indigenous_vacancies"), 2)

    def test_role_scoped_document_does_not_emit_quota_table(self):
        blocks = [_block(FIXTURE.read_text(encoding="utf-8"))]
        proposals = extract_field_proposals(blocks, "v", "c", role_id="r")
        self.assertFalse(any(p["extraction_method"].startswith("tabela") for p in proposals))
