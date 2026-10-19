"""Quadros de vagas por coluna, notação de reserva e distribuição em texto (Fase 41)."""

import json
import sqlite3
import unittest
from contextlib import closing

from radar import modality_legend, vacancy_columns, vacancy_inline
from tests.test_portfolio_f36 import NOON, add_document, add_proposal, make_db

LABEL = "cargo do documento não reconciliado: "

LEGEND = (
    "6.1.7.3. Para fins de identificação das posições, serão utilizadas as seguintes "
    "siglas: I – AC: Ampla Concorrência; II – PcD: Pessoas com Deficiência; "
    "III – PP: Pessoas Pretas e Pardas; IV – PI: Pessoas Indígenas; "
    "V – PQ: Pessoas Quilombolas; VI – PPIQ: vaga unificada destinada às Pessoas Pretas "
    "e Pardas, Pessoas Indígenas e Pessoas Quilombolas; VII – PI/PQ: vaga unificada "
    "destinada às Pessoas Indígenas e Pessoas Quilombolas; e VIII – PP*: vaga adicional "
    "destinada às Pessoas Pretas e Pardas.")


class LegendTest(unittest.TestCase):
    def setUp(self):
        self.definitions = modality_legend.parse_definitions(LEGEND)

    def test_definicoes_do_documento(self):
        self.assertIn("PI", self.definitions)
        self.assertEqual(self.definitions["PI"]["label"], "Pessoas Indígenas")
        self.assertFalse(self.definitions["PI"]["unified"])
        self.assertTrue(self.definitions["PPIQ"]["unified"])
        self.assertEqual(sorted(self.definitions["PPIQ"]["groups"]),
                         ["indigenas", "pretas_e_pardas", "quilombolas"])
        self.assertEqual(sorted(self.definitions["PI/PQ"]["groups"]),
                         ["indigenas", "quilombolas"])

    def test_sem_definicao_nao_presume_semantica(self):
        self.assertEqual(modality_legend.kind({}, "PI"), "unknown")
        self.assertEqual(modality_legend.kind(self.definitions, "PI"), "exclusive")
        self.assertEqual(modality_legend.kind(self.definitions, "PPIQ"), "unified")
        self.assertEqual(modality_legend.kind(self.definitions, "Total"), "aggregate")

    def test_sigla_igual_em_outro_edital_nao_herda_significado(self):
        outro = modality_legend.parse_definitions(
            "I – PI: Polícia de Investigações; II – AC: Apoio Administrativo.")
        self.assertFalse(outro["PI"]["unified"])
        self.assertEqual(outro["PI"]["groups"], [])
        self.assertEqual(modality_legend.kind(outro, "PPIQ"), "unknown")

    def test_definicao_com_dois_grupos_e_unificada(self):
        # Sem a palavra "unificada", nomear dois grupos ainda é vaga compartilhada.
        definitions = modality_legend.parse_definitions(
            "I – PI: Pessoas Indígenas e Quilombolas.")
        self.assertEqual(modality_legend.kind(definitions, "PI"), "unified")


class CrNotationTest(unittest.TestCase):
    def test_numero_mais_cadastro(self):
        self.assertEqual(modality_legend.cr_notation("10+CR"),
                         {"immediate": 10, "reserve": True, "asterisk": False,
                          "explicit_zero": False, "raw": "10+CR"})

    def test_cadastro_com_asterisco_nao_vira_zero_nem_imediato(self):
        parsed = modality_legend.cr_notation("CR*")
        self.assertIsNone(parsed["immediate"])
        self.assertTrue(parsed["reserve"])
        self.assertTrue(parsed["asterisk"])

    def test_cadastro_sem_numero(self):
        parsed = modality_legend.cr_notation("CR")
        self.assertIsNone(parsed["immediate"])
        self.assertTrue(parsed["reserve"])

    def test_total_com_cadastro(self):
        self.assertEqual(modality_legend.cr_notation("15 + CR")["immediate"], 15)

    def test_zero_explicito(self):
        parsed = modality_legend.cr_notation("-")
        self.assertEqual(parsed["immediate"], 0)
        self.assertTrue(parsed["explicit_zero"])

    def test_celula_que_nao_e_quantidade(self):
        self.assertIsNone(modality_legend.cr_notation("a definir"))

    def test_nota_do_asterisco(self):
        text = ("* Vaga adicional destinada a assegurar o percentual mínimo global. "
                "CANDIDATO: RENDA* 1 2 3")
        note = modality_legend.asterisk_note(text)
        self.assertIsNotNone(note)
        self.assertIn("Vaga adicional", note)

    def test_linha_de_renda_nao_e_nota_de_quadro(self):
        self.assertIsNone(modality_legend.asterisk_note("RENDA* 1 2 3 4"))


def _build_pdf(rows, *, header=("AC", "PcD", "PP", "PI", "PQ", "PPIQ", "PI/PQ", "Total"),
               legend_row=None, total_row=None, title="ANEXO II - QUADRO DE VAGAS"):
    """PDF mínimo com o mesmo arranjo de colunas do Anexo II (posições reais)."""
    import pymupdf

    document = pymupdf.open()
    page = document.new_page(width=612, height=792)
    page.insert_text((20, 40), title, fontsize=8)
    xs = [150, 240, 296, 357, 386, 414, 443, 471, 499, 527, 552]
    labels = ["Cargo", "Formação", "Escolaridade"]
    for x, text in zip(xs[:3], labels):
        page.insert_text((x, 80), text, fontsize=7)
    for x, text in zip(xs[3:], header):
        page.insert_text((x, 80), text, fontsize=7)
    y = 110
    for row in rows:
        page.insert_text((20, y), row.get("dre", ""), fontsize=7)
        page.insert_text((150, y), row["cargo"], fontsize=7)
        page.insert_text((240, y), row["formacao"], fontsize=7)
        page.insert_text((296, y), row["escolaridade"], fontsize=7)
        for x, value in zip(xs[3:], row["values"]):
            page.insert_text((x, y), value, fontsize=7)
        y += 26
    if total_row is not None:
        page.insert_text((20, y), total_row["label"], fontsize=7)
        for x, value in zip(xs[3:], total_row["values"]):
            page.insert_text((x, y), value, fontsize=7)
        y += 26
    if legend_row:
        page.insert_text((20, y + 20), legend_row, fontsize=7)
    return document.tobytes()


def _blocks(pdf_bytes):
    from radar.document_extract import extract_document
    return extract_document(pdf_bytes, "application/pdf")["blocks"]


class WideTableTest(unittest.TestCase):
    def setUp(self):
        self.definitions = modality_legend.parse_definitions(LEGEND)

    def parse(self, rows, **kwargs):
        pdf = _build_pdf(rows, **kwargs)
        return vacancy_columns.parse_wide_table(
            _blocks(pdf), "c1", label_prefix=LABEL, pdf_path=pdf,
            definitions=self.definitions)

    def test_colunas_separadas_e_sem_colapso(self):
        result = self.parse([
            {"cargo": "Professor", "formacao": "Matemática",
             "escolaridade": "Nível Superior",
             "values": ["8", "1", "3", "1", "1", "0", "0", "14"]},
        ], total_row={"label": "TOTAL – DRE - BELEM",
                      "values": ["8", "1", "3", "1", "1", "0", "0", "14"]})
        fields = {item["field_name"]: json.loads(item["value_json"])
                  for item in result["proposals"]}
        self.assertEqual(fields["indigenous_vacancies"], 1)   # PI exclusiva
        self.assertEqual(fields["unified_ppiq_vacancies"], 0)  # unificada
        self.assertEqual(fields["unified_pi_pq_vacancies"], 0)
        self.assertEqual(fields["immediate_vacancies"], 14)
        self.assertEqual(result["regions"][0]["consistente"], True)

    def test_unificada_nao_vira_indigena_exclusiva(self):
        result = self.parse([
            {"cargo": "Professor", "formacao": "História",
             "escolaridade": "Nível Superior",
             "values": ["4", "1", "2", "0", "0", "1", "0", "8"]},
        ], total_row={"label": "TOTAL – DRE - BELEM",
                      "values": ["4", "1", "2", "0", "0", "1", "0", "8"]})
        fields = {item["field_name"]: json.loads(item["value_json"])
                  for item in result["proposals"]}
        self.assertEqual(fields["indigenous_vacancies"], 0)
        self.assertEqual(fields["unified_ppiq_vacancies"], 1)
        self.assertEqual(fields["immediate_vacancies"], 8)

    def test_soma_divergente_preserva_valores_e_registra_conflito(self):
        result = self.parse([
            {"cargo": "Professor", "formacao": "Artes",
             "escolaridade": "Nível Superior",
             "values": ["4", "1", "2", "0", "0", "0", "0", "9"]},
        ])
        self.assertTrue(any(item["field_name"] == "indigenous_vacancies"
                            for item in result["proposals"]))
        self.assertIn("conflito aritmetico",
                      result["proposals"][0]["ambiguity_reason"])
        self.assertEqual([p["causa"] for p in result["pendencias"]], ["soma_divergente"])

    def test_sigla_sem_definicao_nao_gera_proposta(self):
        pdf = _build_pdf([
            {"cargo": "Professor", "formacao": "Física",
             "escolaridade": "Nível Superior",
             "values": ["1", "0", "0", "0", "0", "0", "0", "1"]},
        ])
        result = vacancy_columns.parse_wide_table(
            _blocks(pdf), "c1", label_prefix=LABEL, pdf_path=pdf, definitions={})
        # O total publicado continua legível; as siglas sem definição não são interpretadas.
        self.assertEqual([item["field_name"] for item in result["proposals"]],
                         ["immediate_vacancies"])
        self.assertIn("sigla_sem_definicao",
                      [item["causa"] for item in result["pendencias"]])

    def test_sem_pdf_nao_le_quadro_largo(self):
        result = vacancy_columns.parse_wide_table(
            [{"block_id": "b", "page_number": 1, "locator": "página 1",
              "start_offset": 0, "end_offset": 5, "text": "texto"}],
            "c1", label_prefix=LABEL, pdf_path=None, definitions=self.definitions)
        self.assertEqual(result["proposals"], [])
        self.assertEqual(result["pendencias"][0]["causa"], "pdf_ausente")

    def test_evidencia_e_trecho_literal_do_bloco(self):
        pdf = _build_pdf([
            {"cargo": "Professor", "formacao": "Química",
             "escolaridade": "Nível Superior",
             "values": ["2", "0", "0", "0", "0", "1", "0", "3"]},
        ])
        blocks = _blocks(pdf)
        result = vacancy_columns.parse_wide_table(
            blocks, "c1", label_prefix=LABEL, pdf_path=pdf,
            definitions=self.definitions)
        for item in result["proposals"]:
            evidence = item["evidence"]
            block = blocks[evidence["block_index"]]
            self.assertEqual(block["text"][evidence["start_offset"]:
                                            evidence["end_offset"]],
                             evidence["quote"])
            self.assertIn("2 0 0 0 0 1 0 3", evidence["quote"])

    def test_regional_e_rotulo(self):
        result = self.parse([
            {"cargo": "Professor", "formacao": "Biologia",
             "escolaridade": "Nível Superior",
             "values": ["1", "0", "0", "0", "0", "0", "0", "1"]},
        ], total_row={"label": "TOTAL – DRE - ALTAMIRA",
                      "values": ["1", "0", "0", "0", "0", "0", "0", "1"]})
        self.assertEqual(result["regions"][0]["regiao"], "ALTAMIRA")
        self.assertIn("DRE ALTAMIRA", result["proposals"][0]["ambiguity_reason"])

    def test_travessao_no_cargo_nao_funde_escopos(self):
        # "Educação Especial - AEE" e "Educação Especial - LIBRAS" são cargos distintos;
        # o rótulo não pode conter " - " (o review trunca nesse separador).
        aee = vacancy_columns.compose_label("Professor", "Educação Especial - AEE",
                                            "DRE - BELÉM")
        libras = vacancy_columns.compose_label("Professor", "Educação Especial - LIBRAS",
                                               "DRE - BELÉM")
        for label in (aee, libras):
            self.assertNotIn(" - ", label)
        self.assertIn("AEE", aee)
        self.assertIn("LIBRAS", libras)
        self.assertNotEqual(aee, libras)
        # Cargo que transborda para a coluna de formação continua um só nome.
        merged = vacancy_columns.compose_label(
            "Analista de Gestão Governamental e", "Administração", "DRE - BELÉM")
        self.assertIn("Gestão Governamental e Administração", merged)

    def test_celula_com_marcador_de_zero(self):
        result = self.parse([
            {"cargo": "Professor", "formacao": "Filosofia",
             "escolaridade": "Nível Superior",
             "values": ["2", "0", "-", "0", "0", "1", "0", "3"]},
        ], total_row={"label": "TOTAL – DRE - BELEM",
                      "values": ["2", "0", "0", "0", "0", "1", "0", "3"]})
        fields = {item["field_name"]: json.loads(item["value_json"])
                  for item in result["proposals"]}
        self.assertEqual(fields["indigenous_vacancies"], 0)

    def test_linha_sem_primeira_coluna_nao_e_engolida(self):
        pdf = _build_pdf([
            {"cargo": "Professor", "formacao": "Química",
             "escolaridade": "Nível Superior",
             "values": ["", "0", "0", "0", "0", "1", "0", "1"]},
        ])
        result = vacancy_columns.parse_wide_table(
            _blocks(pdf), "c1", label_prefix=LABEL, pdf_path=pdf,
            definitions=self.definitions)
        # A linha é detectada (âncora em qualquer coluna) e fica pendente; o rótulo dela
        # não é absorvido por outra linha.
        self.assertEqual(result["proposals"], [])
        self.assertEqual([item["causa"] for item in result["pendencias"]],
                         ["celula_nao_numerica"])
        self.assertEqual(result["rows"], [])


class CrossPageTest(unittest.TestCase):
    """Linha cortada pela quebra de página: rótulo costurado, evidência na página certa."""

    def build(self):
        import pymupdf

        document = pymupdf.open()
        xs = [150, 240, 296, 357, 386, 414, 443, 471, 499, 527, 552]
        header = ("AC", "PcD", "PP", "PI", "PQ", "PPIQ", "PI/PQ", "Total")
        first = document.new_page(width=612, height=792)
        first.insert_text((20, 40), "ANEXO II - QUADRO DE VAGAS", fontsize=8)
        for x, text in zip(xs[:3], ["Cargo", "Formação", "Escolaridade"]):
            first.insert_text((x, 80), text, fontsize=7)
        for x, text in zip(xs[3:], header):
            first.insert_text((x, 80), text, fontsize=7)
        first.insert_text((150, 110), "Professor", fontsize=7)
        first.insert_text((240, 110), "Matemática", fontsize=7)
        first.insert_text((296, 110), "Nível", fontsize=7)
        first.insert_text((296, 121), "Superior", fontsize=7)
        for x, value in zip(xs[3:], ["1", "0", "0", "1", "0", "0", "0", "2"]):
            first.insert_text((x, 110), value, fontsize=7)
        # Linha cortada: escolaridade e o resto do nome continuam na página seguinte.
        first.insert_text((150, 140), "Especialista em", fontsize=7)
        first.insert_text((240, 140), "Especialista", fontsize=7)
        first.insert_text((296, 140), "Nível", fontsize=7)
        for x, value in zip(xs[3:], ["2", "1", "1", "0", "0", "0", "1", "5"]):
            first.insert_text((x, 140), value, fontsize=7)

        second = document.new_page(width=612, height=792)
        for x, text in zip(xs[:3], ["Cargo", "Formação", "Escolaridade"]):
            second.insert_text((x, 80), text, fontsize=7)
        for x, text in zip(xs[3:], header):
            second.insert_text((x, 80), text, fontsize=7)
        second.insert_text((150, 96), "Educação", fontsize=7)
        second.insert_text((240, 96), "em Educação", fontsize=7)
        second.insert_text((296, 96), "Superior", fontsize=7)
        second.insert_text((150, 130), "Professor", fontsize=7)
        second.insert_text((240, 130), "Física", fontsize=7)
        second.insert_text((296, 130), "Nível", fontsize=7)
        second.insert_text((296, 141), "Superior", fontsize=7)
        for x, value in zip(xs[3:], ["3", "0", "0", "0", "0", "1", "0", "4"]):
            second.insert_text((x, 130), value, fontsize=7)
        return document.tobytes()

    def test_rotulo_costurado_e_evidencia_na_pagina_do_numero(self):
        pdf = self.build()
        blocks = _blocks(pdf)
        result = vacancy_columns.parse_wide_table(
            blocks, "c1", label_prefix=LABEL, pdf_path=pdf,
            definitions=modality_legend.parse_definitions(LEGEND))
        labels = [item["ambiguity_reason"] for item in result["proposals"]]
        stitched = {label for label in labels if "completado" in label}
        self.assertEqual(len(stitched), 1)
        self.assertIn("Especialista em Educação", stitched.pop())
        # A evidência da linha costurada é da página 1 (onde estão os números).
        evidence = [item["evidence"] for item in result["proposals"]
                    if "completado" in item["ambiguity_reason"]][0]
        self.assertEqual(evidence["page_number"], 1)
        self.assertEqual(blocks[evidence["block_index"]]["text"]
                         [evidence["start_offset"]:evidence["end_offset"]],
                         evidence["quote"])
        # A linha seguinte não herdou a continuação.
        other = [label for label in labels if "Física" in label]
        self.assertEqual(len(other), 4)
        self.assertFalse(any("completado" in label for label in other))


class NotationTableTest(unittest.TestCase):
    TEXT = ("3. DOS REQUISITOS 3.1 A denominação do cargo e o número de vagas estão "
            "estabelecidos na tabela a seguir: QUADRO DE VAGAS Cargo Ampla concorrência "
            "Candidatos com deficiência Candidatos negros (pretos e pardos) Candidatos "
            "indígenas Candidatos quilombolas Total de vagas Juiz de Direito Substituto "
            "10+CR 1+CR 4+CR CR* CR* 15 + CR Total 15 3.2 O Concurso destina-se…")

    def blocks(self, text=None):
        return [{"block_id": "b1", "page_number": 3, "locator": "página 3",
                 "start_offset": 0, "end_offset": len(text or self.TEXT),
                 "text": text or self.TEXT}]

    def test_cr_asterisco_nao_vira_imediato_nem_zero(self):
        result = vacancy_columns.parse_notation_table(
            self.blocks(), "c1", label_prefix=LABEL)
        fields = [(item["field_name"], json.loads(item["value_json"]))
                  for item in result["proposals"]]
        self.assertIn(("immediate_vacancies", 15), fields)
        self.assertIn(("indigenous_reserve_notation", "CR*"), fields)
        self.assertNotIn("indigenous_vacancies", [name for name, _ in fields])
        self.assertIn("asterisco_sem_nota",
                      [item["causa"] for item in result["pendencias"]])

    def test_cr_asterisco_com_nota_nao_gera_pendencia(self):
        text = self.TEXT + (" * Vaga de cadastro de reserva destinada às pessoas "
                            "indígenas, conforme o item 1.2.2.")
        result = vacancy_columns.parse_notation_table(
            self.blocks(text), "c1", label_prefix=LABEL)
        self.assertNotIn("asterisco_sem_nota",
                         [item["causa"] for item in result["pendencias"]])
        self.assertIn(("indigenous_reserve_notation", "CR*"),
                      [(item["field_name"], json.loads(item["value_json"]))
                       for item in result["proposals"]])

    def test_soma_das_modalidades_confere_com_total(self):
        result = vacancy_columns.parse_notation_table(
            self.blocks(), "c1", label_prefix=LABEL)
        self.assertTrue(result["rows"][0]["consistente"])

    def test_percentual_no_corpo_nao_vira_quantidade(self):
        text = ("1.2.2 Das vagas estabelecidas, 3% (três por cento) são reservadas a "
                "indígenas. QUADRO DE VAGAS Cargo Ampla concorrência Candidatos com "
                "deficiência Candidatos negros Candidatos indígenas Candidatos "
                "quilombolas Total de vagas Juiz Substituto 10+CR 1+CR 4+CR CR CR 15 + CR")
        result = vacancy_columns.parse_notation_table(
            self.blocks(text), "c1", label_prefix=LABEL)
        values = [json.loads(item["value_json"]) for item in result["proposals"]
                  if item["field_name"] == "indigenous_vacancies"]
        self.assertEqual(values, [])  # nenhum número indígena inventado

    def test_cabecalho_incompleto_nao_desloca_colunas(self):
        # Sem a coluna PcD o alinhamento desloca: o valor de PP seria lido como PI.
        text = ("QUADRO DE VAGAS Cargo Ampla concorrência Candidatos negros (pretos e "
                "pardos) Candidatos indígenas Candidatos quilombolas Total de vagas "
                "Juiz Substituto 10+CR 4+CR CR* CR* 15 + CR")
        result = vacancy_columns.parse_notation_table(
            self.blocks(text), "c1", label_prefix=LABEL)
        self.assertEqual(result["proposals"], [])
        self.assertIn("cabecalho_incompleto",
                      [item["causa"] for item in result["pendencias"]])

    def test_zero_mais_cadastro_preserva_as_duas_informacoes(self):
        text = ("QUADRO DE VAGAS Cargo Ampla concorrência Candidatos com deficiência "
                "Candidatos negros (pretos e pardos) Candidatos indígenas Candidatos "
                "quilombolas Total de vagas Juiz Substituto 13+CR 1+CR 1+CR 0+CR 0+CR "
                "15 + CR")
        result = vacancy_columns.parse_notation_table(
            self.blocks(text), "c1", label_prefix=LABEL)
        fields = {item["field_name"]: json.loads(item["value_json"])
                  for item in result["proposals"]}
        self.assertEqual(fields["indigenous_vacancies"], 0)
        self.assertEqual(fields["indigenous_reserve_notation"], "0+CR")


class InlineDistributionTest(unittest.TestCase):
    TEXT = (
        "A Desembargadora, Presidente da Comissão, torna pública a abertura do Concurso "
        "Público para provimento de 30 (trinta) vagas no cargo de JUIZ DE DIREITO "
        "SUBSTITUTO, quantitativo que poderá ser ampliado. Do total de vagas anunciadas, "
        "serão reservados 5% (cinco por cento) às pessoas com deficiência, 25% (vinte e "
        "cinco por cento) aos negros, 3% (três por cento) aos indígenas e 2% (dois por "
        "cento) aos quilombolas, restando a seguinte distribuição: 19 (dezenove) vagas "
        "para ampla concorrência, 01 (uma) vaga para pessoas com deficiência, 08 (oito) "
        "vagas para negros, 1 (uma) vaga para indígenas e 1 (uma) vaga para quilombolas.")

    def blocks(self, text=None):
        text = text or self.TEXT
        return [{"block_id": "b1", "page_number": 1, "locator": "página 1",
                 "start_offset": 0, "end_offset": len(text), "text": text}]

    def test_quantidade_publicada_no_texto(self):
        result = vacancy_inline.extract_distribution(
            self.blocks(), "c1", label_prefix=LABEL)
        fields = {item["field_name"]: json.loads(item["value_json"])
                  for item in result["proposals"]}
        self.assertEqual(fields["immediate_vacancies"], 30)
        self.assertEqual(fields["indigenous_vacancies"], 1)
        self.assertTrue(result["rows"][0]["consistente"])

    def test_percentual_sem_quantidade_nao_gera_proposta(self):
        text = ("Abertura do Concurso para provimento de 30 (trinta) vagas no cargo de "
                "JUIZ DE DIREITO SUBSTITUTO. Serão reservados 3% (três por cento) aos "
                "indígenas.")
        result = vacancy_inline.extract_distribution(
            self.blocks(text), "c1", label_prefix=LABEL)
        self.assertEqual(result["proposals"], [])

    def test_sem_cargo_nao_associa_por_proximidade(self):
        text = self.TEXT.replace("no cargo de JUIZ DE DIREITO SUBSTITUTO", "neste certame")
        result = vacancy_inline.extract_distribution(
            self.blocks(text), "c1", label_prefix=LABEL)
        self.assertEqual(result["proposals"], [])

    def test_soma_divergente_registra_conflito(self):
        text = self.TEXT.replace("08 (oito) vagas para negros", "07 (sete) vagas para negros")
        result = vacancy_inline.extract_distribution(
            self.blocks(text), "c1", label_prefix=LABEL)
        self.assertEqual([item["causa"] for item in result["pendencias"]],
                         ["soma_divergente"])
        self.assertIn("conflito aritmetico",
                      result["proposals"][0]["ambiguity_reason"])

    def test_vaga_combinada_nao_e_exclusiva_indigena(self):
        text = self.TEXT.replace("1 (uma) vaga para indígenas",
                                 "1 (uma) vaga para indígenas e quilombolas")
        result = vacancy_inline.extract_distribution(
            self.blocks(text), "c1", label_prefix=LABEL)
        fields = [item["field_name"] for item in result["proposals"]]
        self.assertNotIn("indigenous_vacancies", fields)
        self.assertIn("modalidade_combinada",
                      [item["causa"] for item in result["pendencias"]])
        self.assertEqual(result["rows"][0]["combinadas"][0]["quantidade"], 1)

    def test_cadastro_de_reserva_no_trecho_nao_vira_imediato(self):
        text = self.TEXT.replace(
            "restando a seguinte distribuição:",
            "havendo cadastro de reserva, restando a seguinte distribuição:")
        result = vacancy_inline.extract_distribution(
            self.blocks(text), "c1", label_prefix=LABEL)
        fields = [item["field_name"] for item in result["proposals"]]
        self.assertNotIn("immediate_vacancies", fields)
        self.assertIn("cadastro_de_reserva_no_trecho",
                      [item["causa"] for item in result["pendencias"]])


class ReprocessTest(unittest.TestCase):
    def setUp(self):
        self.tmp, self.db = make_db()
        self.addCleanup(self.tmp.cleanup)

    def test_idempotente_e_sem_decisao_humana(self):
        from radar import reprocess
        _, version = add_document(self.db, "c1", text=InlineDistributionTest.TEXT)
        first = reprocess.reprocess_version(self.db, version, dry_run=True)
        self.assertGreater(first["novas"], 0)
        applied = reprocess.reprocess_version(self.db, version, dry_run=False)
        self.assertGreater(applied["gravadas"], 0)
        again = reprocess.reprocess_version(self.db, version, dry_run=False)
        self.assertEqual(again["novas"], 0)
        with closing(sqlite3.connect(self.db)) as conn:
            self.assertEqual(conn.execute(
                "SELECT COUNT(*) FROM revisoes_campo").fetchone()[0], 0)
            self.assertEqual(conn.execute(
                "SELECT COUNT(*) FROM valores_atuais").fetchone()[0], 0)
            # A mesma evidência não é duplicada.
            duplicates = conn.execute(
                "SELECT field_name, value_json, COUNT(*) FROM propostas_campo "
                "GROUP BY field_name, value_json HAVING COUNT(*) > 1").fetchall()
            self.assertEqual(duplicates, [])


class EligibilityIntegrationTest(unittest.TestCase):
    """A notação de reserva vira estado indígena sem virar vaga imediata."""

    def setUp(self):
        self.tmp, self.db = make_db()
        self.addCleanup(self.tmp.cleanup)

    def test_cr_asterisco_e_reserva_sem_quantidade(self):
        from radar import eligibility, reprocess
        _, version = add_document(self.db, "c1", text=NotationTableTest.TEXT)
        add_proposal(self.db, "c1", version_id=version, field="si_compatibility",
                     value="incompativel_com_requisito_explicito",
                     quote="Candidatos indígenas",
                     reason=LABEL + "Juiz de Direito Substituto")
        reprocess.reprocess_version(self.db, version, dry_run=False)
        report = eligibility.matrix(self.db, limit=200, now=NOON)
        rows = [item for item in report["itens"] if item["scope"]]
        self.assertTrue(rows)
        row = rows[0]
        self.assertEqual(row["indigenous"]["estado"], "reserva_sem_quantidade")
        self.assertEqual(row["eligibility"]["estado"], "incompativel_por_requisito")
        self.assertEqual(row["vacancies"]["indigenous_reserve"][0]["value"], "CR*")
        # Nenhuma vaga imediata indígena foi inventada.
        with closing(sqlite3.connect(self.db)) as conn:
            self.assertEqual(conn.execute(
                "SELECT COUNT(*) FROM propostas_campo "
                "WHERE field_name='indigenous_vacancies'").fetchone()[0], 0)

    def test_unificada_fica_separada_na_matriz(self):
        from radar import eligibility
        _, version = add_document(self.db, "c1", text="Tabela do cargo.")
        add_proposal(self.db, "c1", version_id=version, field="si_compatibility",
                     value="aceito_expressamente",
                     quote="Tabela do cargo.", reason=LABEL + "CARGO A")
        add_proposal(self.db, "c1", version_id=version,
                     field="unified_ppiq_vacancies", value=2,
                     quote="Tabela do cargo.", reason=LABEL + "CARGO A")
        add_proposal(self.db, "c1", version_id=version,
                     field="indigenous_vacancies", value=0,
                     quote="Tabela do cargo.", reason=LABEL + "CARGO A")
        report = eligibility.matrix(self.db, limit=200, now=NOON)
        row = [item for item in report["itens"] if item["scope"]][0]
        self.assertEqual(row["vacancies"]["unified"][0]["value"], 2)
        self.assertEqual(row["indigenous"]["estado"], "cargo_explicito_zero")


class ApiTest(unittest.TestCase):
    def setUp(self):
        import threading
        from radar.server import create_server
        self.tmp, self.db = make_db()
        self.addCleanup(self.tmp.cleanup)
        add_document(self.db, "c1", text=NotationTableTest.TEXT)
        self.server = create_server(self.db, host="127.0.0.1", port=0)
        threading.Thread(target=self.server.serve_forever, daemon=True).start()
        self.addCleanup(self.server.server_close)
        self.addCleanup(self.server.shutdown)
        self.port = self.server.server_address[1]

    def get(self, path):
        import http.client
        conn = http.client.HTTPConnection("127.0.0.1", self.port, timeout=10)
        conn.request("GET", path)
        response = conn.getresponse()
        data = response.read()
        conn.close()
        return response.status, data

    def test_quadro_vagas_somente_leitura(self):
        status, body = self.get("/api/quadro-vagas?contest_id=c1")
        self.assertEqual(status, 200)
        payload = json.loads(body)
        self.assertEqual(payload["contest_id"], "c1")
        for key in ("quadro_colunas", "quadro_notacao", "distribuicao_texto",
                    "propostas", "limitacao"):
            self.assertIn(key, payload)
        self.assertEqual(payload["quadro_notacao"]["rows"][0]["celulas"]["PI"], "CR*")

    def test_quadro_vagas_rejeita_parametro_desconhecido(self):
        status, _ = self.get("/api/quadro-vagas?contest_id=c1&x=1")
        self.assertEqual(status, 400)


if __name__ == "__main__":
    unittest.main()
