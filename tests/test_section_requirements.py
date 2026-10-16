"""Requisitos por seção numerada: parsing, extração e associação por nome."""

import json
import tempfile
import unittest
from contextlib import closing
from pathlib import Path

from radar import section_requirements as sr
from radar.document_fields import LABEL_PREFIX
from radar.document_store import (connect_documents, ensure_observation,
                                  migrate_document_schema)

_TS = "2026-10-16T12:00:00+00:00"


def page(text, number=2):
    return dict(page_number=number, locator=f"página {number}", start_offset=0,
                end_offset=len(text), text=text)


# Seção sem código (modelo Valença): "3.2 NOME 3.2.1 Requisitos: ...".
NO_CODE = ("3 DOS CARGOS 3.1 PROFESSOR III 3.1.1 Requisitos: Diploma de curso de nível "
           "médio, fornecido por instituição reconhecida pelo MEC. 3.1.2 Remuneração: "
           "R$ 3.650,83 3.2 PROFESSOR IV – ARTE 3.2.1 Requisitos: Diploma de curso de "
           "nível superior de Licenciatura em Educação Artística. 3.2.2 Remuneração: "
           "R$ 4.468,62 3.3 PROFESSOR IV – MATEMÁTICA 3.3.1 Requisitos: Diploma de "
           "Licenciatura em Matemática. 3.3.2 Remuneração: R$ 4.468,62")


class ParseSectionsTest(unittest.TestCase):
    def test_splits_named_sections(self):
        heads = sr.parse_sections(NO_CODE)
        self.assertEqual([h["name"] for h in heads],
                         ["PROFESSOR III", "PROFESSOR IV – ARTE", "PROFESSOR IV – MATEMÁTICA"])
        self.assertTrue(all(h["code_clause"] is None for h in heads))

    def test_does_not_match_inside_subitem_number(self):
        # "3.1.4" não pode ser lido como seção "1.4".
        names = [h["name"] for h in sr.parse_sections(NO_CODE)]
        self.assertNotIn("4 Jornada de trabalho", names)

    def test_code_section_strips_code_from_name(self):
        text = ("2.4 ESPECIALISTA EM DESENVOLVIMENTO (EDAS) – ESPECIALIDADE: ADMINISTRAÇÃO "
                "(CARGO 400) 2.4.1 Descrição: planejar. 2.4.2 Requisitos: Diploma de "
                "graduação em Administração. 2.4.3 Remuneração: R$ 9.000,00")
        heads = sr.parse_sections(text)
        self.assertEqual(len(heads), 1)
        self.assertEqual(heads[0]["name"], "ESPECIALISTA EM DESENVOLVIMENTO (EDAS) – ESPECIALIDADE: ADMINISTRAÇÃO")
        self.assertEqual(heads[0]["code_clause"], "(CARGO 400)")


class SectionExtractionTest(unittest.TestCase):
    def test_extracts_education_per_section(self):
        props = sr.extract_section_education([page(NO_CODE, 2)], "c", label_prefix=LABEL_PREFIX)
        edu = [p for p in props if p["field_name"] == "education"]
        labels = sorted(p["ambiguity_reason"][len(LABEL_PREFIX):].split(" —")[0] for p in edu)
        self.assertEqual(labels, ["PROFESSOR III", "PROFESSOR IV – ARTE", "PROFESSOR IV – MATEMÁTICA"])
        values = {p["ambiguity_reason"][len(LABEL_PREFIX):]: json.loads(p["value_json"]) for p in edu}
        self.assertIn("Licenciatura em Matemática", values["PROFESSOR IV – MATEMÁTICA"])
        self.assertNotIn("Remuneração", values["PROFESSOR IV – MATEMÁTICA"])

    def test_evidence_quote_matches_block(self):
        block = page(NO_CODE, 2)
        props = sr.extract_section_education([block], "c", label_prefix=LABEL_PREFIX)
        for p in props:
            ev = p["evidence"]
            self.assertEqual(block["text"][ev["start_offset"]:ev["end_offset"]], ev["quote"])

    def test_code_section_emits_code_label(self):
        text = ("2.4 CARGO ADMINISTRATIVO (CARGO 400) 2.4.1 Descrição: x. "
                "2.4.2 Requisitos: Diploma de Administração. 2.4.3 Remuneração: R$ 1")
        props = sr.extract_section_education([page(text, 2)], "c", label_prefix=LABEL_PREFIX)
        edu = [p for p in props if p["field_name"] == "education"][0]
        self.assertTrue(edu["ambiguity_reason"].startswith(LABEL_PREFIX + "400"))

    def test_uppercase_requisitos_is_extracted(self):
        # Regressão: gate não pode ser sensível a maiúsculas.
        text = ("3.2 PROFESSOR IV – ARTE 3.2.1 REQUISITOS: Diploma de Licenciatura em "
                "Educação Artística. 3.2.2 Remuneração: R$ 1")
        props = sr.extract_section_education([page(text, 2)], "c", label_prefix=LABEL_PREFIX)
        self.assertEqual(len([p for p in props if p["field_name"] == "education"]), 1)

    def test_si_classification_per_section(self):
        text = ("3.5 ANALISTA DE TI 3.5.1 Requisitos: Diploma de graduação na área de "
                "Tecnologia da Informação, tais como Ciência da Computação, Sistemas de "
                "Informação ou outros correlatos. 3.5.2 Remuneração: R$ 1")
        props = sr.extract_section_education([page(text, 2)], "c", label_prefix=LABEL_PREFIX)
        si = [p for p in props if p["field_name"] == "si_compatibility"][0]
        self.assertEqual(json.loads(si["value_json"]), "aceito_expressamente")

    def test_no_requisitos_item_no_proposal(self):
        text = ("3.1 PROFESSOR X 3.1.1 Descrição: dar aulas. 3.1.2 Remuneração: R$ 1 "
                "3.2 PROFESSOR Y 3.2.1 Descrição: dar aulas. 3.2.2 Remuneração: R$ 1")
        self.assertEqual(sr.extract_section_education([page(text, 2)], "c", label_prefix=LABEL_PREFIX), [])


class ReconcileByNameTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.db = str(Path(self.tmp.name) / "db.sqlite3")
        migrate_document_schema(self.db)
        self.obs = ensure_observation(self.db, "https://www.quadrix.org.br/informacoes/1/", "quadrix-1")
        with closing(connect_documents(self.db)) as conn:
            self.contest = conn.execute("SELECT contest_id FROM observacoes_concurso WHERE id=?",
                                        (self.obs,)).fetchone()[0]

    def _proposal(self, label, field="education"):
        return {"contest_id": self.contest, "role_id": None, "field_name": field,
                "value_json": '"x"', "value_type": "string", "extraction_method": "t",
                "ambiguity_reason": LABEL_PREFIX + label, "evidence": {}}

    def _table(self, *rows):
        return [{"code": c, "name": n, "education": e} for c, n, e in rows]

    def test_exact_unique_name_is_explicit(self):
        table = self._table(("400", "Professor IV - Arte", "Superior"))
        proposals = [self._proposal("PROFESSOR IV – ARTE")]
        result = sr.reconcile_sections_by_name(self.db, self.contest, self.obs, table, proposals)
        self.assertEqual(result["explicita"], 1)
        self.assertEqual(result["assigned"], 1)
        self.assertIsNotNone(proposals[0]["role_id"])

    def test_em_dash_in_name_is_not_truncated(self):
        # Regressão: travessão em (—) no nome do cargo não pode truncar e associar ao errado.
        table = self._table(("100", "PROFESSOR", "Superior"),
                            ("101", "PROFESSOR — ARTE", "Superior"))
        proposals = [self._proposal("PROFESSOR — ARTE")]
        result = sr.reconcile_sections_by_name(self.db, self.contest, self.obs, table, proposals)
        self.assertEqual(result["explicita"], 1)
        with closing(connect_documents(self.db)) as conn:
            code = conn.execute("SELECT code FROM cargos_identidade WHERE id=?",
                                (proposals[0]["role_id"],)).fetchone()[0]
        self.assertEqual(code, "101")  # associou ao cargo certo, não ao 100

    def test_identity_conflict_does_not_abort(self):
        # Regressão: conflito de identidade na camada por nome não pode abortar o lote.
        from radar.document_store import ensure_role
        ensure_role(self.db, self.contest, self.obs, "ALFA", code="400")
        table = self._table(("400", "BETA GAMMA", "Superior"))
        proposals = [self._proposal("BETA GAMMA")]
        result = sr.reconcile_sections_by_name(self.db, self.contest, self.obs, table, proposals)
        self.assertEqual(result["ambigua"], 1)
        self.assertIsNone(proposals[0]["role_id"])

    def test_duplicate_name_is_ambiguous(self):
        table = self._table(("100", "Assistente Social Escolar", "Superior"),
                            ("101", "Assistente Social Escolar", "Superior"))
        proposals = [self._proposal("ASSISTENTE SOCIAL ESCOLAR")]
        result = sr.reconcile_sections_by_name(self.db, self.contest, self.obs, table, proposals)
        self.assertEqual(result["ambigua"], 1)
        self.assertIsNone(proposals[0]["role_id"])

    def test_no_match_is_sem_cargo(self):
        table = self._table(("400", "Professor de Física", "Superior"))
        proposals = [self._proposal("MERENDEIRO ESCOLAR")]
        result = sr.reconcile_sections_by_name(self.db, self.contest, self.obs, table, proposals)
        self.assertEqual(result["sem_cargo"], 1)
        self.assertIsNone(proposals[0]["role_id"])

    def test_partial_match_is_revisao_not_assigned(self):
        table = self._table(("400", "Professor IV - Arte", "Superior"))
        proposals = [self._proposal("PROFESSOR IV - ARTES VISUAIS")]
        result = sr.reconcile_sections_by_name(self.db, self.contest, self.obs, table, proposals)
        self.assertEqual(result["revisao"], 1)
        self.assertIsNone(proposals[0]["role_id"])  # não associa sem igualdade

    def test_code_label_is_left_to_code_flow(self):
        table = self._table(("400", "Professor", "Superior"))
        proposals = [self._proposal("400 PROFESSOR")]
        result = sr.reconcile_sections_by_name(self.db, self.contest, self.obs, table, proposals)
        self.assertEqual(result["assigned"], 0)
        self.assertEqual(sum(result[k] for k in ("explicita", "sustentada", "revisao", "ambigua", "sem_cargo")), 0)

    def test_schooling_alone_does_not_associate(self):
        # Duas cargas de nível superior com nomes distintos: nada é associado por escolaridade.
        table = self._table(("400", "Professor de Física", "Superior"),
                            ("401", "Professor de Química", "Superior"))
        proposals = [self._proposal("CARGO INEXISTENTE")]
        result = sr.reconcile_sections_by_name(self.db, self.contest, self.obs, table, proposals)
        self.assertEqual(result["sem_cargo"], 1)
        self.assertEqual(result["assigned"], 0)

    def test_idempotent_reassignment_skips_assigned(self):
        table = self._table(("400", "Professor IV - Arte", "Superior"))
        proposals = [self._proposal("PROFESSOR IV – ARTE")]
        sr.reconcile_sections_by_name(self.db, self.contest, self.obs, table, proposals)
        second = sr.reconcile_sections_by_name(self.db, self.contest, self.obs, table, proposals)
        self.assertEqual(second["assigned"], 0)  # já associado


class IntegrationTest(unittest.TestCase):
    """Integração com o pipeline de propostas (não regride isenção nem vagas)."""

    def test_pipeline_includes_section_education_and_exemption(self):
        from radar.document_fields import extract_field_proposals
        text = ("3 DOS CARGOS 3.2 PROFESSOR IV – ARTE 3.2.1 Requisitos: Diploma de "
                "Licenciatura em Educação Artística. 3.2.2 Remuneração: R$ 4.468,62 "
                "ANEXO I CRONOGRAMA 3 Período para solicitação de isenção do valor da "
                "inscrição 21 e 22/09/2026 4 Divulgação do resultado preliminar da "
                "solicitação de isenção 07/10/2026")
        props = extract_field_proposals([page(text, 2)], "v", "c")
        fields = {p["field_name"] for p in props}
        self.assertIn("education", fields)           # seção sem código
        self.assertIn("si_compatibility", fields)
        self.assertIn("exemption_start", fields)     # isenção preservada
        self.assertIn("exemption_end", fields)
        edu = [p for p in props if p["field_name"] == "education"][0]
        self.assertIn("Educação Artística", json.loads(edu["value_json"]))
        # A isenção não foi capturada como requisito de formação.
        self.assertNotIn("isenção", json.loads(edu["value_json"]).lower())


class CrossPageTest(unittest.TestCase):
    """Reconstrução do contexto entre páginas adjacentes (Fase 17)."""

    def test_header_at_end_of_page_requisites_on_next(self):
        # Cabeçalho no fim da p3; subitem Requisitos na p4.
        p3 = page("...atividades do setor. 3.2 PROFESSOR IV – ARTE 3.2.1 Descrição: dar "
                  "aulas de arte; 3.2.2 Detalhada: planejar.", 3)
        p4 = page("3.2.3 Requisitos: Diploma de Licenciatura em Educação Artística. "
                  "3.2.4 Remuneração: R$ 4.468,62 3.3 PROFESSOR IV – MATEMÁTICA "
                  "3.3.1 Requisitos: Diploma de Licenciatura em Matemática.", 4)
        props = sr.extract_section_education([p3, p4], "c", label_prefix=LABEL_PREFIX)
        edu = [p for p in props if p["field_name"] == "education"]
        labels = {p["ambiguity_reason"][len(LABEL_PREFIX):].split(" —")[0] for p in edu}
        self.assertIn("PROFESSOR IV – ARTE", labels)
        self.assertIn("PROFESSOR IV – MATEMÁTICA", labels)

    def test_evidence_points_to_page_of_requisites(self):
        p3 = page("3.2 PROFESSOR IV – ARTE 3.2.1 Descrição: x;", 3)
        p4 = page("3.2.3 Requisitos: Diploma de Licenciatura em Educação Artística. "
                  "3.2.4 Remuneração: R$ 1", 4)
        props = sr.extract_section_education([p3, p4], "c", label_prefix=LABEL_PREFIX)
        edu = [p for p in props if p["field_name"] == "education"][0]
        self.assertEqual(edu["evidence"]["page_number"], 4)  # onde o requisito aparece
        self.assertIn("Educação Artística", json.loads(edu["value_json"]))
        block = p4
        ev = edu["evidence"]
        self.assertEqual(block["text"][ev["start_offset"]:ev["end_offset"]], ev["quote"])

    def test_value_crossing_page_is_truncated_and_flagged(self):
        p3 = page("3.5 CARGO X 3.5.1 Requisitos: Diploma de graduação em Administração e "
                  "curso complementar de", 3)
        p4 = page("especialização reconhecido pelo MEC. 3.5.2 Remuneração: R$ 1", 4)
        props = sr.extract_section_education([p3, p4], "c", label_prefix=LABEL_PREFIX)
        edu = [p for p in props if p["field_name"] == "education"][0]
        self.assertIn("continua na página seguinte", edu["ambiguity_reason"])
        self.assertEqual(edu["evidence"]["page_number"], 3)
        block = p3
        ev = edu["evidence"]
        self.assertEqual(block["text"][ev["start_offset"]:ev["end_offset"]], ev["quote"])

    def test_no_false_bridge_across_distant_cross_reference(self):
        # "1.2" citado como referência cruzada longe do seu suposto "1.2.3" não pode
        # engolir a seção real 3.2 que está no meio.
        p = page("conforme o subitem 1.2 deste edital ... "
                 "3.2 PROFESSOR IV – ARTE 3.2.1 Requisitos: Diploma em Arte. 3.2.2 x "
                 "... o item 1.2.3 deste edital.", 2)
        props = sr.extract_section_education([p], "c", label_prefix=LABEL_PREFIX)
        labels = {x["ambiguity_reason"][len(LABEL_PREFIX):].split(" —")[0]
                  for x in props if x["field_name"] == "education"}
        self.assertEqual(labels, {"PROFESSOR IV – ARTE"})

    def test_repeated_footer_not_attached(self):
        # Rodapé/cabeçalho repetido no topo da página seguinte não vira requisito.
        p3 = page("3.2 PROFESSOR IV – ARTE 3.2.1 Requisitos: Diploma em Arte.", 3)
        p4 = page("TRIBUNAL DE JUSTIÇA | CONCURSO PÚBLICO 2026 4 3.3 OUTRO CARGO "
                  "3.3.1 Requisitos: Diploma em Outra Coisa.", 4)
        props = sr.extract_section_education([p3, p4], "c", label_prefix=LABEL_PREFIX)
        for p in props:
            self.assertNotIn("TRIBUNAL", json.loads(p["value_json"]))

    def test_new_section_ends_previous_scope(self):
        p = page("3.2 PROFESSOR IV – ARTE 3.2.1 Requisitos: Diploma em Arte. "
                 "3.3 PROFESSOR IV – FÍSICA 3.3.1 Requisitos: Diploma em Física.", 2)
        props = sr.extract_section_education([p], "c", label_prefix=LABEL_PREFIX)
        values = {p["ambiguity_reason"][len(LABEL_PREFIX):].split(" —")[0]: json.loads(p["value_json"])
                  for p in props if p["field_name"] == "education"}
        self.assertIn("Arte", values["PROFESSOR IV – ARTE"])
        self.assertNotIn("Física", values["PROFESSOR IV – ARTE"])

    def test_programmatic_content_across_pages_is_not_requirements(self):
        p3 = page("18 CONTEÚDO PROGRAMÁTICO 18.1 CARGO X 18.1.1 Noções de Direito.", 30)
        p4 = page("18.1.2 Noções de Contabilidade. 18.1.3 Administração.", 31)
        self.assertEqual(sr.extract_section_education([p3, p4], "c", label_prefix=LABEL_PREFIX), [])

    def test_number_mid_sentence_is_not_a_section(self):
        # Regressão: "3.2 reais" no meio de uma frase não é cabeçalho de seção.
        p1 = page("O valor da taxa e 3.2 reais por candidato.", 1)
        p2 = page("3.2.1 Requisitos: Diploma em Contabilidade. 3.2.2 Remuneração: R$ 1", 2)
        self.assertEqual(sr.extract_section_education([p1, p2], "c", label_prefix=LABEL_PREFIX), [])

    def test_html_blocks_are_not_used_for_section_requirements(self):
        # Regressão: blocos sem página (HTML) não entram no documento lógico de páginas.
        html_block = dict(page_number=None, locator="linha de tabela", start_offset=0,
                          end_offset=60, text="3.2 PROFESSOR IV – ARTE 3.2.1 Requisitos: Diploma em Arte.")
        self.assertEqual(sr.extract_section_education([html_block], "c", label_prefix=LABEL_PREFIX), [])

    def test_evidence_block_index_maps_to_original_list(self):
        # Bloco sem página antes de blocos de página: o índice da evidência é o da lista ORIGINAL.
        html_block = dict(page_number=None, locator="linha", start_offset=0, end_offset=3, text="xyz")
        p1 = page("3.2 PROFESSOR IV – ARTE 3.2.1 Descrição: x;", 1)
        p2 = page("3.2.3 Requisitos: Diploma em Educação Artística. 3.2.4 R$ 1", 2)
        blocks = [html_block, p1, p2]
        props = sr.extract_section_education(blocks, "c", label_prefix=LABEL_PREFIX)
        edu = [p for p in props if p["field_name"] == "education"][0]
        idx = edu["evidence"]["block_index"]
        self.assertEqual(idx, 2)  # bloco original p2, não o índice 1 de page_blocks
        ev = edu["evidence"]
        self.assertEqual(blocks[idx]["text"][ev["start_offset"]:ev["end_offset"]], ev["quote"])


class LogicalDocumentTest(unittest.TestCase):
    def test_build_logical_document_maps_offsets(self):
        blocks = [page("abc", 1), page("de", 2), page("f", 3)]
        text, spans = sr.build_logical_document(blocks)
        self.assertEqual(text, "abc\nde\nf")
        self.assertEqual(spans[0], {"block_index": 0, "page_number": 1, "start": 0, "end": 3})
        self.assertEqual(spans[1], {"block_index": 1, "page_number": 2, "start": 4, "end": 6})
        self.assertEqual(spans[2], {"block_index": 2, "page_number": 3, "start": 7, "end": 8})
        # span_at localiza o bloco pelo offset
        self.assertEqual(sr._span_at(spans, 5)["block_index"], 1)

    def test_clean_label_uses_earliest_annotation(self):
        from radar.role_reconciliation import _clean_label
        label = "PROFESSOR IV – HISTÓRIA — continua na página seguinte — requisitos presentes"
        self.assertEqual(_clean_label(label), "PROFESSOR IV – HISTÓRIA")


if __name__ == "__main__":
    unittest.main()
