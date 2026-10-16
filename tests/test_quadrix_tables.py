"""Extrator específico do quadro de vagas da Quadrix (PDF textual)."""

import unittest

from radar.quadrix_tables import (INDIGENOUS_TOKENS, MODALITY_TOKENS, _is_terminator,
                                  parse_quadrix_proposals)

_PREFIX = "cargo do documento não reconciliado: "


def page(text, number=2):
    return dict(page_number=number, locator=f"página {number}", start_offset=0,
                end_offset=len(text), text=text)


def layout_a(rows, modalities=("AC", "PCD", "PN", "PI", "PQ")):
    """Cabeçalho codificado com 'Vagas efetivas' + 'Cadastro de reserva'."""
    mods = " ".join(modalities)
    head = ("2.1.1 CARGOS DE NÍVEL MÉDIO Cod Cargo/Ocupação Vagas efetivas "
            "Cadastro de reserva Total de vagas Local de lotação Carga horária semanal "
            f"Salário base* {mods} {mods} ")
    body = " ".join(f"{r}" for r in rows)
    return head + body


def layout_b(rows, modalities=("AC", "PCD", "PPP", "HIPO")):
    """Cabeçalho por especialidade, sem código, com 'Vagas imediatas'."""
    mods = " ".join(modalities)
    head = ("4.1.2 CARGO: EDAS Especialidade Vagas imediatas Cadastro de reserva "
            f"Total de vagas (incluídas as vagas imediatas) {mods} {mods} ")
    return head + " ".join(rows) + " Legenda: AC: ampla concorrência. / PCD: deficiência."


def parse(text, contest_id="c"):
    return parse_quadrix_proposals([page(text)], contest_id, label_prefix=_PREFIX)


def by_field(props, field):
    return [p for p in props if p["field_name"] == field]


class VocabularyTest(unittest.TestCase):
    def test_indigenous_tokens(self):
        self.assertTrue({"PI", "IND", "INDIGENA"} <= INDIGENOUS_TOKENS)
        self.assertIn("PI", MODALITY_TOKENS)
        self.assertNotIn("AC", INDIGENOUS_TOKENS)  # ampla concorrência não é indígena

    def test_terminators(self):
        self.assertTrue(_is_terminator("Legenda:"))
        self.assertTrue(_is_terminator("2.1.2"))
        self.assertTrue(_is_terminator("TOTAL"))
        self.assertFalse(_is_terminator("200"))


class LayoutATest(unittest.TestCase):
    def test_coded_rows_with_indigenous_column(self):
        text = layout_a([
            "200 Assistente Administrativo - - - - - 18 2 8 1 1 30 Cidade 40h R$ 1,00",
            "206 Analista de Sistemas 3 1 2 - - 49 3 18 2 2 80 Vitória 40h R$ 7,00",
        ])
        props = parse(text)
        imm = {p["ambiguity_reason"][len(_PREFIX):]: p["value_json"] for p in by_field(props, "immediate_vacancies")}
        self.assertEqual(imm["200 Assistente Administrativo"], "0")   # dashes = zero
        self.assertEqual(imm["206 Analista de Sistemas"], "6")        # 3+1+2+0+0
        res = {p["ambiguity_reason"][len(_PREFIX):]: p["value_json"] for p in by_field(props, "reserve_vacancies")}
        self.assertEqual(res["206 Analista de Sistemas"], "74")       # 49+3+18+2+2
        ind = by_field(props, "indigenous_vacancies")
        self.assertEqual(len(ind), 2)  # coluna PI presente em todas as linhas
        self.assertEqual(ind[1]["value_json"], "0")  # PI do cargo 206

    def test_indigenous_immediate_positive(self):
        text = layout_a(["300 Técnico Indígena 5 1 2 4 1 10 2 3 1 1 30 Local 40h R$ 1"])
        ind = by_field(parse(text), "indigenous_vacancies")
        self.assertEqual(len(ind), 1)
        self.assertEqual(ind[0]["value_json"], "4")  # PI imediato = 4

    def test_no_indigenous_column_yields_no_indigenous_proposal(self):
        text = layout_a(["200 Cargo X 1 - - - 5 2 1 1 10 Local 40h R$ 1"],
                        modalities=("AC", "PCD", "PPP", "HIPO"))
        props = parse(text)
        self.assertEqual(by_field(props, "indigenous_vacancies"), [])
        self.assertTrue(by_field(props, "immediate_vacancies"))

    def test_column_order_variation(self):
        # PI em outra posição: a leitura segue o cabeçalho, não a posição fixa.
        text = layout_a(["200 Cargo 1 2 3 4 5 6 7 8 9 10 55 Local 40h R$ 1"],
                        modalities=("PI", "AC", "PCD", "PN", "PQ"))
        ind = by_field(parse(text), "indigenous_vacancies")[0]
        self.assertEqual(ind["value_json"], "1")  # primeira modalidade = PI = 1

    def test_two_complementary_tables_on_same_page(self):
        text = (layout_a(["200 Nível Médio 1 - - - - 5 2 1 1 10 20 A 40h R$ 1"])
                + " 2.1.2 CARGOS DE NÍVEL SUPERIOR Cod Cargo/Ocupação Vagas efetivas "
                  "Cadastro de reserva Total de vagas Local de lotação Carga horária semanal "
                  "Salário base* AC PCD PN PI PQ AC PCD PN PI PQ "
                  "400 Nível Superior 2 - - - - 8 2 3 1 1 17 B 40h R$ 2")
        labels = {p["ambiguity_reason"][len(_PREFIX):] for p in by_field(parse(text), "immediate_vacancies")}
        self.assertEqual(labels, {"200 Nível Médio", "400 Nível Superior"})

    def test_total_row_is_not_a_cargo(self):
        text = layout_a([
            "200 Cargo X - - - - - 18 2 8 1 1 30 Local 40h R$ 1",
            "TOTAL 18 2 8 1 1 30",
        ])
        labels = {p["ambiguity_reason"][len(_PREFIX):] for p in by_field(parse(text), "immediate_vacancies")}
        self.assertEqual(labels, {"200 Cargo X"})

    def test_sum_mismatch_row_is_discarded(self):
        # total 999 não confere com imediatas+reserva → linha descartada
        text = layout_a(["200 Cargo X 1 0 0 0 0 5 0 0 0 0 999 Local 40h R$ 1"])
        self.assertEqual(parse(text), [])

    def test_same_label_different_codes_are_distinct_rows(self):
        text = layout_a([
            "200 Analista - - - - - 1 0 0 0 0 1 A 40h R$ 1",
            "201 Analista - - - - - 2 0 0 0 0 2 B 40h R$ 1",
        ])
        labels = {p["ambiguity_reason"][len(_PREFIX):] for p in by_field(parse(text), "immediate_vacancies")}
        self.assertEqual(labels, {"200 Analista", "201 Analista"})

    def test_stray_number_between_rows_does_not_abort_page(self):
        # Regressão: um número avulso entre linhas não pode descartar as linhas seguintes.
        text = layout_a([
            "200 Cargo A - - - - - 1 0 0 0 0 1 Local 40h",
            "2000",  # token avulso (ano) que não é início de linha válida
            "201 Cargo B - - - - - 2 0 0 0 0 2 Local 40h",
        ])
        labels = {p["ambiguity_reason"][len(_PREFIX):] for p in by_field(parse(text), "immediate_vacancies")}
        self.assertEqual(labels, {"200 Cargo A", "201 Cargo B"})

    def test_blank_cell_row_is_skipped_without_aborting_page(self):
        text = layout_a([
            "200 Cargo A - - - - - 1 0 0 0 0 1 Local 40h",
            "201 Cargo B - - - - 2 0 0 0 0 2 Local 40h",   # valor faltando (10 != 11)
            "202 Cargo C - - - - - 3 0 0 0 0 3 Local 40h",
        ])
        labels = {p["ambiguity_reason"][len(_PREFIX):] for p in by_field(parse(text), "immediate_vacancies")}
        self.assertEqual(labels, {"200 Cargo A", "202 Cargo C"})

    def test_shifted_columns_are_not_proposed(self):
        # Regressão: corrida de valores maior que o cabeçalho (coluna deslocada) não
        # pode emitir proposta que passe na soma por coincidência.
        text = layout_a(["200 Cargo 5 0 0 0 0 0 0 0 0 0 5 5"])
        self.assertEqual(parse(text), [])


class LayoutBTest(unittest.TestCase):
    def test_uncoded_rows(self):
        text = layout_b([
            "Administração 23 10 9 5 70 28 29 14 188",
            "Serviço Social 62 25 25 13 188 75 75 37 500",
        ])
        props = parse(text)
        imm = {p["ambiguity_reason"][len(_PREFIX):]: p["value_json"] for p in by_field(props, "immediate_vacancies")}
        self.assertEqual(imm["Administração"], "47")   # 23+10+9+5
        self.assertEqual(imm["Serviço Social"], "125")  # 62+25+25+13
        self.assertEqual(by_field(props, "indigenous_vacancies"), [])  # sem coluna PI

    def test_multiline_label_and_terminator(self):
        text = layout_b(["Direito e Legislação 57 23 23 12 173 69 69 34 460"])
        props = parse(text)
        self.assertEqual(len(by_field(props, "immediate_vacancies")), 1)
        self.assertEqual(props[0]["ambiguity_reason"], _PREFIX + "Direito e Legislação")


class NegativeTest(unittest.TestCase):
    def test_no_header_no_proposals(self):
        text = "1 DISPOSIÇÕES PRELIMINARES O concurso oferece 100 vagas para diversos cargos."
        self.assertEqual(parse(text), [])

    def test_html_rows_are_ignored(self):
        # Blocos de HTML (com separador de célula) não passam por esta estratégia.
        block = dict(page_number=None, locator="linha de tabela", start_offset=0, end_offset=10,
                     text="CARGO | VAGAS IMEDIATAS | INDÍGENAS")
        self.assertEqual(parse_quadrix_proposals([block], "c", label_prefix=_PREFIX), [])

    def test_divergent_groups_are_skipped(self):
        # Grupos imediato/reserva com modalidades diferentes: layout não reconhecido.
        text = ("Especialidade Vagas imediatas Cadastro de reserva Total de vagas "
                "AC PCD PN PI PQ AC PCD PN PQ HIPO "
                "Administração 1 1 1 1 1 1 1 1 1 1 10")
        self.assertEqual(parse(text), [])


class EvidenceTest(unittest.TestCase):
    def test_evidence_quote_includes_label_and_matches_offsets(self):
        text = layout_a(["200 Analista de Sistemas 3 1 2 - - 49 3 18 2 2 80 Vitória 40h R$ 7"])
        block = page(text)
        props = parse_quadrix_proposals([block], "c", label_prefix=_PREFIX)
        for p in props:
            ev = p["evidence"]
            self.assertEqual(block["text"][ev["start_offset"]:ev["end_offset"]], ev["quote"])
            self.assertIn("Analista de Sistemas", ev["quote"])
            self.assertEqual(ev["block_index"], 0)


if __name__ == "__main__":
    unittest.main()
