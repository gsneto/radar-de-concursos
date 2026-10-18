"""Contexto de menções indígenas e separação entre zero publicado e lacuna (Fase 40)."""

import unittest

from radar import decisive_fields, eligibility, indigenous_scope
from tests.test_portfolio_f36 import NOON, add_document, add_proposal, make_db

LABEL = "cargo do documento não reconciliado: "


class MentionContextTest(unittest.TestCase):
    """Só regra de reserva sustenta reserva; as demais menções ficam nomeadas."""

    def context(self, text, title=None):
        return indigenous_scope.mention_context(text, title)

    def test_rani_e_documento_de_identificacao(self):
        self.assertEqual(self.context(
            "Para concorrer, apresentar Registro Administrativo de Nascimento Indígena "
            "(RANI) ou documento equivalente."),
            "documento_de_identificacao")

    def test_adorno_e_vestuario(self):
        self.assertEqual(self.context(
            "É vedado o uso de adorno, cocar ou vestuário indígena durante a prova."),
            "vestuario_ou_adorno")

    def test_conteudo_programatico(self):
        self.assertEqual(self.context(
            "Direitos territoriais dos povos indígenas. Demarcação de terras indígenas. "
            "Usucapião indígena."),
            "conteudo_programatico")

    def test_heteroidentificacao(self):
        self.assertEqual(self.context(
            "Os candidatos indígenas serão submetidos a procedimento de heteroidentificação "
            "e à comissão de verificação."),
            "procedimento_de_heteroidentificacao")

    def test_percentual_para_indigenas_e_regra_de_reserva(self):
        self.assertEqual(self.context(
            "Das vagas, 3% (três por cento) aos indígenas e 2% aos quilombolas."),
            "regra_de_reserva")

    def test_percentual_combinado_nao_e_cota_indigena(self):
        self.assertEqual(self.context(
            "Das vagas ofertadas, 20% (vinte por cento) serão reservadas aos candidatos "
            "negros (pretos e pardos) ou indígenas."),
            "regra_de_reserva_combinada")

    def test_reserva_mencionada_sem_percentual_continua_reserva(self):
        self.assertEqual(self.context("Haverá reserva de vagas para pessoas indígenas."),
                         "regra_de_reserva")

    def test_syllabus_com_negros_e_indigenas_nao_e_reserva(self):
        # "vagas" no mesmo trecho não pode transformar syllabus em reserva.
        self.assertNotIn(self.context(
            "Resistência de negros e indígenas nos períodos Colonial e Imperial. "
            "Serão oferecidas 40 vagas no total."),
            ("regra_de_reserva", "regra_de_reserva_combinada"))

    def test_ano_entre_parenteses_nao_vira_percentual(self):
        # "701 (Marco Temporal)" não é quantidade de vagas.
        self.assertNotIn(self.context(
            "Lei 14.701 (Marco Temporal): reconhecimento de terras indígenas. "
            "Estudo da concorrência."),
            ("regra_de_reserva", "regra_de_reserva_combinada"))

    def test_texto_sem_acento_nao_trava(self):
        # Regressão: a busca sem acento recomeçava do zero e travava o processo.
        self.assertEqual(
            self.context("Fica reservada 1 (uma) vaga para candidato indigena."),
            "regra_de_reserva")

    def test_vagas_sem_percentual_nao_e_reserva(self):
        self.assertEqual(
            self.context("Serão oferecidas 40 vagas. O candidato indígena deverá "
                         "comprovar vínculo."),
            "outro")

    def test_reserva_forte_vence_marcador_de_procedimento(self):
        self.assertEqual(
            self.context("Haverá reserva de vagas para indígenas, mediante "
                         "autodeclaração."),
            "regra_de_reserva")

    def test_combinada_com_indigenas_antes_do_grupo(self):
        self.assertEqual(
            self.context("Reserva de 10% para indígenas e quilombolas."),
            "regra_de_reserva_combinada")

    def test_percentuais_separados_nao_sao_combinados(self):
        self.assertEqual(
            self.context("Das vagas, 3% (três por cento) aos indígenas e 2% aos "
                         "quilombolas."),
            "regra_de_reserva")

    def test_legenda_ni_e_coluna_combinada(self):
        self.assertEqual(
            self.context("N/I: Candidatos negros e indígenas."),
            "regra_de_reserva_combinada")

    def test_contextos_declarados_tem_rotulo(self):
        for context in indigenous_scope.MENTION_CONTEXTS:
            self.assertIn(context, indigenous_scope.MENTION_CONTEXT_LABELS)


class Base(unittest.TestCase):
    def setUp(self):
        self.tmp, self.db = make_db()
        self.addCleanup(self.tmp.cleanup)

    def doc(self, contest="c1", **kwargs):
        return add_document(self.db, contest, **kwargs)

    def prop(self, contest="c1", *, version, field, value, quote, label="CARGO A",
             role_id=None):
        return add_proposal(self.db, contest, version_id=version, field=field,
                            value=value, quote=quote, role_id=role_id,
                            reason=LABEL + label)

    def role(self, contest="c1", name="CARGO A", code=None):
        import sqlite3
        from contextlib import closing
        from tests.test_role_identity_f35 import NOW
        role_id = f"role-{contest}-" + "".join(str(ord(char)) for char in name)
        with closing(sqlite3.connect(self.db)) as conn, conn:
            conn.execute("INSERT OR REPLACE INTO cargos_identidade "
                         "(id,contest_id,name,specialty,created_at,code) "
                         "VALUES (?,?,?,?,?,?)",
                         (role_id, contest, name, None, NOW, code))
        return role_id

    def si(self, version, quote):
        return self.prop(version=version, field="si_compatibility",
                         value="aceito_expressamente", quote=quote)

    def row(self, contest="c1", label=None):
        report = eligibility.matrix(self.db, limit=200, now=NOON)
        for item in report["itens"]:
            if item["contest_id"] != contest:
                continue
            if label is None or (item.get("role_name") or "") == label:
                return item
        raise AssertionError(f"linha não encontrada: {contest} {label}")


class IndigenousStateTest(Base):
    def test_zero_publicado_com_reserva_e_estado_proprio(self):
        role = self.role()
        _, version = self.doc(text="Tabela do cargo.")
        self.prop(version=version, field="si_compatibility", value="aceito_expressamente",
                  quote="Tabela do cargo.", role_id=role)
        self.prop(version=version, field="indigenous_vacancies", value=0,
                  quote="Tabela do cargo.", role_id=role)
        self.prop(version=version, field="indigenous_reserve_vacancies", value=1,
                  quote="Tabela do cargo.", role_id=role)
        item = self.row(label="CARGO A")
        self.assertEqual(item["indigenous"]["estado"],
                         "cargo_zero_imediato_com_reserva")
        self.assertEqual(item["indigenous"]["ambito"], "cargo")
        self.assertIn("zero vaga", item["eligibility"]["motivo"])

    def test_reserva_do_cargo_sem_coluna_imediata(self):
        role = self.role()
        _, version = self.doc(text="Tabela do cargo.")
        self.prop(version=version, field="si_compatibility", value="aceito_expressamente",
                  quote="Tabela do cargo.", role_id=role)
        self.prop(version=version, field="indigenous_reserve_vacancies", value=2,
                  quote="Tabela do cargo.", role_id=role)
        item = self.row(label="CARGO A")
        self.assertEqual(item["indigenous"]["estado"], "cargo_sem_imediata_com_reserva")

    def test_coluna_combinada_nao_vira_cota_indigena(self):
        text = ("Das vagas ofertadas, 20% (vinte por cento) serão reservadas aos "
                "candidatos negros (pretos e pardos) ou indígenas.")
        _, version = self.doc(text=text)
        self.si(version, text)
        item = self.row()
        self.assertEqual(item["indigenous"]["estado"],
                         "reserva_combinada_com_outros_grupos")
        self.assertEqual(item["eligibility"]["estado"], "compativel_sem_vaga_indigena")
        self.assertIn("combinada", item["eligibility"]["motivo"])
        self.assertIn("indígena não separável",
                      item["indigenous"]["estado_label"])

    def test_mencao_lexical_fora_de_reserva_nao_e_reserva(self):
        text = ("Conteúdo programático: usucapião indígena e demarcação de terras "
                "indígenas.")
        _, version = self.doc(text=text)
        self.si(version, text)
        item = self.row()
        self.assertEqual(item["indigenous"]["estado"],
                         "mencao_fora_do_escopo_de_reserva")
        self.assertEqual(item["indigenous"]["evidencias"][0]["contexto"],
                         "conteudo_programatico")

    def test_regra_de_reserva_sem_quantidade_extraida(self):
        text = "Haverá reserva de vagas para pessoas indígenas."
        _, version = self.doc(text=text)
        self.si(version, text)
        item = self.row()
        self.assertEqual(item["indigenous"]["estado"], "mencao_sem_quantidade")
        self.assertIn("sem quantidade extraída",
                      item["indigenous"]["estado_label"])

    def test_linha_do_concurso_nao_usa_rotulo_de_cargo(self):
        text = "Tabela do concurso."
        _, version = self.doc(text=text)
        add_proposal(self.db, "c1", version_id=version,
                     field="indigenous_vacancies", value=0, quote=text)
        add_proposal(self.db, "c1", version_id=version,
                     field="indigenous_reserve_vacancies", value=2, quote=text)
        item = self.row()
        self.assertEqual(item["indigenous"]["estado"],
                         "concurso_sem_imediata_com_reserva")
        self.assertEqual(item["indigenous"]["ambito"], "concurso")
        self.assertNotIn("Tabela do cargo", item["indigenous"]["estado_label"])

    def test_versao_e_denominador_declaram_a_regra(self):
        report = eligibility.matrix(self.db, limit=10, now=NOON)
        self.assertEqual(report["version"], "eligibility_v3")
        self.assertIn("zero imediato", report["denominador"]["indigena"])
        self.assertIn("regra de reserva", report["denominador"]["indigena"])

    def test_filtro_aceita_estado_novo_e_rejeita_desconhecido(self):
        text = ("Das vagas, 20% (vinte por cento) serão reservadas aos candidatos "
                "negros ou indígenas.")
        _, version = self.doc(text=text)
        self.si(version, text)
        report = eligibility.matrix(self.db, limit=10, now=NOON,
                                    indigenous="reserva_combinada_com_outros_grupos")
        self.assertGreaterEqual(report["total"], 1)
        with self.assertRaises(ValueError):
            eligibility.matrix(self.db, limit=10, now=NOON, indigenous="cota_inventada")


class DecisiveIndigenousTest(Base):
    def report_for(self, contest_id="c1"):
        return decisive_fields.decisive_report(self.db, contest_ids=[contest_id],
                                               limit=10)

    def test_coluna_combinada_no_relatorio_decisivo(self):
        self.doc(text="Das vagas ofertadas, 20% (vinte por cento) serão reservadas aos "
                      "candidatos negros ou indígenas.")
        item = self.report_for()["itens"][0]
        self.assertEqual(item["indigenas"]["estado"],
                         "reserva_combinada_com_outros_grupos")
        self.assertEqual(item["indigenas"]["mencao"]["contexto"],
                         "regra_de_reserva_combinada")

    def test_mencao_fora_de_reserva_no_relatorio_decisivo(self):
        self.doc(text="É vedado o uso de adorno ou vestuário indígena.")
        item = self.report_for()["itens"][0]
        self.assertEqual(item["indigenas"]["estado"],
                         "mencao_fora_do_escopo_de_reserva")

    def test_pagina_de_conteudo_antes_da_reserva_nao_esconde_reserva(self):
        import sqlite3
        from contextlib import closing
        from tests.test_role_identity_f35 import NOW
        text = "Conteúdo programático: usucapião indígena."
        document_id, version_id = self.doc(text=text)
        with closing(sqlite3.connect(self.db)) as conn, conn:
            conn.execute("""INSERT INTO blocos_documento
                (id,version_id,page_number,locator,start_offset,end_offset,text)
                VALUES (?,?,?,?,?,?,?)""",
                (f"blk-{version_id}-p4", version_id, 4, "página 4", 0, 60,
                 "Haverá reserva de vagas para pessoas indígenas."))
        item = self.report_for()["itens"][0]
        self.assertEqual(item["indigenas"]["estado"], "mencao_sem_quantidade")
        self.assertEqual(item["indigenas"]["mencao"]["page_number"], 4)


if __name__ == "__main__":
    unittest.main()
