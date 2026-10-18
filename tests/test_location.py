"""Localização estruturada: prova x lotação, abrangência, estados e conflito."""

import unittest

from radar import location


class ParseTest(unittest.TestCase):
    def test_municipio_com_uf_barra(self):
        out = location.parse_location("Salvador/BA")
        self.assertEqual((out["municipio"], out["uf"], out["scope"]), ("Salvador", "BA", "municipal"))
        self.assertEqual(out["confidence"], "alta")

    def test_municipio_com_uf_travessao(self):
        out = location.parse_location("Paulo Afonso - Bahia")
        self.assertEqual(out["uf"], "BA")
        self.assertEqual(out["municipio"], "Paulo Afonso")

    def test_apenas_estado_por_nome(self):
        out = location.parse_location("As provas ocorrerão no estado da Bahia")
        self.assertEqual(out["uf"], "BA")
        self.assertIsNone(out["municipio"])
        self.assertEqual(out["scope"], "estadual")
        self.assertEqual(out["confidence"], "media")

    def test_apenas_uf_isolada(self):
        self.assertEqual(location.parse_location("PE")["uf"], "PE")

    def test_abrangencia_nacional(self):
        out = location.parse_location("lotação em todo o território nacional")
        self.assertEqual(out["scope"], "nacional")
        self.assertIsNone(out["uf"])

    def test_sem_localizacao_reconhecivel(self):
        self.assertIsNone(location.parse_location("ver edital"))
        self.assertIsNone(location.parse_location(None))
        self.assertIsNone(location.parse_location(""))

    def test_uf_invalida_nao_e_aceita(self):
        # "XX" não é UF: não deve produzir localização municipal.
        out = location.parse_location("Cidade/XX")
        self.assertIsNone(out)

    def test_texto_corrido_nao_vira_municipio(self):
        # Regressão: preposições/verbos não podem virar município nem UF.
        self.assertIsNone(location.parse_location("Vagas - para o cargo de Analista"))
        self.assertIsNone(location.parse_location("Local: a definir - para todos os candidatos"))
        self.assertIsNone(location.parse_location("A prova será realizada na cidade de São Paulo"))

    def test_nome_de_rua_nao_vira_municipio(self):
        self.assertIsNone(location.parse_location("Avenida Bahia - SP"))

    def test_municipio_com_nome_de_estado_com_uf_explicita(self):
        # "Rio de Janeiro/RJ" e "São Paulo/SP" são municípios, não o estado.
        out = location.parse_location("Rio de Janeiro/RJ")
        self.assertEqual((out["municipio"], out["uf"]), ("Rio de Janeiro", "RJ"))
        out = location.parse_location("São Paulo/SP")
        self.assertEqual((out["municipio"], out["uf"]), ("São Paulo", "SP"))
        # Sem UF explícita, o nome continua tratado como estado (não se inventa município).
        out = location.parse_location("Rio de Janeiro")
        self.assertIsNone(out["municipio"])
        self.assertEqual(out["uf"], "RJ")

    def test_municipio_sem_uf_tem_confianca_baixa(self):
        out = location.parse_location("Porto Alegre –")
        self.assertEqual(out["municipio"], "Porto Alegre")
        self.assertIsNone(out["uf"])
        self.assertEqual(out["confidence"], "baixa")

    def test_estados_acentuados(self):
        # Regressão: nomes de estado acentuados devem casar.
        self.assertEqual(location.parse_location("Goiânia - Goiás")["uf"], "GO")
        self.assertEqual(location.parse_location("Belém / Pará")["uf"], "PA")
        self.assertEqual(location.parse_location("Vitória / Espírito Santo")["uf"], "ES")
        self.assertEqual(location.parse_location("no estado de São Paulo")["uf"], "SP")

    def test_municipio_com_prefixo_corrido(self):
        out = location.parse_location("Cidade de Paulo Afonso/BA")
        self.assertEqual(out["municipio"], "Paulo Afonso")
        self.assertEqual(out["uf"], "BA")

    def test_estado_isolado_por_nome(self):
        out = location.parse_location("Rondônia")
        self.assertEqual(out["uf"], "RO")
        self.assertIsNone(out["municipio"])

    def test_conectivo_preservado_no_nome(self):
        self.assertEqual(location.parse_location("Juazeiro do Norte/CE")["municipio"], "Juazeiro do Norte")
        self.assertEqual(location.parse_location("Santa Bárbara d’Oeste/SP")["municipio"],
                         "Santa Bárbara D'Oeste")


class ResolveTest(unittest.TestCase):
    def _proposal(self, field, value, state="extraido", version="v1"):
        return {"field_name": field, "value": value, "state": state,
                "evidence": {"version_id": version, "page_number": 3, "quote": str(value)}}

    def test_prova_e_lotacao_separadas(self):
        proposals = [self._proposal("exam_location", "Salvador/BA"),
                     self._proposal("work_location", "Recife/PE")]
        out = location.resolve_location(proposals, analyzed=True)
        self.assertEqual(out["prova"]["uf"], "BA")
        self.assertEqual(out["prova"]["municipios"], ["Salvador"])
        self.assertEqual(out["lotacao"]["uf"], "PE")
        self.assertEqual(out["lotacao"]["municipios"], ["Recife"])

    def test_lotacao_conhecida_prova_desconhecida(self):
        proposals = [self._proposal("work_location", "Recife/PE")]
        out = location.resolve_location(proposals, analyzed=True)
        self.assertEqual(out["lotacao"]["state"], "extraido_nao_revisado")
        self.assertEqual(out["prova"]["state"], "nao_informado")
        self.assertIsNone(out["prova"]["uf"])

    def test_prova_conhecida_lotacao_desconhecida(self):
        proposals = [self._proposal("exam_location", "Salvador/BA")]
        out = location.resolve_location(proposals, analyzed=True)
        self.assertEqual(out["prova"]["uf"], "BA")
        self.assertEqual(out["lotacao"]["state"], "nao_informado")

    def test_nao_informado_vs_nao_extraido(self):
        out = location.resolve_location([], analyzed=True)
        self.assertEqual(out["prova"]["state"], "nao_informado")
        out2 = location.resolve_location([], analyzed=False)
        self.assertEqual(out2["prova"]["state"], "nao_extraido")

    def test_validado_vira_confirmado(self):
        proposals = [self._proposal("exam_location", "Salvador/BA", state="validado")]
        self.assertEqual(location.resolve_location(proposals, analyzed=True)["prova"]["state"],
                         "confirmado_documentalmente")

    def test_ambiguo_preservado(self):
        proposals = [self._proposal("exam_location", "Salvador/BA", state="ambiguo")]
        self.assertEqual(location.resolve_location(proposals, analyzed=True)["prova"]["state"], "ambiguo")

    def test_conflito_entre_valores(self):
        proposals = [self._proposal("exam_location", "Salvador/BA"),
                     self._proposal("exam_location", "Recife/PE", version="v2")]
        out = location.resolve_location(proposals, analyzed=True)
        self.assertEqual(out["prova"]["state"], "em_conflito")

    def test_campos_coerentes_nao_geram_conflito_falso(self):
        # exam_location presente: extras não são combinados (evita falso conflito).
        proposals = [self._proposal("exam_location", "Salvador/BA"),
                     self._proposal("exam_uf", "BA")]
        out = location.resolve_location(proposals, analyzed=True)
        self.assertNotEqual(out["prova"]["state"], "em_conflito")
        self.assertEqual(out["prova"]["uf"], "BA")

    def test_evidencia_e_versao_preservadas(self):
        proposals = [self._proposal("exam_location", "Salvador/BA", version="vX")]
        prova = location.resolve_location(proposals, analyzed=True)["prova"]
        self.assertEqual(prova["version_id"], "vX")
        self.assertEqual(prova["evidence"]["quote"], "Salvador/BA")

    def test_ausente_nao_vira_distante(self):
        out = location.resolve_location([], analyzed=False)
        self.assertIsNone(out["prova"]["uf"])
        self.assertEqual(out["prova"]["scope"], "desconhecida")


if __name__ == "__main__":
    unittest.main()
