"""Extrator genérico de quadro de vagas: colunas, modalidades, ambiguidade e incerteza."""

import json
import unittest

from radar.document_fields import LABEL_PREFIX
from radar import vacancy_tables as vt


def rows(*cell_lists):
    """Constrói blocos de linha a partir de listas de células (como `_HTMLBlocks`)."""
    return [dict(index=i, text=" | ".join(cells), page_number=None)
            for i, cells in enumerate(cell_lists)]


def values(proposals, field):
    return sorted(json.loads(p["value_json"]) for p in proposals if p["field_name"] == field)


class NormalizeTest(unittest.TestCase):
    def test_normalize_removes_accents_and_case(self):
        self.assertEqual(vt.normalize("Indígenas (3%)"), "INDIGENAS (3%)")
        self.assertEqual(vt.normalize(None), "")


class ColumnMappingTest(unittest.TestCase):
    def test_order_independent(self):
        role, columns = vt.map_columns(["VAGAS", "INDÍGENAS", "CARGO"])
        self.assertEqual(role, 2)
        self.assertEqual(columns, {"immediate_vacancies": 0, "indigenous_vacancies": 1})

    def test_vagas_totais_is_immediate_not_indigenous(self):
        _, columns = vt.map_columns(["CARGO", "VAGAS TOTAIS", "INDÍGENAS (3%)"])
        self.assertEqual(columns["immediate_vacancies"], 1)
        self.assertEqual(columns["indigenous_vacancies"], 2)

    def test_reserve_column(self):
        _, columns = vt.map_columns(["CARGO", "CADASTRO DE RESERVA"])
        self.assertEqual(columns["reserve_vacancies"], 1)

    def test_cr_is_word_only_not_substring(self):
        # "CRECHE"/"INSCRIÇÕES"/"CRONOGRAMA" contêm "CR" mas não são reserva.
        for header in ("VAGAS PARA CRECHE", "INSCRIÇÕES", "CRONOGRAMA", "DESCRIÇÃO"):
            _, columns = vt.map_columns(["CARGO", header])
            self.assertNotIn("reserve_vacancies", columns, header)
        _, columns = vt.map_columns(["CARGO", "VAGAS", "CR"])
        self.assertEqual(columns.get("reserve_vacancies"), 2)

    def test_ampla_is_not_immediate(self):
        # "AMPLA CONCORRÊNCIA" é modalidade (subconjunto), não vagas imediatas totais.
        _, columns = vt.map_columns(["CARGO", "AMPLA CONCORRÊNCIA", "VAGAS"])
        self.assertEqual(columns.get("immediate_vacancies"), 2)
        _, only_ampla = vt.map_columns(["CARGO", "AMPLA CONCORRÊNCIA"])
        self.assertNotIn("immediate_vacancies", only_ampla)

    def test_no_role_token_is_not_header(self):
        role, columns = vt.map_columns(["OUTRA TABELA", "99", "9"])
        self.assertIsNone(role)


class QuantityTest(unittest.TestCase):
    def test_explicit_zero(self):
        self.assertEqual(vt.parse_quantity("0"), 0)

    def test_cr_without_number(self):
        self.assertIsNone(vt.parse_quantity("CR"))
        # O inteiro da célula é o imediato; o texto do CR fica na evidência (quote).
        self.assertEqual(vt.parse_quantity("69 + CR*"), 69)

    def test_blank_is_unknown(self):
        self.assertIsNone(vt.parse_quantity(""))
        self.assertIsNone(vt.parse_quantity("—"))


class ExtractTest(unittest.TestCase):
    def test_role_and_total(self):
        proposals = vt.extract(
            rows(["CARGO", "VAGAS"], ["Professor", "69"], ["TOTAL", "69"]),
            "c", label_prefix=LABEL_PREFIX)
        self.assertEqual(values(proposals, "immediate_vacancies"), [69, 69])
        role_row = [p for p in proposals if p["ambiguity_reason"]]
        total_row = [p for p in proposals if p["ambiguity_reason"] is None]
        self.assertEqual(role_row[0]["ambiguity_reason"], LABEL_PREFIX + "Professor")
        self.assertIsNone(total_row[0]["evidence"]["role_label"])

    def test_indigenous_per_role_when_present(self):
        proposals = vt.extract(
            rows(["CARGO", "VAGAS TOTAIS", "INDÍGENAS (3%)"],
                 ["Prof A", "69", "2"], ["Prof B", "32", "1"], ["TOTAL", "101", "3"]),
            "c", label_prefix=LABEL_PREFIX)
        per_role = [p for p in proposals if p["field_name"] == "indigenous_vacancies"
                    and p["ambiguity_reason"]]
        self.assertEqual(sorted(json.loads(p["value_json"]) for p in per_role), [1, 2])
        totals = [p for p in proposals if p["field_name"] == "indigenous_vacancies"
                  and p["ambiguity_reason"] is None]
        self.assertEqual(json.loads(totals[0]["value_json"]), 3)

    def test_global_indigenous_not_replicated_per_role(self):
        proposals = vt.extract(
            rows(["CARGO", "VAGAS", "INDÍGENAS"],
                 ["Prof A", "10", ""], ["Prof B", "20", ""], ["TOTAL", "30", "3"]),
            "c", label_prefix=LABEL_PREFIX)
        per_role_ind = [p for p in proposals if p["field_name"] == "indigenous_vacancies"
                        and p["ambiguity_reason"]]
        self.assertEqual(per_role_ind, [])
        self.assertEqual(values(proposals, "indigenous_vacancies"), [3])

    def test_cadastro_de_reserva_column_with_number(self):
        proposals = vt.extract(
            rows(["CARGO", "VAGAS", "CADASTRO DE RESERVA"], ["Prof A", "10", "5"]),
            "c", label_prefix=LABEL_PREFIX)
        self.assertEqual(values(proposals, "reserve_vacancies"), [5])

    def test_cr_without_number_does_not_become_zero_or_immediate(self):
        proposals = vt.extract(
            rows(["CARGO", "VAGAS"], ["Prof A", "69 + CR*"]), "c", label_prefix=LABEL_PREFIX)
        self.assertEqual(values(proposals, "immediate_vacancies"), [69])
        self.assertEqual([p for p in proposals if p["field_name"] == "reserve_vacancies"], [])
        # A evidência preserva o texto original (com o marcador CR), sem virar número.
        self.assertEqual(proposals[0]["evidence"]["quote"], "Prof A | 69 + CR*")

    def test_blank_cell_is_unknown_not_zero(self):
        proposals = vt.extract(
            rows(["CARGO", "VAGAS", "INDÍGENAS"], ["Prof A", "10", ""], ["Prof B", "20", "1"]),
            "c", label_prefix=LABEL_PREFIX)
        self.assertEqual(values(proposals, "immediate_vacancies"), [10, 20])
        self.assertEqual(values(proposals, "indigenous_vacancies"), [1])

    def test_two_row_header_is_merged(self):
        proposals = vt.extract(
            rows(["CARGO", "VAGAS", ""], ["", "TOTAL", "INDÍGENAS"], ["Prof A", "69", "2"]),
            "c", label_prefix=LABEL_PREFIX)
        self.assertEqual(values(proposals, "immediate_vacancies"), [69])
        self.assertEqual(values(proposals, "indigenous_vacancies"), [2])

    def test_role_name_line_breaks_are_normalized(self):
        proposals = vt.extract(
            rows(["CARGO", "VAGAS"], ["  Prof   de\nEducação   Infantil ", "69"]),
            "c", label_prefix=LABEL_PREFIX)
        label = proposals[0]["ambiguity_reason"][len(LABEL_PREFIX):]
        self.assertEqual(label, "Prof de Educação Infantil")

    def test_number_in_non_vacancy_table_is_ignored(self):
        proposals = vt.extract(
            rows(["ITEM", "VALOR"], ["Serviço", "99"]), "c", label_prefix=LABEL_PREFIX)
        self.assertEqual(proposals, [])

    def test_two_similar_role_names_are_not_merged(self):
        proposals = vt.extract(
            rows(["CARGO", "VAGAS"],
                 ["Prof. de Educação Infantil", "69"],
                 ["Prof. de Educação Infantil (Libras)", "3"]),
            "c", label_prefix=LABEL_PREFIX)
        labels = sorted(p["ambiguity_reason"] for p in proposals)
        self.assertEqual(len(set(labels)), 2)

    def test_evidence_carries_header_and_page(self):
        proposals = vt.extract(
            rows(["CARGO", "VAGAS"], ["Prof A", "10"]), "c", label_prefix=LABEL_PREFIX,
            section_title="ANEXO I", method="tabela")
        ev = proposals[0]["evidence"]
        self.assertEqual(ev["header"], "CARGO | VAGAS")
        self.assertEqual(ev["section"], "ANEXO I")
        self.assertEqual(ev["quote"], "Prof A | 10")
        self.assertEqual(ev["block_index"], 1)
        self.assertEqual(proposals[0]["extraction_method"], "tabela")

    def test_no_header_returns_empty(self):
        self.assertEqual(vt.extract(rows(["a", "b"], ["c", "d"]), "c", label_prefix=LABEL_PREFIX), [])


class BestTableTest(unittest.TestCase):
    def test_prefers_table_with_more_modalities(self):
        simple = rows(["CARGO", "VAGAS"], ["Prof A", "10"])
        quota = rows(["CARGO", "VAGAS TOTAIS", "INDÍGENAS"], ["Prof A", "10", "1"])
        self.assertIs(vt.best_table([simple, quota]), quota)
        self.assertIs(vt.best_table([quota, simple]), quota)

    def test_returns_none_without_vacancy_table(self):
        self.assertIsNone(vt.best_table([rows(["ITEM", "VALOR"], ["x", "9"])]))


if __name__ == "__main__":
    unittest.main()
