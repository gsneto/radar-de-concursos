"""Extração de local de prova a partir do edital (Fase 26)."""

import json
import unittest

from radar import exam_location


def page(text, number=1):
    return [{"page_number": number, "text": text}]


class SingularTest(unittest.TestCase):
    def values(self, text, field="exam_location"):
        return [json.loads(p["value_json"]) for p in
                exam_location.extract_exam_location(page(text), "c1", label_prefix="")
                if p["field_name"] == field]

    def test_cidade_de_com_uf_parentetica(self):
        text = ("2.1 As provas serão realizadas preferencialmente na cidade de Macapá, "
                "no Estado do Amapá (AP).")
        self.assertEqual(self.values(text), ["Macapá/AP"])

    def test_municipio_de(self):
        text = "A prova objetiva ocorrerá no município de Santana, AP."
        self.assertEqual(self.values(text), ["Santana/AP"])

    def test_cidade_do_com_estado_por_extenso(self):
        text = "A Prova Objetiva será realizada na cidade do Salvador, Bahia, no dia 17."
        self.assertEqual(self.values(text), ["Salvador/BA"])

    def test_uf_nao_vem_da_preposicao_para(self):
        # "para" (preposição) não pode virar Pará/PA.
        text = ("As provas serão realizadas na cidade de Macapá e o candidato deve levar "
                "caneta para o local, no Estado do Amapá (AP).")
        self.assertIn("Macapá/AP", self.values(text))

    def test_nao_extrai_municipio_e_uf_quando_ha_varias_cidades(self):
        text = ("As etapas e as fases do concurso serão realizadas nas cidades de "
                "Curitiba/PR e Maringá/PR.")
        proposals = exam_location.extract_exam_location(page(text), "c1", label_prefix="")
        fields = {p["field_name"] for p in proposals}
        self.assertIn("exam_location", fields)
        self.assertNotIn("exam_municipio", fields)

    def test_lista_de_cidades_preservada(self):
        text = ("As provas serão realizadas nas cidades de Colatina/ES, Guarapari/ES "
                "e Vitória/ES.")
        self.assertEqual(self.values(text), ["Colatina/ES; Guarapari/ES; Vitória/ES"])


class RejectionTest(unittest.TestCase):
    def values(self, text):
        return [json.loads(p["value_json"]) for p in
                exam_location.extract_exam_location(page(text), "c1", label_prefix="")
                if p["field_name"] == "exam_location"]

    def test_heteroidentificacao_nao_e_local_de_prova(self):
        text = ("Os procedimentos presenciais de verificação serão realizados na cidade "
                "de Macapá.")
        self.assertEqual(self.values(text), [])

    def test_horario_oficial_nao_e_local(self):
        text = ("A aplicação ocorrerá das 13h às 18h, conforme o horário oficial da cidade "
                "de Brasília (DF).")
        self.assertEqual(self.values(text), [])

    def test_sede_do_orgao_nao_e_local_de_prova(self):
        text = "As provas serão realizadas na sede do órgão, em Brasília/DF."
        self.assertEqual(self.values(text), [])

    def test_texto_sem_contexto_de_prova(self):
        text = "O candidato deverá comparecer ao local designado na cidade de Macapá."
        self.assertEqual(self.values(text), [])

    def test_documento_sem_mencao_nao_gera_proposta(self):
        self.assertEqual(self.values("Edital de abertura de concurso público."), [])


class PendingTest(unittest.TestCase):
    def test_locais_a_divulgar_registrado_como_declaracao(self):
        text = ("10.2 Os locais para a realização da Prova Objetiva Seletiva serão divulgados "
                "no endereço eletrônico do concurso a partir do dia 18 de janeiro de 2027.")
        values = [json.loads(p["value_json"]) for p in
                  exam_location.extract_exam_location(page(text), "c1", label_prefix="")]
        self.assertEqual(values, ["a_divulgar"])

    def test_a_divulgar_nao_vira_cidade(self):
        text = ("Os locais de prova serão divulgados oportunamente; os candidatos devem "
                "acompanhar o site.")
        proposals = exam_location.extract_exam_location(page(text), "c1", label_prefix="")
        self.assertEqual([p["field_name"] for p in proposals], ["exam_location"])


class EvidenceTest(unittest.TestCase):
    def test_evidencia_aponta_pagina_e_trecho_literal(self):
        text = ("6.1 A prova será realizada na cidade de Palmas, no Estado do Tocantins (TO). "
                "6.2 Outras regras.")
        blocks = [{"page_number": 12, "text": text}]
        proposal = exam_location.extract_exam_location(blocks, "c1", label_prefix="")[0]
        evidence = proposal["evidence"]
        self.assertEqual(evidence["page_number"], 12)
        self.assertEqual(text[evidence["start_offset"]:evidence["end_offset"]],
                         evidence["quote"])
        self.assertIn("Palmas", evidence["quote"])

    def test_toda_proposta_nasce_ambigua(self):
        text = "A prova será realizada na cidade de Palmas, TO."
        for proposal in exam_location.extract_exam_location(page(text), "c1", label_prefix=""):
            self.assertTrue(proposal["ambiguity_reason"])
            self.assertEqual(proposal["extraction_method"], "local-prova")

    def test_multiplas_paginas(self):
        blocks = [{"page_number": 1, "text": "A prova será realizada na cidade de Palmas, TO."},
                  {"page_number": 2, "text": "A prova será realizada na cidade de Gurupi, TO."}]
        proposals = exam_location.extract_exam_location(blocks, "c1", label_prefix="")
        values = [json.loads(p["value_json"]) for p in proposals
                  if p["field_name"] == "exam_location"]
        self.assertEqual(len(values), 2)


class RegressionTest(unittest.TestCase):
    """Casos levantados na revisão independente da Fase 26."""

    def props(self, text):
        return exam_location.extract_exam_location(
            [{"page_number": 1, "text": text}], "c1", label_prefix="")

    def values(self, text):
        return [json.loads(p["value_json"]) for p in self.props(text)
                if p["field_name"] == "exam_location"]

    def test_lotacao_nao_vira_local_de_prova(self):
        text = ("A lotação dos candidatos será na cidade de Macapá e as provas serão "
                "realizadas em Belém/PA.")
        self.assertEqual(self.values(text), ["Belém/PA"])

    def test_uf_preservada_na_mesma_cidade(self):
        text = "As provas serão realizadas na cidade de Macapá/AP, das 13h às 18h."
        self.assertEqual(self.values(text), ["Macapá/AP"])

    def test_uf_falsa_nao_e_aceita(self):
        for text in ("As provas serão realizadas na cidade de Macapá, em 2026.",
                     "As provas serão realizadas na cidade de Macapá, as 13h."):
            for proposal in self.props(text):
                if proposal["field_name"] == "exam_uf":
                    self.fail("UF inventada em: " + text)

    def test_lista_com_e_nao_vira_um_municipio(self):
        text = "As provas serão realizadas na cidade de Macapá e Santana."
        self.assertEqual(self.values(text), ["Macapá; Santana"])
        fields = {p["field_name"] for p in self.props(text)}
        self.assertNotIn("exam_municipio", fields)

    def test_local_singular_a_divulgar(self):
        text = "O local de prova será divulgado oportunamente."
        self.assertEqual(self.values(text), ["a_divulgar"])

    def test_passado_nao_e_pendencia(self):
        text = "Os locais de prova foram divulgados no site oficial."
        self.assertEqual(self.values(text), [])


if __name__ == "__main__":
    unittest.main()
