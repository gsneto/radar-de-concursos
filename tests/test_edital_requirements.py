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


class CodeGroupTest(unittest.TestCase):
    def test_individual(self):
        self.assertEqual(er.parse_code_group("CÓDIGO 404"), ["404"])

    def test_cargo_marker(self):
        # Variante "CARGO" (editais com "(CARGO 200)").
        self.assertEqual(er.parse_code_group("CARGO 200"), ["200"])
        self.assertEqual(er.parse_code_group("(CARGO 400)"), ["400"])

    def test_range_ate(self):
        self.assertEqual(er.parse_code_group("CÓDIGOS 200 ATÉ 206"),
                         ["200", "201", "202", "203", "204", "205", "206"])

    def test_range_a(self):
        self.assertEqual(er.parse_code_group("CÓDIGOS 400 A 403"), ["400", "401", "402", "403"])

    def test_range_hyphen(self):
        self.assertEqual(er.parse_code_group("CÓDIGOS 400-402"), ["400", "401", "402"])

    def test_range_en_dash(self):
        self.assertEqual(er.parse_code_group("CÓDIGOS 400–402"), ["400", "401", "402"])

    def test_inconsistent_spaces(self):
        self.assertEqual(er.parse_code_group("CÓDIGOS   400   ATÉ   402"), ["400", "401", "402"])

    def test_list(self):
        self.assertEqual(er.parse_code_group("CÓDIGOS 400, 401 E 402"), ["400", "401", "402"])

    def test_implausible_range_not_expanded(self):
        # Amplitude absurda não é código de cargo.
        self.assertEqual(er.parse_code_group("CÓDIGOS 10 ATÉ 5000"), [])

    def test_item_number_is_not_a_code_group(self):
        # Sem o marcador CÓDIGO(S) não há bloco de códigos.
        self.assertEqual(er.parse_code_group("18.1 Conhecimentos técnicos"), [])

    def test_mixed_list_and_range(self):
        # Blocos mistos: a faixa é expandida e os avulsos preservados.
        self.assertEqual(er.parse_code_group("CÓDIGOS 200, 400 ATÉ 402"),
                         ["400", "401", "402", "200"])
        self.assertEqual(er.parse_code_group("CÓDIGOS 400 A 403 E 500"),
                         ["400", "401", "402", "403", "500"])
        self.assertEqual(er.parse_code_group("CÓDIGOS 200 ATÉ 206, 300"),
                         ["200", "201", "202", "203", "204", "205", "206", "300"])

    def test_empty(self):
        self.assertEqual(er.parse_code_group(""), [])
        self.assertEqual(er.parse_code_group(None), [])


class GroupedEducationTest(unittest.TestCase):
    ANEXO = ("36 ANEXO II ATRIBUIÇÕES E REQUISITOS DOS CARGOS "
             "1.1 PROFISSIONAL DE SUPORTE TÉCNICO (PST)-ASSISTENTE (CÓDIGOS 200 ATÉ 202) "
             "a) Requisitos: Diploma de curso de nível médio, fornecido por instituição "
             "reconhecida pelo MEC. "
             "b) Descrição sumária: prestar apoio administrativo. "
             "2.1 ANALISTA DE INFORMÁTICA (CÓDIGOS 400 ATÉ 402) "
             "a) Requisitos: Diploma de graduação na área de Tecnologia da Informação, tais "
             "como Ciência da Computação, Sistemas de Informação, Engenharia de Software ou "
             "outros cursos correlatos reconhecidos pelo MEC. "
             "b) Descrição sumária: instalar softwares. "
             "3.1 ANALISTA DE TI (CÓDIGO 404) "
             "a) Requisitos: Diploma de graduação em Ciência da Computação. "
             "b) Descrição sumária: administrar redes.")

    def test_group_expands_to_each_code(self):
        props = er.extract_education([page(self.ANEXO, 36)], "c", label_prefix="P:")
        edu_labels = sorted(p["ambiguity_reason"][len("P:"):].split(" —")[0]
                            for p in props if p["field_name"] == "education")
        self.assertEqual(edu_labels, ["200", "201", "202", "400", "401", "402",
                                      "404 ANALISTA DE TI"])

    def test_shared_evidence_preserved_for_group(self):
        props = er.extract_education([page(self.ANEXO, 36)], "c", label_prefix="P:")
        block = page(self.ANEXO, 36)
        for p in props:
            ev = p["evidence"]
            self.assertEqual(block["text"][ev["start_offset"]:ev["end_offset"]], ev["quote"])
        # O bloco literal de códigos fica na evidência compartilhada.
        group_400 = next(p for p in props if p["ambiguity_reason"].endswith("400 — bloco CÓDIGOS 400 ATÉ 402"))
        self.assertIn("CÓDIGOS 400 ATÉ 402", group_400["evidence"]["quote"])
        # Os três cargos do grupo compartilham exatamente a mesma evidência.
        same = [p for p in props if p["field_name"] == "education"
                and p["ambiguity_reason"].endswith("bloco CÓDIGOS 400 ATÉ 402")]
        quotes = {p["evidence"]["quote"] for p in same}
        self.assertEqual(len(quotes), 1)

    def test_si_classified_per_group_code(self):
        props = er.extract_education([page(self.ANEXO, 36)], "c", label_prefix="P:")
        si = {p["ambiguity_reason"][len("P:"):].split(" —")[0]: json.loads(p["value_json"])
              for p in props if p["field_name"] == "si_compatibility"}
        self.assertEqual(si["400"], "aceito_expressamente")
        self.assertEqual(si["401"], "aceito_expressamente")
        self.assertEqual(si["402"], "aceito_expressamente")

    def test_conteudo_programatico_not_requirements(self):
        text = ("18 CONTEÚDO PROGRAMÁTICO 18.1 CARGO (CÓDIGOS 400 ATÉ 403): "
                "1 Fundamentos: 1.1 Noções. b) Descrição: nada.")
        self.assertEqual(er.extract_education([page(text, 30)], "c", label_prefix="P:"), [])


class ExemptionRegressionTest(unittest.TestCase):
    """Regressão: a Fase 15 não pode alterar a extração de isenção (Fase 14)."""

    CRONO = ("ANEXO I CRONOGRAMA Item Atividade Datas/Períodos* "
             "3 Período para solicitação de isenção do valor da inscrição 21 e 22/09/2026 "
             "4 Divulgação do resultado preliminar da solicitação de isenção 07/10/2026 "
             "5 Recurso contra o resultado preliminar da isenção 08 e 09/10/2026 "
             "6 Resultado definitivo da solicitação de isenção 14/10/2026 "
             "7 Período de solicitação de inscrição 21/09 a 21/10/2026")

    def test_exemption_dates_unchanged(self):
        props = er.extract_exemption_dates([page(self.CRONO, 5)], "c")
        v = {p["field_name"]: p["value_json"] for p in props}
        self.assertEqual(v["exemption_start"], '"2026-09-21"')
        self.assertEqual(v["exemption_end"], '"2026-09-22"')
        self.assertEqual(v["exemption_result_preliminary"], '"2026-10-07"')
        self.assertEqual(v["exemption_result_final"], '"2026-10-14"')
        self.assertNotEqual(v.get("exemption_end"), '"2026-10-21"')  # não é inscrição


class DeclaredEducationTest(unittest.TestCase):
    def test_labeled_requirement_extracted(self):
        # Modelo do formato FGV: requisito na tabela de vagas, com cabeçalho entre o rótulo e o valor.
        text = ("3.1 A denominação do cargo ... na tabela a seguir: "
                "PODER JUDICIÁRIO DO ESTADO DO AMAPÁ Requisitos de escolaridade "
                "Valor da taxa de inscrição Nível Superior – Direito R$ 358,77 "
                "QUADRO DE VAGAS Cargo Ampla concorrência")
        props = er.extract_declared_education([page(text, 3)], "c", label_prefix="P:")
        edu = [p for p in props if p["field_name"] == "education"]
        self.assertEqual(len(edu), 1)
        self.assertEqual(json.loads(edu[0]["value_json"]), "Nível Superior – Direito")
        si = [p for p in props if p["field_name"] == "si_compatibility"][0]
        self.assertEqual(json.loads(si["value_json"]), "incompativel_com_requisito_explicito")

    def test_evidence_quote_matches_block(self):
        text = ("Requisitos de escolaridade Nível Superior em Ciência da Computação "
                "R$ 100,00 Quadro de vagas")
        block = page(text, 3)
        props = er.extract_declared_education([block], "c", label_prefix="P:")
        self.assertTrue(props)
        for p in props:
            ev = p["evidence"]
            self.assertEqual(block["text"][ev["start_offset"]:ev["end_offset"]], ev["quote"])

    def test_no_label_no_proposal(self):
        text = "O cargo exige nível superior, conforme o quadro anexo."
        self.assertEqual(er.extract_declared_education([page(text, 1)], "c", label_prefix="P:"), [])

    def test_label_without_level_is_ignored(self):
        text = "Requisitos de escolaridade conforme o quadro anexo, sem detalhamento."
        self.assertEqual(er.extract_declared_education([page(text, 1)], "c", label_prefix="P:"), [])

    def test_does_not_capture_across_sentence(self):
        # Regressão: o valor não pode atravessar o fim da frase.
        text = ("Requisitos de escolaridade Nível Superior. A jornada de trabalho é de 40 "
                "horas semanais. O salário inicial é de R$ 12.000,00.")
        props = er.extract_declared_education([page(text, 1)], "c", label_prefix="P:")
        edu = [p for p in props if p["field_name"] == "education"][0]
        self.assertEqual(json.loads(edu["value_json"]), "Nível Superior")

    def test_proper_noun_superior_is_not_a_level(self):
        # Regressão: "Superior Tribunal de Justiça" não é nível de escolaridade.
        text = ("Os requisitos de escolaridade previstos no edital do Superior Tribunal de "
                "Justiça serão exigidos na posse.")
        self.assertEqual(er.extract_declared_education([page(text, 1)], "c", label_prefix="P:"), [])


if __name__ == "__main__":
    unittest.main()
