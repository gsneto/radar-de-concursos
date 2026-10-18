"""Elegibilidade por cargo, escopo indígena e quadro de vagas em texto (Fase 38)."""

import http.client
import json
import sqlite3
import threading
import unittest
from contextlib import closing

from radar import document_fields, eligibility
from radar.server import create_server
from tests.test_portfolio_f36 import NOON, add_document, add_proposal, make_db

LABEL = "cargo do documento não reconciliado: "


class Base(unittest.TestCase):
    def setUp(self):
        self.tmp, self.db = make_db()
        self.addCleanup(self.tmp.cleanup)

    def doc(self, contest="c1", **kwargs):
        return add_document(self.db, contest, **kwargs)

    def prop(self, contest="c1", *, version, field, value, quote, label="CARGO A"):
        return add_proposal(self.db, contest, version_id=version, field=field,
                            value=value, quote=quote, reason=LABEL + label)

    def matrix(self, **filters):
        return eligibility.matrix(self.db, limit=200, now=NOON, **filters)

    def row(self, contest="c1", label=None, **filters):
        rows = self.matrix(**filters)["itens"]
        for item in rows:
            if item["contest_id"] != contest:
                continue
            if label is None or (item.get("role_name") or "") == label:
                return item
        raise AssertionError(f"linha não encontrada: {contest} {label} {filters}")

    def counts(self):
        with closing(sqlite3.connect(self.db)) as conn:
            return conn.execute(
                "SELECT (SELECT COUNT(*) FROM revisoes_campo),"
                "(SELECT COUNT(*) FROM valores_atuais),"
                "(SELECT COUNT(*) FROM reconciliacoes_cargo),"
                "(SELECT COUNT(*) FROM revalidacoes_prazo)").fetchone()


class EligibilityStateTest(Base):
    def test_aceitacao_expressa_e_compativel(self):
        _, version = self.doc(text="Requisito do cargo.")
        self.prop(version=version, field="si_compatibility",
                  value="aceito_expressamente",
                  quote="curso superior em Sistemas de Informação")
        item = self.row()
        self.assertEqual(item["eligibility"]["estado"], "compativel_sem_vaga_indigena")
        self.assertEqual(item["si"]["estado"], "explicito")

    def test_categoria_sustentada_e_compativel(self):
        _, version = self.doc(text="Requisito do cargo.")
        self.prop(version=version, field="si_compatibility",
                  value="abrangido_por_categoria",
                  quote="curso superior na área de Tecnologia da Informação, tais como "
                        "Ciência da Computação e Engenharia da Computação")
        item = self.row()
        self.assertEqual(item["eligibility"]["estado"], "compativel_sem_vaga_indigena")
        self.assertEqual(item["si"]["estado"], "categoria_inclui_curso")

    def test_nome_do_curso_no_texto_vence_categoria(self):
        _, version = self.doc(text="Requisito do cargo.")
        self.prop(version=version, field="si_compatibility",
                  value="abrangido_por_categoria",
                  quote="curso superior na área de Tecnologia da Informação, tais como "
                        "Ciência da Computação e Sistemas de Informação")
        item = self.row()
        self.assertEqual(item["si"]["estado"], "explicito")

    def test_correlato_exige_interpretacao(self):
        _, version = self.doc(text="Requisito do cargo.")
        self.prop(version=version, field="si_compatibility", value="ambiguo",
                  quote="curso superior em área de computação")
        item = self.row()
        self.assertEqual(item["eligibility"]["estado"], "compativel_por_interpretacao")
        self.assertEqual(item["si"]["estado"], "area_correlata_interpretacao")

    def test_requisito_de_outra_formacao_e_incompativel(self):
        _, version = self.doc(text="Requisito do cargo.")
        self.prop(version=version, field="si_compatibility",
                  value="incompativel_com_requisito_explicito",
                  quote="curso de bacharelado em Direito")
        item = self.row()
        self.assertEqual(item["eligibility"]["estado"], "incompativel_por_requisito")
        self.assertEqual(item["si"]["estado"], "outras_formacoes")

    def test_ambiguo_sem_texto_de_formacao_nao_e_potencial(self):
        _, version = self.doc(text="Requisito do cargo.")
        self.prop(version=version, field="si_compatibility", value="ambiguo",
                  quote="Oficina de formação de membros para bancas")
        item = self.row()
        self.assertNotEqual(item["eligibility"]["estado"],
                            "compativel_por_interpretacao")
        self.assertEqual(item["si"]["estado"], "nao_encontrado")

    def test_conhecimentos_basicos_em_informatica_nao_e_formacao(self):
        _, version = self.doc(text="Requisito do cargo.")
        self.prop(version=version, field="si_compatibility", value="ambiguo",
                  quote="curso de nível médio e conhecimentos básicos em informática")
        item = self.row()
        self.assertNotEqual(item["eligibility"]["estado"],
                            "compativel_por_interpretacao")

    def test_dois_cargos_no_mesmo_concurso_nao_se_contaminam(self):
        _, version = self.doc(text="Requisito A. Requisito B.")
        self.prop(version=version, field="si_compatibility", value="aceito_expressamente",
                  quote="Requisito A.", label="ANALISTA DE TI")
        self.prop(version=version, field="si_compatibility",
                  value="incompativel_com_requisito_explicito",
                  quote="Requisito B.", label="MEDICO")
        rows = {item["role_name"]: item for item in self.matrix()["itens"]}
        self.assertEqual(rows["ANALISTA DE TI"]["eligibility"]["estado"],
                         "compativel_sem_vaga_indigena")
        self.assertEqual(rows["MEDICO"]["eligibility"]["estado"],
                         "incompativel_por_requisito")

    def test_cargo_sem_leitura_nao_herda_agregado(self):
        _, version = self.doc(text="Requisito A. Requisito B.")
        self.prop(version=version, field="si_compatibility", value="aceito_expressamente",
                  quote="Requisito A.", label="ANALISTA DE TI")
        self.prop(version=version, field="education", value="Superior",
                  quote="Requisito B.", label="MEDICO")
        rows = {item["role_name"]: item for item in self.matrix()["itens"]}
        self.assertEqual(rows["MEDICO"]["si"]["estado"], "nao_encontrado")
        self.assertNotEqual(rows["MEDICO"]["eligibility"]["estado"],
                            "compativel_sem_vaga_indigena")

    def test_identidade_pendente(self):
        _, version = self.doc(text="Requisito.")
        self.prop(version=version, field="education", value="Superior", quote="Requisito.")
        item = self.row()
        self.assertEqual(item["identity"], "pendente")
        self.assertEqual(item["eligibility"]["estado"], "identidade_pendente")

    def test_incompatibilidade_vence_identidade_pendente(self):
        _, version = self.doc(text="Requisito.")
        self.prop(version=version, field="si_compatibility",
                  value="incompativel_com_requisito_explicito",
                  quote="curso de bacharelado em Direito")
        item = self.row()
        self.assertEqual(item["identity"], "pendente")
        self.assertEqual(item["eligibility"]["estado"], "incompativel_por_requisito")


class IndigenousScopeTest(Base):
    def test_vaga_indigena_do_cargo(self):
        _, version = self.doc(text="Requisito.")
        self.prop(version=version, field="si_compatibility", value="aceito_expressamente",
                  quote="curso superior em Sistemas de Informação")
        self.prop(version=version, field="indigenous_vacancies", value=1,
                  quote="CARGO A 9 1 4 1 CR 15+ CR")
        item = self.row()
        self.assertEqual(item["indigenous"]["estado"], "cargo_imediata")
        self.assertEqual(item["indigenous"]["ambito"], "cargo")
        self.assertEqual(item["eligibility"]["estado"],
                         "compativel_com_vaga_indigena_cargo")

    def test_vaga_indigena_so_do_concurso_nao_e_do_cargo(self):
        _, version = self.doc(text="Requisito.")
        self.prop(version=version, field="si_compatibility", value="aceito_expressamente",
                  quote="curso superior em Sistemas de Informação")
        # Sem rótulo de cargo: escopo do concurso.
        add_proposal(self.db, "c1", version_id=version, field="indigenous_vacancies",
                     value=3, quote="quadro geral: 3 vagas indígenas")
        item = self.row(label="CARGO A")
        self.assertEqual(item["indigenous"]["estado"],
                         "concurso_imediata_sem_distribuicao")
        self.assertEqual(item["indigenous"]["ambito"], "concurso")
        self.assertNotEqual(item["eligibility"]["estado"],
                            "compativel_com_vaga_indigena_cargo")

    def test_reserva_do_cargo_sem_vaga_imediata(self):
        _, version = self.doc(text="Requisito.")
        self.prop(version=version, field="si_compatibility", value="aceito_expressamente",
                  quote="curso superior em Sistemas de Informação")
        self.prop(version=version, field="indigenous_vacancies", value=0,
                  quote="CARGO A 1 - - - - 25 2 10 1 1 40")
        self.prop(version=version, field="indigenous_reserve_vacancies", value=1,
                  quote="CARGO A 1 - - - - 25 2 10 1 1 40")
        item = self.row()
        self.assertEqual(item["indigenous"]["estado"],
                         "cargo_sem_imediata_com_reserva")
        self.assertEqual(item["eligibility"]["estado"], "compativel_sem_vaga_indigena")

    def test_cadastro_de_reserva_geral_nao_e_indigena(self):
        _, version = self.doc(text="Requisito.")
        self.prop(version=version, field="reserve_vacancies", value=39,
                  quote="cadastro de reserva 39")
        item = self.row()
        self.assertEqual(item["indigenous"]["estado"], "ausente_no_documento")

    def test_total_agregado_nao_vira_indigena(self):
        _, version = self.doc(text="Requisito.")
        self.prop(version=version, field="vagas_total_publicado", value=100,
                  quote="total de vagas 100")
        item = self.row()
        self.assertNotIn(item["indigenous"]["estado"], ("cargo_imediata",))
        self.assertEqual(item["vacancies"]["aggregate"][0]["value"], 100)

    def test_zero_explicito_do_cargo(self):
        _, version = self.doc(text="Requisito.")
        self.prop(version=version, field="indigenous_vacancies", value=0,
                  quote="CARGO A 1 0 0 0 0 1")
        item = self.row()
        self.assertEqual(item["indigenous"]["estado"], "cargo_explicito_zero")

    def test_linha_do_concurso_declara_distribuicao(self):
        _, version = self.doc(text="Requisito.")
        self.prop(version=version, field="indigenous_vacancies", value=1,
                  quote="CARGO A 9 1 4 1 CR 15+ CR")
        # Uma proposta de escopo do concurso garante a linha "(concurso)".
        add_proposal(self.db, "c1", version_id=version, field="education",
                     value="Superior", quote="Requisito.")
        rows = self.matrix()["itens"]
        contest_row = [item for item in rows if not item["scope"]][0]
        self.assertEqual(contest_row["indigenous"]["estado"], "distribuido_por_cargo")
        self.assertEqual(contest_row["indigenous"]["ambito"], "concurso")


class InlineTableTest(unittest.TestCase):
    TEXT = ("4. DAS VAGAS QUADRO DE VAGAS Cargo Ampla Concorrência Pessoa com Deficiência "
            "Negros Indígenas Quilombolas Total de vagas Juiz Substituto 9 1 4 1 CR 15+ CR "
            "5. DOS REQUISITOS BÁSICOS")

    def test_quadro_em_texto_por_cargo(self):
        blocks = [{"text": self.TEXT, "page_number": 4}]
        proposals = document_fields._inline_vacancy_proposals(blocks, "c1")
        values = {(p["field_name"], json.loads(p["value_json"])) for p in proposals}
        self.assertIn(("immediate_vacancies", 15), values)
        self.assertIn(("indigenous_vacancies", 1), values)
        self.assertTrue(all(p["ambiguity_reason"].endswith("Juiz Substituto")
                            for p in proposals))
        self.assertTrue(all(p["evidence"]["quote"] ==
                            "Juiz Substituto 9 1 4 1 CR 15+ CR" for p in proposals))

    def test_cr_nao_vira_zero_nem_imediata(self):
        text = ("QUADRO DE VAGAS Cargo Ampla Concorrência PcD Negros Indígenas "
                "Quilombolas Total de vagas Cargo X 1 0 0 CR 0 1 + CR")
        proposals = document_fields._inline_vacancy_proposals(
            [{"text": text, "page_number": 1}], "c1")
        indigenous = [p for p in proposals if p["field_name"] == "indigenous_vacancies"]
        self.assertEqual(indigenous, [])
        immediate = [p for p in proposals if p["field_name"] == "immediate_vacancies"]
        self.assertEqual(json.loads(immediate[0]["value_json"]), 1)

    def test_prosa_sem_quadro_nao_gera_vaga(self):
        text = ("O cargo de Analista exige formação superior. Indígenas e quilombolas "
                "têm reserva de 30% das vagas. Total de vagas: 15.")
        self.assertEqual(document_fields._inline_vacancy_proposals(
            [{"text": text, "page_number": 1}], "c1"), [])

    def test_numeracao_de_topicos_nao_e_quadro(self):
        text = ("ANEXO CONTEÚDO Cargo 1. Fundamentos da Cardiologia Pediátrica; "
                "2. Circulação fetal; 3. Epidemiologia; 4. Genética; 5. Avaliação; "
                "6. Sintomas; Ampla Concorrência Negros PcD Indígenas Quilombolas Total")
        self.assertEqual(document_fields._inline_vacancy_proposals(
            [{"text": text, "page_number": 1}], "c1"), [])


class TjscCaseTest(Base):
    """Teste obrigatório: TJSC Juiz Substituto 2026."""

    def setUp(self):
        super().setUp()
        self.doc_text = (
            "4. DAS VAGAS QUADRO DE VAGAS Cargo Ampla Concorrência Pessoa com Deficiência "
            "Negros Indígenas Quilombolas Total de vagas Juiz Substituto 9 1 4 1 CR 15+ CR "
            "5. DOS REQUISITOS BÁSICOS À INVESTIDURA DO CARGO 5.1 São requisitos para "
            "ingresso no cargo de Juiz Substituto: c) ter concluído o curso de bacharelado "
            "em Direito, em instituição reconhecida pelo MEC. "
            "9.1.2 As inscrições estarão abertas no período das 16h do dia 19 de outubro de "
            "2026 até às 16h do dia 26 de novembro de 2026.")
        self.document_id, self.version = add_document(self.db, "c1", text=self.doc_text,
                                                      published_at="2026-10-13")
        # Quadro de vagas extraído pelo parser inline (como no reprocessamento).
        for proposal in document_fields._inline_vacancy_proposals(
                [{"text": self.doc_text, "page_number": 4}], "c1"):
            add_proposal(self.db, "c1", version_id=self.version,
                         field=proposal["field_name"],
                         value=json.loads(proposal["value_json"]),
                         quote=proposal["evidence"]["quote"],
                         reason=proposal["ambiguity_reason"])
        # Requisito declarado no documento (rótulo de escolaridade, não de cargo).
        add_proposal(self.db, "c1", version_id=self.version,
                     field="si_compatibility",
                     value="incompativel_com_requisito_explicito",
                     quote="ter concluído o curso de bacharelado em Direito",
                     reason="cargo do documento não reconciliado: "
                            "escolaridade declarada (Nível Superior - Direito)")
        add_proposal(self.db, "c1", version_id=self.version, field="education",
                     value="Nível Superior - Direito",
                     quote="ter concluído o curso de bacharelado em Direito",
                     reason="cargo do documento não reconciliado: "
                            "escolaridade declarada (Nível Superior - Direito)")
        # Prazo de inscrição (extraído do texto).
        for field, value, quote, _start, _end in document_fields._registration_dates(
                self.doc_text):
            add_proposal(self.db, "c1", version_id=self.version, field=field,
                         value=value, quote=quote)

    def test_vaga_indigena_do_cargo_e_reconhecida(self):
        item = self.row(label="Juiz Substituto")
        self.assertEqual(item["indigenous"]["estado"], "cargo_imediata")
        self.assertEqual(item["indigenous"]["ambito"], "cargo")
        self.assertEqual(item["indigenous"]["evidencias"][0]["value"], 1)
        self.assertIsNotNone(item["indigenous"]["evidencias"][0]["page_number"])

    def test_reserva_nao_torna_o_cargo_compativel(self):
        item = self.row(label="Juiz Substituto")
        self.assertEqual(item["eligibility"]["estado"], "incompativel_por_requisito")
        self.assertEqual(item["si"]["estado"], "outras_formacoes")
        self.assertEqual(item["si"]["atribuicao"], "unico_cargo_do_concurso")

    def test_requisito_de_direito_aparece_na_evidencia(self):
        item = self.row(label="Juiz Substituto")
        quotes = " ".join(entry["quote"] or "" for entry in item["si"]["evidencias"])
        self.assertIn("bacharelado em Direito", quotes)

    def test_inicio_de_inscricao_nao_vem_da_isencao(self):
        item = self.row(label="Juiz Substituto")
        values = {entry["grupo"]: entry["valor"] for entry in item["temporal"]["prazos"]}
        self.assertEqual(values.get("inscricao_inicio"), "2026-10-19")
        self.assertEqual(values.get("inscricao_fim"), "2026-11-26")

    def test_tjsc_nao_entra_nos_destaques(self):
        highlights = eligibility.highlights(self.db, limit=12, now=NOON)
        self.assertEqual([item for item in highlights["itens"]
                          if item["contest_id"] == "c1"], [])

    def test_nenhuma_decisao_criada(self):
        eligibility.matrix(self.db, limit=10, now=NOON)
        eligibility.highlights(self.db, limit=10, now=NOON)
        self.assertEqual(self.counts(), (0, 0, 0, 0))


class HighlightTest(Base):
    def test_destaque_so_com_requisito_sustentado(self):
        _, version = self.doc(text="Requisito.")
        self.prop(version=version, field="si_compatibility", value="aceito_expressamente",
                  quote="curso superior em Sistemas de Informação")
        highlights = eligibility.highlights(self.db, limit=12, now=NOON)
        self.assertEqual(highlights["total"], 1)
        self.assertIn("requisito sustenta o perfil",
                      " ".join(highlights["itens"][0]["motivo_inclusao"]))

    def test_incompativel_nao_entra_mesmo_com_vaga_indigena(self):
        _, version = self.doc(text="Requisito.")
        self.prop(version=version, field="si_compatibility",
                  value="incompativel_com_requisito_explicito",
                  quote="curso de bacharelado em Direito")
        self.prop(version=version, field="indigenous_vacancies", value=1,
                  quote="CARGO A 9 1 4 1 CR 15+ CR")
        self.assertEqual(eligibility.highlights(self.db, limit=12, now=NOON)["total"], 0)

    def test_limite_de_dois_por_concurso(self):
        for index in range(3):
            _, version = add_document(self.db, "c1", tipo="edital_abertura",
                                      title=f"Edital {index}",
                                      published_at=f"2026-0{index + 1}-01",
                                      text="Requisito.")
            self.prop(version=version, field="si_compatibility",
                      value="aceito_expressamente",
                      quote="curso superior em Sistemas de Informação",
                      label=f"CARGO {index}")
        highlights = eligibility.highlights(self.db, limit=10, now=NOON)
        self.assertEqual(highlights["total"], 2)

    def test_paginacao_nao_perde_candidatos(self):
        for index in range(3):
            _, version = add_document(self.db, "c1", tipo="edital_abertura",
                                      title=f"Edital {index}",
                                      published_at=f"2026-0{index + 1}-01",
                                      text="Requisito.")
            add_proposal(self.db, "c1", version_id=version,
                         field="si_compatibility", value="aceito_expressamente",
                         quote="curso superior em Sistemas de Informação",
                         reason=LABEL + f"CARGO {index}")
        report = eligibility.matrix(self.db, limit=2, now=NOON)
        self.assertEqual(report["total"], 3)
        self.assertTrue(report["has_more"])
        second = eligibility.matrix(self.db, limit=2, offset=2, now=NOON)
        self.assertFalse(second["has_more"])


class ApiTest(Base):
    def setUp(self):
        super().setUp()
        _, version = self.doc(text="Requisito.")
        self.prop(version=version, field="si_compatibility", value="aceito_expressamente",
                  quote="curso superior em Sistemas de Informação")
        self.server = create_server(self.db, host="127.0.0.1", port=0)
        threading.Thread(target=self.server.serve_forever, daemon=True).start()
        self.addCleanup(self.server.server_close)
        self.addCleanup(self.server.shutdown)
        self.port = self.server.server_address[1]

    def get(self, path):
        conn = http.client.HTTPConnection("127.0.0.1", self.port, timeout=10)
        conn.request("GET", path)
        response = conn.getresponse()
        data = response.read()
        conn.close()
        return response.status, data

    def test_rotas(self):
        for path, key in (("/api/elegibilidade", "por_elegibilidade"),
                          ("/api/elegibilidade/destaques", "criterio")):
            status, body = self.get(path)
            self.assertEqual(status, 200, path)
            self.assertIn(key, json.loads(body))

    def test_filtros_invalidos(self):
        for path in ("/api/elegibilidade?eligibility=xyz",
                     "/api/elegibilidade?indigenous=xyz",
                     "/api/elegibilidade?temporal=xyz",
                     "/api/elegibilidade?identity=xyz",
                     "/api/elegibilidade?desconhecido=1"):
            status, _ = self.get(path)
            self.assertEqual(status, 400, path)

    def test_contrato_v1_preservado(self):
        status, body = self.get("/api/concursos")
        self.assertEqual(status, 200)
        payload = json.loads(body)
        items = payload if isinstance(payload, list) else payload.get("concursos", [])
        if items:
            self.assertEqual(len(items[0]), 18)


if __name__ == "__main__":
    unittest.main()
