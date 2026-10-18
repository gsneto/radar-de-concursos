"""Reconciliação por código, escolaridade mínima e elegibilidade formal (Fase 39)."""

import http.client
import json
import sqlite3
import threading
import unittest
from contextlib import closing

from radar import edital_requirements, eligibility, quadrix_tables, reprocess
from radar.server import create_server
from tests.test_portfolio_f36 import NOON, add_document, add_proposal, make_db

LABEL = "cargo do documento não reconciliado: "

MEDIO_SEM_AREA = ("Diploma ou certificado, devidamente registrado, de conclusão de curso de "
                  "nível médio, fornecido por instituição de ensino reconhecida pelo "
                  "Ministério da Educação (MEC).")
SUPERIOR_SEM_AREA = ("Diploma de curso de nível superior, devidamente registrado, em "
                     "qualquer área de formação.")
TECNICO_INFORMATICA = (MEDIO_SEM_AREA + " Curso técnico em Informática, Tecnologia da "
                       "Informação, Redes de Computadores ou área correlata, ou experiência "
                       "comprovada de 6 meses na área de Tecnologia da Informação.")
TECNICO_DESIGN = (MEDIO_SEM_AREA + " Curso técnico em Design Gráfico, Comunicação Visual, "
                  "Produção Multimídia, área correlata.")
SUPERIOR_TI = ("Diploma de conclusão de curso de graduação de nível superior nas áreas de "
               "Tecnologia da Informação ou Ciências da Computação, ou curso de denominação "
               "e conteúdo equivalentes, em grau de bacharel ou tecnólogo.")
SUPERIOR_DIREITO = ("Diploma de conclusão de curso de graduação de nível superior em "
                    "Direito, fornecido por instituição reconhecida pelo MEC. Registro ativo "
                    "na OAB.")


class ClassificationTest(unittest.TestCase):
    def test_ensino_medio_e_nivel_minimo(self):
        self.assertEqual(edital_requirements.classify_si_compatibility(MEDIO_SEM_AREA)[0],
                         "nivel_minimo_sem_area")
        self.assertEqual(edital_requirements.education_level(MEDIO_SEM_AREA), "medio")
        self.assertFalse(edital_requirements.names_specific_area(MEDIO_SEM_AREA))

    def test_superior_sem_area_e_nivel_minimo(self):
        self.assertEqual(edital_requirements.classify_si_compatibility(SUPERIOR_SEM_AREA)[0],
                         "nivel_minimo_sem_area")
        self.assertEqual(edital_requirements.education_level(SUPERIOR_SEM_AREA), "superior")

    def test_curso_tecnico_de_ti_e_ambiguo_por_nivel(self):
        state, reason = edital_requirements.classify_si_compatibility(TECNICO_INFORMATICA)
        self.assertEqual(state, "ambiguo")
        self.assertIn("nível", reason)

    def test_curso_tecnico_de_outra_area_e_especifico(self):
        self.assertEqual(
            edital_requirements.classify_si_compatibility(TECNICO_DESIGN)[0],
            "incompativel_com_requisito_explicito")

    def test_categoria_formal_abrangente(self):
        self.assertEqual(edital_requirements.classify_si_compatibility(SUPERIOR_TI)[0],
                         "abrangido_por_categoria")

    def test_graduacao_especifica_diferente(self):
        self.assertEqual(
            edital_requirements.classify_si_compatibility(SUPERIOR_DIREITO)[0],
            "incompativel_com_requisito_explicito")

    def test_si_expresso(self):
        text = SUPERIOR_TI.replace("Ciências da Computação",
                                   "Ciências da Computação, Sistemas de Informação")
        self.assertEqual(edital_requirements.classify_si_compatibility(text)[0],
                         "aceito_expressamente")

    def test_area_de_nao_e_abertura(self):
        text = "curso superior em área de computação"
        self.assertEqual(edital_requirements.classify_si_compatibility(text)[0], "ambiguo")

    def test_direito_de_dirigir_nao_e_formacao(self):
        text = (MEDIO_SEM_AREA + " Carteira Nacional de Habilitação, válida e regular, sem "
                "impedimentos que restrinjam o exercício do direito de dirigir.")
        self.assertEqual(edital_requirements.classify_si_compatibility(text)[0],
                         "nivel_minimo_sem_area")

    def test_quadro_compacto_nivel_superior_direito(self):
        self.assertEqual(edital_requirements.area_clause("Nível Superior - Direito"),
                         "Direito")
        self.assertEqual(
            edital_requirements.classify_si_compatibility("Nível Superior - Direito")[0],
            "incompativel_com_requisito_explicito")

    def test_qualquer_area_nao_e_area_especifica(self):
        self.assertIsNone(edital_requirements.area_clause(
            "curso superior em qualquer área de formação"))


class LicenciaturaTest(unittest.TestCase):
    PLENA = ("Licenciatura Plena com habilitação para o magistério na Educação Infantil e "
             "nos anos iniciais do Ensino Fundamental.")
    AREA = ("Curso em nível superior completo de licenciatura, de graduação plena, na área "
            "de atuação a que concorre.")

    def test_licenciatura_plena_nao_e_nivel_minimo(self):
        self.assertEqual(edital_requirements.classify_si_compatibility(self.PLENA)[0],
                         "incompativel_com_requisito_explicito")
        self.assertTrue(edital_requirements.names_specific_area(self.PLENA))

    def test_licenciatura_por_area_de_atuacao_nao_e_nivel_minimo(self):
        self.assertEqual(edital_requirements.classify_si_compatibility(self.AREA)[0],
                         "incompativel_com_requisito_explicito")

    def test_licenciatura_em_qualquer_area_continua_nivel_minimo(self):
        text = "curso de licenciatura em qualquer área"
        self.assertEqual(edital_requirements.classify_si_compatibility(text)[0],
                         "nivel_minimo_sem_area")


class Base(unittest.TestCase):
    def setUp(self):
        self.tmp, self.db = make_db()
        self.addCleanup(self.tmp.cleanup)

    def doc(self, contest="c1", **kwargs):
        return add_document(self.db, contest, **kwargs)

    def prop(self, contest="c1", *, version, field, value, quote, label):
        return add_proposal(self.db, contest, version_id=version, field=field,
                            value=value, quote=quote, reason=LABEL + label)

    def matrix(self, **filters):
        return eligibility.matrix(self.db, limit=200, now=NOON, **filters)

    def row(self, contest="c1", label=None, **filters):
        for item in self.matrix(**filters)["itens"]:
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
                "(SELECT COUNT(*) FROM reconciliacoes_cargo)").fetchone()


class CodeJoinTest(Base):
    def test_leitura_do_codigo_vai_para_o_cargo_nomeado(self):
        _, version = self.doc(text="Requisito.")
        # Leitura pendurada no rótulo só-código.
        add_proposal(self.db, "c1", version_id=version, field="si_compatibility",
                     value="ambiguo", quote=MEDIO_SEM_AREA, reason=LABEL + "200")
        add_proposal(self.db, "c1", version_id=version, field="education",
                     value="Nível médio", quote=MEDIO_SEM_AREA, reason=LABEL + "200")
        self.prop(version=version, field="immediate_vacancies", value=1,
                  quote="200 CARGO A 1", label="200 CARGO A")
        item = self.row(label="200 CARGO A")
        self.assertEqual(item["si"]["estado"], "nivel_minimo")
        self.assertEqual(item["si"]["atribuicao"], "codigo_do_cargo")
        self.assertEqual(item["eligibility"]["estado"], "compativel_por_nivel_minimo")

    def test_codigo_ambiguo_nao_e_usado(self):
        _, version = self.doc(text="Requisito.")
        add_proposal(self.db, "c1", version_id=version, field="si_compatibility",
                     value="ambiguo", quote=MEDIO_SEM_AREA, reason=LABEL + "200")
        # Dois cargos nomeados com o mesmo código: junção não é segura.
        self.prop(version=version, field="immediate_vacancies", value=1,
                  quote="200 CARGO A 1", label="200 CARGO A")
        self.prop(version=version, field="education", value="Superior",
                  quote="200 CARGO B 1", label="200 CARGO B")
        for label in ("200 CARGO A", "200 CARGO B"):
            item = self.row(label=label)
            self.assertNotEqual(item["si"]["atribuicao"], "codigo_do_cargo")

    def test_codigo_de_outro_concurso_nao_e_usado(self):
        _, version = self.doc("c1", text="Requisito.")
        add_proposal(self.db, "c1", version_id=version, field="si_compatibility",
                     value="ambiguo", quote=MEDIO_SEM_AREA, reason=LABEL + "200")
        self.prop("c1", version=version, field="education", value="Superior",
                  quote="200 CARGO A 1", label="200 CARGO A")
        _, other = self.doc("c2", text="Requisito.")
        # No concurso 2 o código 200 exige Direito: a leitura de c1 não pode vazar.
        add_proposal(self.db, "c2", version_id=other, field="si_compatibility",
                     value="incompativel_com_requisito_explicito",
                     quote=SUPERIOR_DIREITO, reason=LABEL + "200")
        add_proposal(self.db, "c2", version_id=other, field="education",
                     value="Superior", quote="200 CARGO Z", reason=LABEL + "200 CARGO Z")
        item = self.row(contest="c2", label="200 CARGO Z")
        self.assertEqual(item["si"]["estado"], "outras_formacoes")
        self.assertEqual(item["eligibility"]["estado"], "incompativel_por_requisito")


class FamilyAndLocalityTest(Base):
    def test_mesmo_titulo_em_localidades_distintas(self):
        _, version = self.doc(text="Requisito.")
        for code, city in (("200", "Cachoeiro de Itapemirim"), ("201", "Colatina"),
                           ("202", "Guarapari")):
            self.prop(version=version, field="immediate_vacancies", value=1,
                      quote=f"{code} Assistente Administrativo 1", label=(
                          f"{code} Assistente Administrativo"))
            self.prop(version=version, field="vaga_municipio", value=city,
                      quote=f"{code} Assistente Administrativo 1 {city}",
                      label=f"{code} Assistente Administrativo")
        report = self.matrix()
        rows = {item["role_name"]: item for item in report["itens"]}
        self.assertEqual(len([name for name in rows
                              if "Assistente Administrativo" in name]), 3)
        localities = {item["cargo"]["localidade"]["valor"]
                      for item in report["itens"]
                      if item["cargo"]["localidade"]}
        self.assertEqual(localities, {"Cachoeiro de Itapemirim", "Colatina", "Guarapari"})
        familias = {item["cargo"]["familia"] for item in report["itens"]
                    if item["cargo"]["familia"]}
        self.assertEqual(familias, {"Assistente Administrativo"})

    def test_localidade_nao_e_local_de_prova(self):
        _, version = self.doc(text="Requisito.")
        self.prop(version=version, field="vaga_municipio", value="Vitória",
                  quote="208 Analista 1 Vitória", label="208 Analista")
        self.prop(version=version, field="exam_location", value="Florianópolis/SC",
                  quote="Provas em Florianópolis/SC", label="208 Analista")
        item = self.row(label="208 Analista")
        self.assertEqual(item["cargo"]["localidade"]["valor"], "Vitória")
        prova = ((item["localizacao"] or {}).get("prova") or {})
        self.assertIn("Florianópolis", prova.get("text") or "")

    def test_vagas_nao_transferem_entre_codigos(self):
        _, version = self.doc(text="Requisito.")
        self.prop(version=version, field="immediate_vacancies", value=1,
                  quote="200 Cargo A 1", label="200 Cargo A")
        self.prop(version=version, field="immediate_vacancies", value=6,
                  quote="206 Cargo A 6", label="206 Cargo A")
        rows = {item["role_name"]: item for item in self.matrix()["itens"]}
        self.assertEqual(rows["200 Cargo A"]["vacancies"]["immediate"][0]["value"], 1)
        self.assertEqual(rows["206 Cargo A"]["vacancies"]["immediate"][0]["value"], 6)


class QuadrixTableTest(unittest.TestCase):
    TEXT = ("DOS CARGOS E VAGAS CARGOS DE NÍVEL MÉDIO Cod Cargo/Ocupação Vagas efetivas "
            "Cadastro de reserva Total de vagas Local de lotação AC PCD PN PI PQ AC PCD "
            "PN PI PQ 200 Assistente Administrativo - - - - - 18 2 8 1 1 30 Cachoeiro de "
            "Itapemirim 40h R$ 2.341,23 201 Assistente Administrativo - - - - - 18 2 8 1 1 "
            "30 Colatina 40h R$ 2.341,23 208 Assistente de T.I. 1 - - - - 25 2 10 1 1 40 "
            "Vitória 40h R$ 4.050,00 2.2 DOS REQUISITOS")

    def test_localidade_por_codigo(self):
        blocks = [{"text": self.TEXT, "page_number": 2}]
        proposals = quadrix_tables.parse_quadrix_proposals(
            blocks, "c1", label_prefix=LABEL)
        localities = {(p["ambiguity_reason"].replace(LABEL, ""), p["value_json"])
                      for p in proposals if p["field_name"] == "vaga_municipio"}
        self.assertIn(("200 Assistente Administrativo",
                       json.dumps("Cachoeiro de Itapemirim")), localities)
        self.assertIn(("201 Assistente Administrativo", json.dumps("Colatina")), localities)
        self.assertIn(("208 Assistente de T.I.", json.dumps("Vitória")), localities)

    def test_localidade_com_evidencia_da_linha(self):
        blocks = [{"text": self.TEXT, "page_number": 2}]
        proposals = [p for p in quadrix_tables.parse_quadrix_proposals(
            blocks, "c1", label_prefix=LABEL) if p["field_name"] == "vaga_municipio"]
        for item in proposals:
            self.assertIn("Assistente", item["evidence"]["quote"])
            self.assertIn(json.loads(item["value_json"]), item["evidence"]["quote"])

    def test_reprocessamento_e_idempotente(self):
        _, version = self.doc_and_version(self.TEXT)
        first = reprocess.reprocess_version(self.db, version, dry_run=False)
        second = reprocess.reprocess_version(self.db, version, dry_run=False)
        self.assertGreaterEqual(first["novas"], 1)
        self.assertEqual(second["novas"], 0)
        self.assertEqual(second["invalidas"], 0)

    def doc_and_version(self, text):
        self.tmp, self.db = make_db()
        self.addCleanup(self.tmp.cleanup)
        document_id, version = add_document(self.db, "c1", text=text)
        return document_id, version


class MinimumLevelTest(Base):
    def test_nivel_medio_compativel_por_nivel_minimo(self):
        _, version = self.doc(text="Requisito.")
        self.prop(version=version, field="si_compatibility", value="ambiguo",
                  quote=MEDIO_SEM_AREA, label="200 Auxiliar")
        item = self.row(label="200 Auxiliar")
        self.assertEqual(item["si"]["estado"], "nivel_minimo")
        self.assertEqual(item["eligibility"]["estado"], "compativel_por_nivel_minimo")
        self.assertEqual(item["si"]["educacao"]["kind"], "nivel_minimo")
        self.assertIn("escolaridade mínima",
                      item["eligibility"]["estado_label"].lower())

    def test_nivel_superior_sem_area(self):
        _, version = self.doc(text="Requisito.")
        self.prop(version=version, field="si_compatibility", value="ambiguo",
                  quote=SUPERIOR_SEM_AREA, label="400 Analista")
        item = self.row(label="400 Analista")
        self.assertEqual(item["eligibility"]["estado"], "compativel_por_nivel_minimo")

    def test_graduacao_especifica_nao_e_nivel_minimo(self):
        _, version = self.doc(text="Requisito.")
        self.prop(version=version, field="si_compatibility",
                  value="incompativel_com_requisito_explicito",
                  quote=SUPERIOR_DIREITO, label="412 Jurídico")
        item = self.row(label="412 Jurídico")
        self.assertEqual(item["si"]["estado"], "outras_formacoes")
        self.assertEqual(item["si"]["educacao"]["kind"], "formacao_especifica")
        self.assertEqual(item["eligibility"]["estado"], "incompativel_por_requisito")

    def test_nivel_minimo_nao_vira_compativel_quando_ha_area(self):
        _, version = self.doc(text="Requisito.")
        self.prop(version=version, field="si_compatibility", value="ambiguo",
                  quote=TECNICO_DESIGN, label="207 Especializado")
        item = self.row(label="207 Especializado")
        self.assertEqual(item["eligibility"]["estado"], "incompativel_por_requisito")

    def test_registro_profissional_aparece_na_evidencia(self):
        _, version = self.doc(text="Requisito.")
        self.prop(version=version, field="si_compatibility",
                  value="incompativel_com_requisito_explicito",
                  quote=SUPERIOR_DIREITO, label="412 Jurídico")
        item = self.row(label="412 Jurídico")
        quotes = " ".join(entry["quote"] or "" for entry in item["si"]["evidencias"])
        self.assertIn("Registro ativo na OAB", quotes)


class Pilot3049Test(Base):
    """Piloto: códigos 200–206, 208 e 407 do Quadrix 3049."""

    def setUp(self):
        super().setUp()
        _, self.version = self.doc(text="Requisito.")
        for code, city in (("200", "Cachoeiro de Itapemirim"), ("201", "Colatina"),
                           ("202", "Guarapari"), ("203", "Linhares"),
                           ("204", "Venda Nova do Imigrante"), ("205", "Vila Velha"),
                           ("206", "Vitória")):
            label = f"{code} Profissional de Suporte Técnico (PST)-Assistente Administrativo"
            add_proposal(self.db, "c1", version_id=self.version, field="si_compatibility",
                         value="ambiguo", quote=MEDIO_SEM_AREA, reason=LABEL + code)
            add_proposal(self.db, "c1", version_id=self.version, field="education",
                         value="Nível médio", quote=MEDIO_SEM_AREA, reason=LABEL + code)
            add_proposal(self.db, "c1", version_id=self.version,
                         field="immediate_vacancies", value=1,
                         quote=f"{label} 1", reason=LABEL + label)
            add_proposal(self.db, "c1", version_id=self.version, field="vaga_municipio",
                         value=city, quote=f"{label} 1 {city}", reason=LABEL + label)
        add_proposal(self.db, "c1", version_id=self.version, field="si_compatibility",
                     value="abrangido_por_categoria", quote=TECNICO_INFORMATICA,
                     reason=LABEL + "208 Profissional de Suporte Técnico (PST)-Assistente de T.I.")
        add_proposal(self.db, "c1", version_id=self.version, field="si_compatibility",
                     value="abrangido_por_categoria", quote=SUPERIOR_TI,
                     reason=LABEL + "407 Profissional Analista Superior (PAS)-Analista de T.I.")

    def test_200_a_206_sao_nivel_minimo(self):
        report = self.matrix()
        rows = [item for item in report["itens"] if "Assistente Administrativo" in
                (item["role_name"] or "")]
        self.assertEqual(len(rows), 7)
        for item in rows:
            self.assertEqual(item["si"]["estado"], "nivel_minimo")
            self.assertEqual(item["eligibility"]["estado"], "compativel_por_nivel_minimo")
            self.assertEqual(item["si"]["atribuicao"], "codigo_do_cargo")

    def test_200_a_206_preservam_codigo_e_localidade(self):
        report = self.matrix()
        pairs = {(item["cargo"]["codigo"], item["cargo"]["localidade"]["valor"])
                 for item in report["itens"] if "Assistente Administrativo" in
                 (item["role_name"] or "")}
        self.assertEqual(pairs, {
            ("200", "Cachoeiro de Itapemirim"), ("201", "Colatina"),
            ("202", "Guarapari"), ("203", "Linhares"),
            ("204", "Venda Nova do Imigrante"), ("205", "Vila Velha"),
            ("206", "Vitória")})

    def test_208_e_interpretacao_nao_categoria(self):
        item = self.row(label="208 Profissional de Suporte Técnico (PST)-Assistente de T.I.")
        self.assertEqual(item["si"]["estado"], "area_correlata_interpretacao")
        self.assertEqual(item["eligibility"]["estado"], "compativel_por_interpretacao")

    def test_407_e_categoria(self):
        item = self.row(label="407 Profissional Analista Superior (PAS)-Analista de T.I.")
        self.assertEqual(item["si"]["estado"], "categoria_inclui_curso")
        self.assertEqual(item["eligibility"]["estado"], "compativel_sem_vaga_indigena")

    def test_nao_ha_transferencia_de_vagas(self):
        report = self.matrix()
        for item in report["itens"]:
            if item["cargo"]["codigo"] in ("200", "201", "202", "203", "204", "205", "206"):
                self.assertEqual(item["vacancies"]["immediate"][0]["value"], 1)

    def test_nenhuma_decisao_criada(self):
        self.matrix()
        self.assertEqual(self.counts(), (0, 0, 0))


class ReviewAndPendingTest(Base):
    def test_pending_audit_por_causa(self):
        _, version = self.doc(text="Requisito.")
        add_proposal(self.db, "c1", version_id=version, field="si_compatibility",
                     value="ambiguo", quote=MEDIO_SEM_AREA, reason=LABEL + "200")
        add_proposal(self.db, "c1", version_id=version, field="education",
                     value="Superior", quote="200 CARGO A", reason=LABEL + "200 CARGO A")
        report = eligibility.pending_audit(self.db, limit=50, now=NOON)
        self.assertGreaterEqual(report["total"], 2)
        causes = {item["cause"] for item in report["itens"]}
        self.assertIn("codigo_sem_nome", causes)
        self.assertTrue(set(report["por_causa"]) <= set(eligibility.PENDING_CAUSES))

    def test_review_inclui_armazenado_e_derivado(self):
        _, version = self.doc(text="Requisito.")
        self.prop(version=version, field="si_compatibility",
                  value="abrangido_por_categoria", quote=TECNICO_INFORMATICA,
                  label="208 Assistente de T.I.")
        fichas = eligibility.compatibility_review(self.db, limit=50, now=NOON)
        ficha = [item for item in fichas["itens"]
                 if item["role_name"] == "208 Assistente de T.I."][0]
        self.assertEqual(ficha["si_estado"], "area_correlata_interpretacao")
        self.assertEqual(ficha["valor_armazenado"], ["abrangido_por_categoria"])
        self.assertEqual(ficha["educacao"]["nivel"], "tecnico")

    def test_proposta_rejeitada_nao_sustenta(self):
        _, version = self.doc(text="Requisito.")
        proposal = self.prop(version=version, field="si_compatibility",
                             value="aceito_expressamente",
                             quote="curso superior em Sistemas de Informação",
                             label="404 Analista")
        from radar import review
        review.decide_proposal(self.db, proposal, "rejeitado", reviewer="Ana",
                               reason="texto de outro cargo", origin="interface")
        item = self.row(label="404 Analista")
        self.assertEqual(item["si"]["estado"], "nao_encontrado")


class ReviewFindingsTest(Base):
    def test_decisao_validada_nao_e_sobrescrita(self):
        _, version = self.doc(text="Requisito.")
        proposal = self.prop(version=version, field="si_compatibility",
                             value="incompativel_com_requisito_explicito",
                             quote=MEDIO_SEM_AREA, label="200 Cargo")
        from radar import review
        review.decide_proposal(self.db, proposal, "validado", reviewer="Ana",
                               reason="requisito é de nível médio", origin="interface")
        item = self.row(label="200 Cargo")
        # A releitura diria nível mínimo, mas a decisão humana vigente prevalece.
        self.assertEqual(item["si"]["estado"], "outras_formacoes")

    def test_explicito_nao_e_apagado_por_ambiguidade(self):
        _, version = self.doc(text="Requisito A. Requisito B.")
        self.prop(version=version, field="si_compatibility", value="aceito_expressamente",
                  quote="curso superior em Sistemas de Informação", label="404 Analista")
        self.prop(version=version, field="si_compatibility", value="ambiguo",
                  quote="curso superior em área de computação", label="404 Analista")
        item = self.row(label="404 Analista")
        self.assertEqual(item["si"]["estado"], "explicito")

    def test_educacao_vem_da_evidencia_do_estado(self):
        _, version = self.doc(text="Requisito A. Requisito B.")
        self.prop(version=version, field="si_compatibility",
                  value="incompativel_com_requisito_explicito",
                  quote=SUPERIOR_DIREITO, label="412 Jurídico")
        self.prop(version=version, field="si_compatibility", value="ambiguo",
                  quote=MEDIO_SEM_AREA, label="412 Jurídico")
        item = self.row(label="412 Jurídico")
        self.assertEqual(item["si"]["estado"], "outras_formacoes")
        self.assertEqual(item["si"]["educacao"]["kind"], "formacao_especifica")

    def test_atribuicao_por_codigo_exige_leitura(self):
        _, version = self.doc(text="Requisito.")
        add_proposal(self.db, "c1", version_id=version, field="education",
                     value="Nível médio", quote=MEDIO_SEM_AREA, reason=LABEL + "200")
        self.prop(version=version, field="immediate_vacancies", value=1,
                  quote="200 Cargo A 1", label="200 Cargo A")
        item = self.row(label="200 Cargo A")
        self.assertNotEqual(item["si"]["atribuicao"], "codigo_do_cargo")
        self.assertEqual(item["si"]["estado"], "nao_encontrado")

    def test_rotulos_do_cargo_preenchidos(self):
        _, version = self.doc(text="Requisito.")
        self.prop(version=version, field="si_compatibility", value="aceito_expressamente",
                  quote="curso superior em Sistemas de Informação", label="404 Analista")
        add_proposal(self.db, "c1", version_id=version, field="education",
                     value="Superior", quote="Requisito.",
                     reason=LABEL + "404 ANALISTA")
        item = self.row(label="404 Analista")
        self.assertEqual(len(item["cargo"]["rotulos"]), 2)


class ApiTest(Base):
    def setUp(self):
        super().setUp()
        _, version = self.doc(text="Requisito.")
        self.prop(version=version, field="si_compatibility", value="ambiguo",
                  quote=MEDIO_SEM_AREA, label="200 Auxiliar")
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

    def test_rotas_novas(self):
        for path, key in (("/api/elegibilidade/pendentes", "por_causa"),
                          ("/api/elegibilidade/revisao", "por_si")):
            status, body = self.get(path)
            self.assertEqual(status, 200, path)
            self.assertIn(key, json.loads(body))

    def test_parametros_invalidos(self):
        for path in ("/api/elegibilidade/pendentes?cause=xyz",
                     "/api/elegibilidade/pendentes?desconhecido=1",
                     "/api/elegibilidade/revisao?limit=0"):
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
