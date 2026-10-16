"""Ranking explicável: rótulos, cobertura, piso excepcional e determinismo."""

import unittest

from radar import ranking


def score(**kwargs):
    base = dict(indigenous_immediate=None, indigenous_reserve=None, si_compatibility="nao_extraido",
                distance_km=None, practical_distance_km=300, exam_uf=None, interest_states=[],
                evidence_confidence=None, confirmed_fields=0, total_decisive=0)
    base.update(kwargs)
    return ranking.score_contest(**base)


class LabelTest(unittest.TestCase):
    def test_boa_aderencia_atual(self):
        out = score(indigenous_immediate=2, si_compatibility="aceito_expressamente",
                    distance_km=50, exam_uf="BA", interest_states=["BA"], evidence_confidence="alta",
                    confirmed_fields=3, total_decisive=3)
        self.assertEqual(out["label"], "boa_aderencia")

    def test_oportunidade_importante_distante(self):
        out = score(indigenous_immediate=8, si_compatibility="aceito_expressamente",
                    distance_km=1500, exam_uf="SP", evidence_confidence="alta",
                    confirmed_fields=3, total_decisive=3)
        self.assertEqual(out["label"], "oportunidade_importante_distante")
        self.assertTrue(out["exceptional"])

    def test_distante_excepcional_nao_desaparece(self):
        distante = score(indigenous_immediate=10, si_compatibility="aceito_expressamente",
                         distance_km=3000, exam_uf="AM", evidence_confidence="alta",
                         confirmed_fields=3, total_decisive=3)
        self.assertGreaterEqual(distante["score"], ranking.EXCEPTIONAL_FLOOR)
        self.assertTrue(distante["exceptional"])

    def test_piso_exige_aceitacao_expressa(self):
        # Regressão: categoria ampla não dispara o piso (evita inflar caso fraco).
        out = score(indigenous_immediate=3, si_compatibility="abrangido_por_categoria",
                    evidence_confidence=None, confirmed_fields=0, total_decisive=0)
        self.assertFalse(out["exceptional"])

    def test_score_nunca_excede_possible(self):
        out = score(indigenous_immediate=3, si_compatibility="aceito_expressamente")
        self.assertLessEqual(out["score"], out["possible"])

    def test_piso_marcado_quando_aplicado(self):
        out = score(indigenous_immediate=3, si_compatibility="aceito_expressamente")
        # Sem distância/evidência, a pontuação bruta é baixa: o piso entra e fica marcado.
        self.assertTrue(out["floor_applied"] or out["score"] >= ranking.EXCEPTIONAL_FLOOR)

    def test_sem_vagas_indigenas_confirmadas_tem_rotulo_proprio(self):
        out = score(indigenous_immediate=0, si_compatibility="aceito_expressamente",
                    distance_km=50, exam_uf="BA", evidence_confidence="alta",
                    confirmed_fields=3, total_decisive=3)
        self.assertEqual(out["label"], "sem_vagas_indigenas")
        self.assertEqual(out["label_text"], "Sem vagas indígenas confirmadas")

    def test_compatibilidade_desfavoravel(self):
        out = score(indigenous_immediate=5, si_compatibility="incompativel_com_requisito_explicito",
                    distance_km=20, exam_uf="BA", evidence_confidence="alta",
                    confirmed_fields=3, total_decisive=3)
        self.assertEqual(out["label"], "compatibilidade_desfavoravel")

    def test_exige_confirmacao_si_ambiguo(self):
        out = score(indigenous_immediate=3, si_compatibility="ambiguo", distance_km=100,
                    evidence_confidence="media", confirmed_fields=1, total_decisive=3)
        self.assertEqual(out["label"], "exige_confirmacao")

    def test_sem_dados_suficientes(self):
        out = score()
        self.assertEqual(out["label"], "sem_dados_suficientes")
        self.assertEqual(out["coverage"], 0.0)


class MissingDataTest(unittest.TestCase):
    def test_ausente_nao_e_zero(self):
        # Reserva indígena ausente -> fator desconhecido (não conta como 0).
        out = score(indigenous_immediate=1, si_compatibility="aceito_expressamente",
                    distance_km=50, exam_uf="BA", evidence_confidence="alta",
                    confirmed_fields=2, total_decisive=2)
        reserve = next(f for f in out["factors"] if f["key"] == "vagas_indigenas_reserva")
        self.assertIsNone(reserve["points"])
        self.assertFalse(reserve["known"])

    def test_zero_confirmado_difere_de_ausente(self):
        zero = score(indigenous_immediate=0, si_compatibility="aceito_expressamente",
                     distance_km=50, exam_uf="BA", evidence_confidence="alta",
                     confirmed_fields=2, total_decisive=2)
        imed = next(f for f in zero["factors"] if f["key"] == "vagas_indigenas_imediatas")
        self.assertEqual(imed["points"], 0)
        self.assertTrue(imed["known"])

    def test_cadastro_reserva_nao_soma_como_imediata(self):
        out = score(indigenous_immediate=0, indigenous_reserve=10,
                    si_compatibility="aceito_expressamente", distance_km=50, exam_uf="BA",
                    evidence_confidence="alta", confirmed_fields=2, total_decisive=2)
        imed = next(f for f in out["factors"] if f["key"] == "vagas_indigenas_imediatas")
        self.assertEqual(imed["points"], 0)  # reserva não vira vaga imediata
        self.assertNotEqual(out["label"], "boa_aderencia")

    def test_so_cadastro_reserva_nao_e_boa_aderencia(self):
        out = score(indigenous_immediate=None, indigenous_reserve=5,
                    si_compatibility="aceito_expressamente", distance_km=50, exam_uf="BA",
                    evidence_confidence="alta", confirmed_fields=2, total_decisive=2)
        self.assertNotEqual(out["label"], "boa_aderencia")


class DeterminismTest(unittest.TestCase):
    def test_mesmos_dados_mesma_pontuacao(self):
        a = score(indigenous_immediate=3, si_compatibility="abrangido_por_categoria",
                  distance_km=200, exam_uf="PE", interest_states=["BA", "PE"],
                  evidence_confidence="media", confirmed_fields=1, total_decisive=3)
        b = score(indigenous_immediate=3, si_compatibility="abrangido_por_categoria",
                  distance_km=200, exam_uf="PE", interest_states=["BA", "PE"],
                  evidence_confidence="media", confirmed_fields=1, total_decisive=3)
        self.assertEqual(a["score"], b["score"])
        self.assertEqual(a["label"], b["label"])
        self.assertEqual(a["factors"], b["factors"])

    def test_versao_presente(self):
        self.assertEqual(score()["version"], ranking.RANKING_VERSION)


class ExplainTest(unittest.TestCase):
    def test_cada_fator_tem_motivo_e_peso(self):
        out = score(indigenous_immediate=2, si_compatibility="aceito_expressamente",
                    distance_km=50, exam_uf="BA", evidence_confidence="alta",
                    confirmed_fields=3, total_decisive=3)
        self.assertTrue(out["factors"])
        for factor in out["factors"]:
            self.assertIn("key", factor)
            self.assertIn("reason", factor)
            self.assertIsInstance(factor["reason"], str)
            self.assertGreater(factor["max"], 0)

    def test_explicacao_rastreavel(self):
        out = score(indigenous_immediate=2, si_compatibility="aceito_expressamente",
                    distance_km=50, exam_uf="BA", evidence_confidence="alta",
                    confirmed_fields=3, total_decisive=3)
        self.assertIn("Sistemas de Informação", out["explain"])
        self.assertIn("vaga", out["explain"].lower())

    def test_coverage_parcial_quando_faltam_dados(self):
        out = score(indigenous_immediate=2, si_compatibility="aceito_expressamente",
                    distance_km=50, exam_uf="BA", evidence_confidence="alta",
                    confirmed_fields=3, total_decisive=3)
        self.assertLessEqual(out["coverage"], 1.0)
        self.assertGreater(out["coverage"], 0.0)

    def test_distancia_influencia_sem_excluir(self):
        perto = score(indigenous_immediate=4, si_compatibility="aceito_expressamente",
                      distance_km=50, exam_uf="BA", evidence_confidence="alta",
                      confirmed_fields=3, total_decisive=3)
        longe = score(indigenous_immediate=4, si_compatibility="aceito_expressamente",
                      distance_km=2500, exam_uf="AM", evidence_confidence="alta",
                      confirmed_fields=3, total_decisive=3)
        self.assertGreater(perto["score"], longe["score"])
        self.assertGreater(longe["score"], 0)  # continua com pontuação (visível)

    def test_urgencia_nao_faz_parte_da_pontuacao(self):
        # A pontuação não recebe urgência: cargo incompatível continua incompatível.
        out = score(indigenous_immediate=5, si_compatibility="incompativel_com_requisito_explicito",
                    distance_km=10, exam_uf="BA", evidence_confidence="alta",
                    confirmed_fields=3, total_decisive=3)
        self.assertEqual(out["label"], "compatibilidade_desfavoravel")


if __name__ == "__main__":
    unittest.main()
