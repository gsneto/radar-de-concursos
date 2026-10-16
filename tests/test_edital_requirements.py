"""Requisitos de formação, compatibilidade com SI e prazos de isenção."""

import json
import unittest

from radar import edital_requirements as er


def page(text, number=1):
    return dict(page_number=number, locator=f"página {number}", start_offset=0,
                end_offset=len(text), text=text)


class SICompatibilityTest(unittest.TestCase):
    def test_si_literal_is_accepted(self):
        state, _ = er.classify_si_compatibility(
            "graduação na área de Tecnologia da Informação, tais como Ciência da Computação, "
            "Sistemas de Informação, Engenharia de Software ou outros correlatos")
        self.assertEqual(state, "aceito_expressamente")

    def test_broad_category_with_opening(self):
        state, _ = er.classify_si_compatibility(
            "curso de nível superior na área de Tecnologia da Informação ou área correlata")
        self.assertEqual(state, "abrangido_por_categoria")

    def test_broad_category_without_opening_is_ambiguous(self):
        state, _ = er.classify_si_compatibility("curso superior em Ciência da Computação")
        self.assertEqual(state, "ambiguo")

    def test_non_computing_requirement(self):
        state, _ = er.classify_si_compatibility(
            "Diploma de conclusão de curso de graduação em Direito, com registro na OAB")
        self.assertEqual(state, "incompativel_com_requisito_explicito")

    def test_empty_is_nao_informado(self):
        self.assertEqual(er.classify_si_compatibility("")[0], "nao_informado")
        self.assertEqual(er.classify_si_compatibility(None)[0], "nao_informado")

    def test_ti_title_alone_does_not_prove(self):
        # Requisito de área alheia, mesmo com título de TI, não vira "aceito".
        state, _ = er.classify_si_compatibility("curso superior em Administração")
        self.assertNotEqual(state, "aceito_expressamente")


class EducationExtractionTest(unittest.TestCase):
    ANEXO = ("36 ANEXO II ATRIBUIÇÕES E REQUISITOS DOS CARGOS "
             "3.2 ANALISTA DE INFORMÁTICA (CÓDIGO 404) "
             "a) Requisitos: Diploma ou certificado de curso de graduação na área de "
             "Tecnologia da Informação, tais como Ciência da Computação, Sistemas de "
             "Informação, Engenharia de Software ou outros cursos correlatos reconhecidos "
             "pelo MEC. "
             "b) Descrição sumária das atividades: instalar e configurar softwares. "
             "3.3 ASSESSOR JURÍDICO (CÓDIGO 405) "
             "a) Requisitos: Diploma de curso de graduação em Direito e registro na OAB. "
             "b) Descrição sumária: prestar assessoria jurídica.")

    def test_extracts_education_courses_and_si(self):
        props = er.extract_education([page(self.ANEXO, 36)], "c", label_prefix="P:")
        by = {(p["field_name"], p["ambiguity_reason"]): p for p in props}
        edu = [p for p in props if p["field_name"] == "education"]
        self.assertEqual(len(edu), 2)
        labels = {p["ambiguity_reason"][len("P:"):] for p in edu}
        self.assertEqual(labels, {"404 ANALISTA DE INFORMÁTICA", "405 ASSESSOR JURÍDICO"})
        courses = {p["ambiguity_reason"][len("P:"):]: json.loads(p["value_json"]) for p in props
                   if p["field_name"] == "accepted_courses"}
        self.assertIn("Sistemas de Informação", courses["404 ANALISTA DE INFORMÁTICA"])
        si = {p["ambiguity_reason"][len("P:"):].split(" —")[0]: json.loads(p["value_json"])
              for p in props if p["field_name"] == "si_compatibility"}
        self.assertEqual(si["404 ANALISTA DE INFORMÁTICA"], "aceito_expressamente")
        self.assertIn("incompativel", si["405 ASSESSOR JURÍDICO"])

    def test_evidence_quote_matches_block(self):
        block = page(self.ANEXO, 36)
        props = er.extract_education([block], "c", label_prefix="P:")
        for p in props:
            ev = p["evidence"]
            self.assertEqual(block["text"][ev["start_offset"]:ev["end_offset"]], ev["quote"])
            self.assertTrue(ev["quote"].strip())

    def test_conteudo_programatico_header_is_not_education(self):
        # Cabeçalho de conteúdo programático (sem "a) Requisitos" perto) não gera proposta.
        text = ("18 CONTEÚDO PROGRAMÁTICO 18.1 AGENTE FISCAL (CÓDIGO 400): "
                "1 Conhecimentos técnicos: 1.1 Propriedades da matéria. "
                "b) Descrição sumária: nada.")
        self.assertEqual(er.extract_education([page(text, 30)], "c", label_prefix="P:"), [])

    def test_nivel_medio_has_no_courses_list(self):
        text = ("1.1 AUXILIAR ADMINISTRATIVO (CÓDIGO 200) a) Requisitos: Diploma ou "
                "certificado de conclusão de curso de nível médio, fornecido por instituição "
                "reconhecida pelo MEC. b) Descrição: realizar trabalhos.")
        props = er.extract_education([page(text, 2)], "c", label_prefix="P:")
        self.assertEqual([p for p in props if p["field_name"] == "accepted_courses"], [])
        self.assertEqual([p for p in props if p["field_name"] == "education"], props[:1])


class ExemptionDatesTest(unittest.TestCase):
    CRONO = ("ANEXO I CRONOGRAMA Item Atividade Datas/Períodos* "
             "3 Período para solicitação de isenção do valor da inscrição e envio da "
             "documentação, exclusivamente via upload no sistema eletrônico de isenção "
             "21 e 22/09/2026 Das 10 horas do primeiro dia às 18 horas do último dia "
             "4 Divulgação do resultado preliminar da solicitação de isenção do valor da "
             "inscrição 07/10/2026 "
             "5 Período para a interposição de recurso contra o resultado preliminar da "
             "isenção do valor da inscrição 08 e 09/10/2026 Das 10 horas às 18 horas "
             "6 Divulgação das respostas de recursos e do resultado definitivo da solicitação "
             "de isenção do valor da inscrição 14/10/2026 "
             "7 Período de solicitação de inscrição 21/09 a 21/10/2026")

    def _values(self):
        props = er.extract_exemption_dates([page(self.CRONO, 5)], "c")
        return {p["field_name"]: p["value_json"] for p in props}

    def test_extracts_all_exemption_dates(self):
        v = self._values()
        self.assertEqual(v["exemption_start"], '"2026-09-21"')
        self.assertEqual(v["exemption_end"], '"2026-09-22"')
        self.assertEqual(v["exemption_result_preliminary"], '"2026-10-07"')
        self.assertEqual(v["exemption_appeal"], '"2026-10-08"')
        self.assertEqual(v["exemption_result_final"], '"2026-10-14"')

    def test_does_not_confuse_with_registration_deadline(self):
        v = self._values()
        # A inscrição (21/09 a 21/10) não pode virar prazo de isenção.
        self.assertNotEqual(v.get("exemption_end"), '"2026-10-21"')

    def test_body_text_without_date_is_ignored(self):
        text = ("6.9.3 O resultado preliminar da solicitação de isenção do valor da inscrição "
                "será divulgado na data provável estabelecida no cronograma do Anexo I.")
        self.assertEqual(er.extract_exemption_dates([page(text, 6)], "c"), [])

    def test_does_not_cross_sentence_into_registration_dates(self):
        # Regressão: a data da inscrição na frase seguinte não pode virar isenção.
        text = ("Período para solicitação de isenção, conforme o cronograma. "
                "As inscrições ocorrem de 01/03 a 20/03/2024 e o pagamento até 21/03/2024.")
        props = er.extract_exemption_dates([page(text, 5)], "c")
        values = {p["value_json"] for p in props}
        self.assertNotIn('"2024-03-01"', values)
        self.assertNotIn('"2024-03-20"', values)

    def test_same_month_range_with_a(self):
        text = "Período para solicitação de isenção do valor da inscrição 18 a 19/03/2026."
        props = er.extract_exemption_dates([page(text, 5)], "c")
        v = {p["field_name"]: p["value_json"] for p in props}
        self.assertEqual(v["exemption_start"], '"2026-03-18"')
        self.assertEqual(v["exemption_end"], '"2026-03-19"')

    def test_no_exemption_information(self):
        text = "2 DOS CARGOS E VAGAS. Não há isenção prevista neste edital específico."
        self.assertEqual(er.extract_exemption_dates([page(text, 2)], "c"), [])


if __name__ == "__main__":
    unittest.main()
